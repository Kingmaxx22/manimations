"""Design system for Manimations.

Centralises every visual token: palette, typography, spacing, motion, and the
global Manim render configuration.  Topic projects import from here and never
hard-code colours or font sizes, which is what keeps a library of explainers
looking like one coherent channel.

Units: Manim scene units.  With ``frame_height = 8`` and a 1920x1080 canvas,
1 scene unit is 135 px, so the safe area is roughly x in [-6.7, 6.7] and
y in [-3.6, 3.6] after margins.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from functools import lru_cache

from manim import ManimColor, Text, config

#: Environment variable carrying the active orientation name ("landscape" or
#: "vertical").  Set by the render pipeline so scene files need no project import.
ORIENTATION_ENV = "MANIMATIONS_ORIENTATION"

# --------------------------------------------------------------------------
# Palette
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class Palette:
    """Raw hex tokens.  Restrained dark-navy base with a small accent set."""

    # backgrounds / surfaces
    bg: str = "#0B1220"
    bg_deep: str = "#070C16"
    surface: str = "#141E33"
    surface_alt: str = "#1B2740"
    surface_raised: str = "#22304C"

    # lines
    border: str = "#2E3F5E"
    border_soft: str = "#22304A"
    grid: str = "#16223A"

    # type
    text: str = "#F2F6FC"
    text_secondary: str = "#A9B8D4"
    text_muted: str = "#6C7E9E"

    # accents (recurring concepts get stable colours)
    cyan: str = "#22D3EE"
    violet: str = "#8B7BFF"
    amber: str = "#FBBF24"
    green: str = "#34D399"
    rose: str = "#FB7185"
    blue: str = "#60A5FA"
    slate: str = "#94A3B8"


# --------------------------------------------------------------------------
# Fonts
# --------------------------------------------------------------------------

# Ordered preferences; the first installed family wins.  Keeps the framework
# portable between this Windows box, macOS and Linux CI.
_HEADING_CANDIDATES = ("Segoe UI", "Inter", "Helvetica Neue", "DejaVu Sans", "Arial")
_BODY_CANDIDATES = ("Segoe UI", "Inter", "Helvetica Neue", "DejaVu Sans", "Arial")
_MONO_CANDIDATES = (
    "JetBrains Mono",
    "Cascadia Mono",
    "Consolas",
    "DejaVu Sans Mono",
    "Menlo",
    "monospace",
)


@lru_cache(maxsize=8)
def _resolve_font(candidates: tuple[str, ...]) -> str:
    """Return the first font family that actually renders on this machine."""
    for name in candidates:
        try:
            Text("Aa", font=name)
            return name
        except Exception:  # pragma: no cover - depends on host fonts
            continue
    return candidates[-1]


def heading_font() -> str:
    return _resolve_font(_HEADING_CANDIDATES)


def body_font() -> str:
    return _resolve_font(_BODY_CANDIDATES)


def mono_font() -> str:
    return _resolve_font(_MONO_CANDIDATES)


# --------------------------------------------------------------------------
# Sizes, spacing, motion
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class Sizes:
    """Point sizes tuned for 1920x1080."""

    hero: int = 96
    title: int = 76
    heading: int = 50
    subheading: int = 40
    body: int = 33
    label: int = 26
    small: int = 22
    tiny: int = 18
    mono: int = 34
    mono_small: int = 26
    mono_tiny: int = 21
    stat: int = 128
    stat_small: int = 84


@dataclass(frozen=True)
class Spacing:
    """Scene-unit spacing scale (roughly an 8pt grid at 135 px/unit)."""

    xs: float = 0.12
    sm: float = 0.22
    md: float = 0.38
    lg: float = 0.62
    xl: float = 0.95
    xxl: float = 1.4

    margin_x: float = 0.85  # safe-area inset from the frame edge
    margin_y: float = 0.55
    card_pad: float = 0.34
    content_top: float = 2.55  # y of the first content row under a header
    header_y: float = 3.15


@dataclass(frozen=True)
class Motion:
    """Duration presets, in seconds.  Everything stays in the 0.3-1.2 band."""

    quick: float = 0.35
    base: float = 0.6
    medium: float = 0.9
    slow: float = 1.3
    reveal_lag: float = 0.14
    beat: float = 0.5  # small pause between ideas
    breath: float = 1.1  # end-of-scene settle


@dataclass(frozen=True)
class Theme:
    palette: Palette = field(default_factory=Palette)
    sizes: Sizes = field(default_factory=Sizes)
    spacing: Spacing = field(default_factory=Spacing)
    motion: Motion = field(default_factory=Motion)

    # --- convenience colour accessors (ManimColor, cached per instance) ---
    def __post_init__(self) -> None:
        p = self.palette
        object.__setattr__(self, "bg", ManimColor(p.bg))
        object.__setattr__(self, "bg_deep", ManimColor(p.bg_deep))
        object.__setattr__(self, "surface", ManimColor(p.surface))
        object.__setattr__(self, "surface_alt", ManimColor(p.surface_alt))
        object.__setattr__(self, "surface_raised", ManimColor(p.surface_raised))
        object.__setattr__(self, "border", ManimColor(p.border))
        object.__setattr__(self, "border_soft", ManimColor(p.border_soft))
        object.__setattr__(self, "grid", ManimColor(p.grid))
        object.__setattr__(self, "text", ManimColor(p.text))
        object.__setattr__(self, "text_secondary", ManimColor(p.text_secondary))
        object.__setattr__(self, "text_muted", ManimColor(p.text_muted))
        object.__setattr__(self, "cyan", ManimColor(p.cyan))
        object.__setattr__(self, "violet", ManimColor(p.violet))
        object.__setattr__(self, "amber", ManimColor(p.amber))
        object.__setattr__(self, "green", ManimColor(p.green))
        object.__setattr__(self, "rose", ManimColor(p.rose))
        object.__setattr__(self, "blue", ManimColor(p.blue))
        object.__setattr__(self, "slate", ManimColor(p.slate))

    # --- semantic aliases used across components ---
    @property
    def accent(self) -> ManimColor:
        return self.cyan

    def accent_named(self, name: str) -> ManimColor:
        """Map a brief-supplied accent name to a colour."""
        return {
            "cyan": self.cyan,
            "violet": self.violet,
            "amber": self.amber,
            "green": self.green,
            "rose": self.rose,
            "blue": self.blue,
            "slate": self.slate,
        }.get(name, self.cyan)


THEME = Theme()


# --------------------------------------------------------------------------
# Orientation and render configuration
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class Orientation:
    """A video orientation: the output contract for one deliverable."""

    name: str
    width: int
    height: int
    fps: int = 30
    #: Manim frame height in scene units.  Held at 8 in both orientations so the
    #: vertical spacing tokens stay valid; the width is derived from the aspect.
    frame_height: float = 8.0

    @property
    def aspect(self) -> float:
        return self.width / self.height

    @property
    def frame_width(self) -> float:
        return self.frame_height * self.aspect

    @property
    def is_vertical(self) -> bool:
        return self.height > self.width

    @property
    def safe_width(self) -> float:
        """Usable scene-unit width inside the default horizontal margins."""
        return self.frame_width - 2 * 0.85


#: Landscape 16:9 — the default for YouTube-style explainers.
LANDSCAPE = Orientation("landscape", 1920, 1080, 30)
#: Vertical 9:16 — TikTok / Reels / Shorts.
VERTICAL = Orientation("vertical", 1080, 1920, 30)

ORIENTATIONS: dict[str, Orientation] = {
    "landscape": LANDSCAPE,
    "vertical": VERTICAL,
}

#: Backwards-compatible aliases for the landscape contract.
VIDEO_WIDTH = LANDSCAPE.width
VIDEO_HEIGHT = LANDSCAPE.height
VIDEO_FPS = LANDSCAPE.fps

#: Manim quality shorthand used by the pipeline.
PREVIEW_QUALITY = "l"  # low-res, 15fps
FINAL_QUALITY = "h"  # 1080p-class, fps overridden explicitly


def _active_orientation() -> Orientation:
    """The orientation the current render is using (set by the pipeline)."""
    name = os.environ.get(ORIENTATION_ENV, "landscape").strip().lower()
    return ORIENTATIONS.get(name, LANDSCAPE)


def apply_theme(background: ManimColor | None = None,
                orientation: Orientation | None = None) -> Theme:
    """Force Manim's global config to the Manimations design language.

    Called automatically by :class:`manimations.scene.ExplainerScene`.  Safe to
    call repeatedly.

    The orientation (landscape 16:9 or vertical 9:16) is taken from the
    ``MANIMATIONS_ORIENTATION`` environment variable when the pipeline sets it,
    so a scene file needs no project import to render correctly in either format.

    Important: this deliberately does **not** set ``pixel_width`` /
    ``pixel_height`` / ``frame_rate``.  Resolution and frame rate are owned by
    the render quality flags (``-q l`` for previews, ``-r W,H --fps N`` for
    finals) so that previews stay fast.  Only the background colour and the
    frame aspect ratio are forced here.
    """
    orient = orientation or _active_orientation()
    config.background_color = background or THEME.bg
    # Frame height stays 8 units in both orientations; the width follows the
    # aspect ratio.  Vertical is therefore simply a narrower frame.
    config.frame_height = orient.frame_height
    config.frame_width = orient.frame_width
    return THEME
