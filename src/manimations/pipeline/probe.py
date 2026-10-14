"""Thin ffprobe/ffmpeg wrappers used for output validation.

Output validation is a hard requirement: the pipeline must confirm resolution,
frame rate and duration from the actual file on disk, never from the fact that a
subprocess exited 0.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path


@dataclass
class VideoInfo:
    path: str
    width: int
    height: int
    fps: float
    duration: float
    n_frames: int
    has_audio: bool
    vcodec: str = ""
    acodec: str = ""

    def matches(self, width: int, height: int, fps: float, tol: float = 0.6) -> bool:
        return (
            self.width == width
            and self.height == height
            and abs(self.fps - fps) <= tol
        )


def have_ffmpeg() -> bool:
    return bool(shutil.which("ffmpeg") and shutil.which("ffprobe"))


def _parse_rate(rate: str) -> float:
    if not rate or "/" not in rate:
        try:
            return float(rate)
        except (TypeError, ValueError):
            return 0.0
    num, den = rate.split("/")
    try:
        den_f = float(den)
        return float(num) / den_f if den_f else 0.0
    except (TypeError, ValueError):
        return 0.0


def probe_video(path: str | Path) -> VideoInfo | None:
    """Return stream metadata for ``path`` or ``None`` if it cannot be probed."""
    path = Path(path)
    if not path.exists():
        return None
    cmd = [
        "ffprobe", "-v", "error", "-print_format", "json",
        "-show_format", "-show_streams", str(path),
    ]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    except (subprocess.SubprocessError, OSError):
        return None
    if proc.returncode != 0:
        return None
    try:
        data = json.loads(proc.stdout or "{}")
    except json.JSONDecodeError:
        return None

    streams = data.get("streams", [])
    vstream = next((s for s in streams if s.get("codec_type") == "video"), None)
    astream = next((s for s in streams if s.get("codec_type") == "audio"), None)
    if vstream is None:
        return None

    fmt = data.get("format", {})
    duration = float(fmt.get("duration") or vstream.get("duration") or 0.0)
    n_frames = 0
    try:
        n_frames = int(vstream.get("nb_frames") or 0)
    except (TypeError, ValueError):
        n_frames = 0
    if not n_frames and duration:
        n_frames = int(duration * _parse_rate(vstream.get("r_frame_rate", "0")))

    return VideoInfo(
        path=str(path.resolve()),
        width=int(vstream.get("width", 0)),
        height=int(vstream.get("height", 0)),
        fps=_parse_rate(vstream.get("r_frame_rate", "0")),
        duration=duration,
        n_frames=n_frames,
        has_audio=astream is not None,
        vcodec=vstream.get("codec_name", ""),
        acodec=(astream or {}).get("codec_name", ""),
    )


def probe_audio_duration(path: str | Path) -> float:
    """Duration in seconds of an audio file (0.0 on failure)."""
    path = Path(path)
    if not path.exists():
        return 0.0
    cmd = [
        "ffprobe", "-v", "error", "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1", str(path),
    ]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        return float(proc.stdout.strip() or 0.0)
    except (subprocess.SubprocessError, ValueError, OSError):
        return 0.0


def scene_durations(files: Iterable[str | Path]) -> dict[str, float]:
    """Measured duration of each rendered scene file, keyed by scene id.

    The file stem is the scene id (``build/final/03_solution.mp4`` ->
    ``03_solution``).  Files that are missing or unreadable are left out so
    callers can fall back to the brief's declared duration for those.

    Why this exists: a scene's declared ``duration`` is a *target*, not a
    promise.  ``ExplainerScene._pad_to_target`` holds the final frame until the
    target, but when the scene's own animation already runs longer it applies a
    minimum hold INSTEAD of the pad, so the scene renders longer than declared.
    Any timeline built afterwards — the narration track, the subtitles, the SFX
    cues — has to follow what was actually rendered, or every later scene's
    voice starts early by the overrun.  Measured on episode-32-lazydocker: a
    1.3 s overrun on scene 01 put scene 03's voice 1.1 s before scene 03
    appeared, with the last 2.5 s of the video silent.
    """
    out: dict[str, float] = {}
    for item in files:
        path = Path(item)
        if not path.exists():
            continue
        info = probe_video(path)
        if info is not None and info.duration > 0:
            out[path.stem] = info.duration
    return out


def extract_frames(video: str | Path, out_dir: str | Path, *, fps: float = 1.0,
                   width: int = 480) -> list[Path]:
    """Extract frames at ``fps`` into ``out_dir``; returns sorted paths."""
    video, out_dir = Path(video), Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    for old in out_dir.glob("frame_*.png"):
        old.unlink()
    cmd = [
        "ffmpeg", "-y", "-v", "error", "-i", str(video),
        "-vf", f"fps={fps},scale={width}:-1", str(out_dir / "frame_%05d.png"),
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        return []
    return sorted(out_dir.glob("frame_*.png"))


def extract_last_frame(video: str | Path, out_png: str | Path) -> Path | None:
    out_png = Path(out_png)
    out_png.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        "ffmpeg", "-y", "-v", "error", "-sseof", "-0.1", "-i", str(video),
        "-frames:v", "1", str(out_png),
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    return out_png if proc.returncode == 0 and out_png.exists() else None
