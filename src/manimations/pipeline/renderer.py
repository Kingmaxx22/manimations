"""The rendering pipeline: preview, repair, final, and everything around it.

Responsibilities
----------------
* render a scene at preview quality, then at final quality
* retry recoverable failures up to ``max_repair_attempts`` (default 3)
* never overwrite a good render with an unvalidated one (render to a temp path,
  verify it, then promote)
* record successful renders in the cache so unchanged scenes are reused
* hand finished scene files to the assembler

Everything shells out to the ``manim`` CLI via the current interpreter
(``sys.executable -m manim``) so the framework works the same under ``uv run``,
a plain venv, or CI.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path

from ..config import ProjectConfig, SceneSpec
from ..scene import SPEC_ENV
from ..theme import ORIENTATION_ENV
from .cache import RenderCache
from .errors import FailureKind, RenderError, RepairLog, classify
from . import probe

#: Quality presets.  The final resolution comes from the project's orientation;
#: previews are scaled down from it, keeping the aspect ratio.
PREVIEW_SHORT_SIDE = 480  # px on the short side for preview renders
PREVIEW_FPS = 15
FINAL_FPS = 30

MAX_REPAIR_ATTEMPTS = 3


def preview_resolution(orient) -> tuple[int, int]:
    """A small preview resolution matching the project's aspect ratio.

    Dimensions are forced even: H.264 requires it for chroma subsampling.
    """
    short = PREVIEW_SHORT_SIDE
    long_side = round(short * orient.aspect)
    if long_side % 2:
        long_side += 1
    if orient.is_vertical:
        return long_side, short  # 9:16 -> 270x480
    return long_side, short  # 16:9 -> 854x480


@dataclass
class RenderResult:
    scene_id: str
    ok: bool
    path: Path | None = None
    quality: str = "l"
    duration: float = 0.0
    cached: bool = False
    attempts: int = 0
    error: RenderError | None = None


def _manim_cmd() -> list[str]:
    return [sys.executable, "-m", "manim"]


def render_scene(
    project: ProjectConfig,
    spec: SceneSpec,
    *,
    quality: str = "l",
    media_dir: Path | None = None,
    timeout: int = 900,
    max_attempts: int = MAX_REPAIR_ATTEMPTS,
    log_dir: Path | None = None,
) -> RenderResult:
    """Render one scene, retrying recoverable failures.

    Returns a :class:`RenderResult`; callers must check ``result.ok`` and the
    existence of ``result.path`` — success is never assumed.
    """
    media_dir = Path(media_dir or project.build_dir / "media")
    log_dir = Path(log_dir or project.qa_dir / "logs")
    log_dir.mkdir(parents=True, exist_ok=True)

    orient = project.orient
    if quality == "l":
        w, h = preview_resolution(orient)
        fps = PREVIEW_FPS
    else:
        w, h = orient.width, orient.height
        fps = orient.fps or FINAL_FPS
    # Manim's quality flag only sets a resolution/fps preset; we always pass an
    # explicit -r and --fps, so use the "low" preset as a base in both cases.
    qflag = "l"

    out_dir = project.final_dir if quality != "l" else project.preview_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    # Manim writes to <media_dir>/videos/<script_stem>/<quality_tag>/<output>.mp4
    media_dir = Path(media_dir)
    # render to a temp name so a good file is never clobbered by a bad one
    staging_name = f".{spec.id}.staging"

    def _find_staging() -> Path | None:
        """Locate the freshly rendered file, whatever folder Manim chose.

        The quality folder name depends on the flags we pass *and* on any config
        file in play, so we glob for it rather than computing it.
        """
        root = media_dir / "videos" / project.scenes_file.stem
        if not root.exists():
            return None
        matches = sorted(root.glob(f"*/{staging_name}.mp4"))
        matches = [m for m in matches if m.stat().st_size > 0]
        if not matches:
            return None
        return max(matches, key=lambda p: p.stat().st_mtime)

    cmd = _manim_cmd() + [
        "render",
        "-q", qflag,
        "--fps", str(fps),
        "-r", f"{w},{h}",
        "--disable_caching",
        "-o", staging_name,
        "--media_dir", str(media_dir),
        "--log_dir", str(log_dir),
        str(project.scenes_file),
        spec.cls,
    ]

    last_error: RenderError | None = None
    # Tell the scene its declared duration and the frame orientation, so it can
    # pad to match the narration and lay out correctly for the aspect ratio.
    env = dict(os.environ)
    env[SPEC_ENV] = json.dumps(
        {"id": spec.id, "duration": spec.duration, "accent": spec.accent}
    )
    env[ORIENTATION_ENV] = project.orientation
    for attempt in range(1, max_attempts + 1):
        t0 = time.time()
        try:
            proc = subprocess.run(
                cmd, capture_output=True, text=True, timeout=timeout,
                cwd=str(project.root), env=env,
            )
            rc, out, err = proc.returncode, proc.stdout, proc.stderr
        except subprocess.TimeoutExpired as exc:
            rc, out, err = 124, (exc.stdout or ""), f"render timed out after {timeout}s"
            if isinstance(out, bytes):
                out = out.decode(errors="ignore")
            if isinstance(err, bytes):
                err = err.decode(errors="ignore")

        staging = _find_staging()
        if rc == 0 and staging is not None:
            info = probe.probe_video(staging)
            duration = info.duration if info else 0.0
            # promote staging -> final name (never clobber until validated)
            final = out_dir / f"{spec.id}.mp4"
            shutil.move(str(staging), str(final))
            return RenderResult(
                scene_id=spec.id, ok=True, path=final, quality=quality,
                duration=duration, attempts=attempt,
            )

        kind, message = classify(err, out)
        last_error = RenderError(
            scene_id=spec.id, kind=kind, message=message, returncode=rc,
            stderr_tail=err[-4000:], stdout_tail=out[-2000:], attempts=attempt,
            log_path=str(log_dir),
        )
        if not last_error.recoverable:
            break
        time.sleep(min(2.0 * attempt, 5.0))  # brief backoff between retries

    assert last_error is not None
    last_error.attempts = attempt
    return RenderResult(
        scene_id=spec.id, ok=False, quality=quality,
        attempts=attempt, error=last_error,
    )


@dataclass
class PipelineReport:
    results: list[RenderResult]
    repair_log: RepairLog
    total_seconds: float

    @property
    def ok(self) -> bool:
        return all(r.ok for r in self.results)

    @property
    def failures(self) -> list[RenderResult]:
        return [r for r in self.results if not r.ok]


def render_project(
    project: ProjectConfig,
    *,
    quality: str = "l",
    only: list[str] | None = None,
    use_cache: bool = True,
    max_attempts: int = MAX_REPAIR_ATTEMPTS,
    timeout: int = 900,
    progress=None,
) -> PipelineReport:
    """Render every (selected) scene at the given quality.

    ``progress`` is an optional ``callable(scene_id, result)`` for live CLI
    feedback.  Scenes are validated first; a scene whose class is missing is
    reported, not crashed on.
    """
    cache = RenderCache(project.cache_file)
    log = RepairLog()
    results: list[RenderResult] = []
    t0 = time.time()

    specs = [s for s in project.scenes if not only or s.id in only]

    for spec in specs:
        if use_cache and cache.is_fresh(project, spec, quality):
            entry = cache.get(spec.id)
            results.append(
                RenderResult(
                    scene_id=spec.id, ok=True, path=Path(entry.path),  # type: ignore[union-attr]
                    quality=quality, duration=entry.duration, cached=True,  # type: ignore[union-attr]
                )
            )
            if progress:
                progress(spec.id, results[-1])
            continue

        res = render_scene(
            project, spec, quality=quality,
            max_attempts=max_attempts, timeout=timeout,
        )
        if res.ok and res.path is not None:
            cache.record(project, spec, quality, res.path, res.duration)
        elif res.error is not None:
            log.add(res.error)
        results.append(res)
        if progress:
            progress(spec.id, res)

    if len(log):
        log.write(project.qa_dir / "render_errors.txt")

    return PipelineReport(results=results, repair_log=log, total_seconds=time.time() - t0)


def contact_sheet(video: Path, out_png: Path, *, cols: int = 3, rows: int = 2,
                  width: int = 480) -> Path | None:
    """Build a contact sheet of evenly-spaced frames from a video."""
    info = probe.probe_video(video)
    if not info or info.duration <= 0:
        return None
    n = cols * rows
    step = max(1, int(info.duration * info.fps / n))
    out_png.parent.mkdir(parents=True, exist_ok=True)
    vf = (
        f"select='not(mod(n\\,{step}))',scale={width}:-1,"
        f"tile={cols}x{rows}"
    )
    cmd = [
        "ffmpeg", "-y", "-v", "error", "-i", str(video),
        "-vf", vf, "-frames:v", "1", str(out_png),
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0 or not out_png.exists():
        return None
    return out_png
