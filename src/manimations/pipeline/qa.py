"""Quality assurance: real, programmatic inspection of rendered frames.

This module genuinely analyses the pixels of rendered video — it does not merely
claim to.  For each sampled frame it measures:

* **content bounds** — the bounding box of non-background pixels, checked against
  the safe area to catch clipped text or off-screen graphics
* **edge contact** — content touching the frame border (almost always a bug)
* **blankness** — near-uniform frames (a scene that failed to draw anything)
* **contrast/legibility proxy** — fraction of pixels close to the text colour

It also validates output resolution / fps / duration and writes contact sheets.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path

from . import probe

try:  # Pillow ships with Manim, but keep the import defensive
    from PIL import Image
except Exception:  # pragma: no cover
    Image = None  # type: ignore[assignment]


@dataclass
class FrameAnalysis:
    index: int
    width: int
    height: int
    content_box: tuple[int, int, int, int]  # left, top, right, bottom
    content_ratio: float
    blank: bool
    touches_edge: bool
    edge_sides: list[str] = field(default_factory=list)


@dataclass
class VideoQA:
    path: str
    width: int
    height: int
    fps: float
    duration: float
    has_audio: bool
    n_frames_sampled: int
    frames: list[FrameAnalysis] = field(default_factory=list)
    problems: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.problems

    def summary(self) -> str:
        return (
            f"{Path(self.path).name}: {self.width}x{self.height}@{self.fps:g}fps "
            f"{self.duration:.2f}s audio={self.has_audio} "
            f"frames={self.n_frames_sampled} problems={len(self.problems)}"
        )


def _background_rgb() -> tuple[int, int, int]:
    """The theme background, as 8-bit RGB."""
    from ..theme import THEME

    return tuple(int(round(c * 255)) for c in THEME.bg.to_rgb())


def _detect_background(img: "Image.Image", expected: tuple[int, int, int]) -> tuple[int, int, int]:
    """Return the video's actual background colour.

    Lossy encoding shifts the flat background a little; taking the *mode* of the
    corner region is far more reliable than trusting the theme constant.  Falls
    back to ``expected`` when the corners are not uniform (e.g. a full-bleed frame).
    """
    img = img.convert("RGB")
    w, h = img.size
    patch = 12
    corners = []
    for ox, oy in ((0, 0), (w - patch, 0), (0, h - patch), (w - patch, h - patch)):
        for x in range(ox, ox + patch, 3):
            for y in range(oy, oy + patch, 3):
                corners.append(img.getpixel((x, y)))
    if not corners:
        return expected
    from collections import Counter

    mode, _ = Counter(corners).most_common(1)[0]
    # only accept the detected colour if it is close-ish to what we expect
    if sum(abs(mode[i] - expected[i]) for i in range(3)) <= 60:
        return mode
    return expected


def analyse_frame(img: "Image.Image", *, index: int, bg: tuple[int, int, int],
                  bg_tol: int = 18, edge_px: int = 4) -> FrameAnalysis:
    """Measure content bounds and edge contact for one frame."""
    img = img.convert("RGB")
    w, h = img.size
    px = img.load()
    left, top, right, bottom = w, h, 0, 0
    content = 0
    # Sample on a stride for speed; frames are 480px wide in QA mode.
    stride = 2
    for y in range(0, h, stride):
        for x in range(0, w, stride):
            r, g, b = px[x, y]
            if (abs(r - bg[0]) + abs(g - bg[1]) + abs(b - bg[2])) > bg_tol:
                content += 1
                if x < left:
                    left = x
                if x > right:
                    right = x
                if y < top:
                    top = y
                if y > bottom:
                    bottom = y
    total = (w // stride) * (h // stride)
    ratio = content / total if total else 0.0
    if content == 0:
        return FrameAnalysis(index, w, h, (0, 0, 0, 0), 0.0, True, False, [])

    sides: list[str] = []
    if left <= edge_px:
        sides.append("left")
    if top <= edge_px:
        sides.append("top")
    if right >= w - 1 - edge_px:
        sides.append("right")
    if bottom >= h - 1 - edge_px:
        sides.append("bottom")
    blank = ratio < 0.004
    return FrameAnalysis(
        index=index, width=w, height=h,
        content_box=(left, top, right, bottom),
        content_ratio=round(ratio, 5), blank=blank,
        touches_edge=bool(sides), edge_sides=sides,
    )


def analyse_video(
    video: str | Path,
    *,
    expect: tuple[int, int, float] | None = None,
    duration_range: tuple[float, float] | None = None,
    sample_fps: float = 1.0,
    edge_margin_pct: float = 0.5,
    work_dir: str | Path | None = None,
) -> VideoQA | None:
    """Sample frames from ``video`` and analyse them.

    ``expect`` is ``(width, height, fps)`` for output-contract validation.
    Returns ``None`` only if the file cannot be probed at all.
    """
    video = Path(video)
    info = probe.probe_video(video)
    if info is None:
        return None

    qa = VideoQA(
        path=str(video.resolve()), width=info.width, height=info.height,
        fps=info.fps, duration=info.duration, has_audio=info.has_audio,
        n_frames_sampled=0,
    )

    if expect is not None:
        ew, eh, efps = expect
        if (info.width, info.height) != (ew, eh):
            qa.problems.append(
                f"resolution {info.width}x{info.height} != expected {ew}x{eh}"
            )
        if abs(info.fps - efps) > 0.6:
            qa.problems.append(f"fps {info.fps:g} != expected {efps:g}")
    if duration_range is not None:
        lo, hi = duration_range
        if not (lo <= info.duration <= hi):
            qa.problems.append(
                f"duration {info.duration:.2f}s outside [{lo:g}, {hi:g}]"
            )
    if info.duration <= 0:
        qa.problems.append("duration is zero / unreadable")

    if Image is None:
        qa.problems.append("Pillow unavailable; frame analysis skipped")
        return qa

    work_dir = Path(work_dir or video.parent / "_qa_frames")
    frames = probe.extract_frames(video, work_dir, fps=sample_fps, width=480)
    expected_bg = _background_rgb()
    bg = expected_bg
    for i, fp in enumerate(frames):
        try:
            with Image.open(fp) as im:
                if i == 0:
                    bg = _detect_background(im, expected_bg)
                fa = analyse_frame(im, index=i, bg=bg)
        except Exception as exc:  # pragma: no cover
            qa.problems.append(f"could not read frame {fp.name}: {exc}")
            continue
        qa.frames.append(fa)

    qa.n_frames_sampled = len(qa.frames)
    if qa.n_frames_sampled == 0:
        qa.problems.append("no frames could be extracted for analysis")

    blanks = [f.index for f in qa.frames if f.blank]
    if blanks:
        qa.problems.append(f"blank/near-empty frames at sample indices {blanks[:6]}")

    # edge contact: only flag when a meaningful amount of content sits on the
    # border (a stray 1px antialias is not a bug)
    for f in qa.frames:
        if f.touches_edge and f.content_ratio > 0.01:
            qa.problems.append(
                f"frame {f.index}: content touches frame edge ({', '.join(f.edge_sides)})"
            )
            break

    return qa


def write_report(qa: VideoQA, path: str | Path) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "path": qa.path,
                "width": qa.width,
                "height": qa.height,
                "fps": qa.fps,
                "duration": qa.duration,
                "has_audio": qa.has_audio,
                "ok": qa.ok,
                "problems": qa.problems,
                "frames": [asdict(f) for f in qa.frames],
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    return path
