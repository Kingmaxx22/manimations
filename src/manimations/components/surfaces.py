"""Surfaces, cards, connectors and callouts.

These are the structural pieces every diagram is assembled from: rounded
surfaces that group ideas, arrows that show flow, and callouts that annotate a
specific element while the narration talks about it.
"""

from __future__ import annotations

from typing import Iterable, Sequence

from manim import (
    DOWN,
    LEFT,
    RIGHT,
    UP,
    Arrow,
    DashedLine,
    Line,
    ManimColor,
    Mobject,
    RoundedRectangle,
    Triangle,
    VGroup,
)

from ..helpers import layout
from ..theme import THEME
from . import typography


# --------------------------------------------------------------------------
# surfaces
# --------------------------------------------------------------------------
def panel(width: float, height: float, *, accent: ManimColor | None = None,
          fill: ManimColor | None = None, stroke: ManimColor | None = None,
          corner_radius: float = 0.16, fill_opacity: float = 1.0,
          stroke_width: float = 1.6) -> RoundedRectangle:
    """A flat rounded surface used as a card/panel background."""
    return RoundedRectangle(
        width=width,
        height=height,
        corner_radius=corner_radius,
        fill_color=fill or THEME.surface,
        fill_opacity=fill_opacity,
        stroke_color=stroke or accent or THEME.border,
        stroke_width=stroke_width,
    )


def card(title: str | None = None, body_text: str | None = None, *, width: float = 3.6,
         accent: ManimColor | None = None, title_size: int | None = None,
         body_size: int | None = None, pad: float | None = None,
         icon: Mobject | None = None, min_height: float | None = None) -> VGroup:
    """A titled card.  Returns ``VGroup(surface, content)``.

    The surface is the first submobject so callers can target it for highlight
    animations (``card[0].set_stroke(...)``).
    """
    pad = pad if pad is not None else THEME.spacing.card_pad
    accent = accent or THEME.accent
    inner = VGroup()
    if icon is not None:
        inner.add(icon)
    if title:
        inner.add(typography.headline(title, size=title_size or THEME.sizes.subheading))
    if body_text:
        inner.add(typography.body(body_text, size=body_size or THEME.sizes.body))
    if not inner:
        inner.add(Mobject())
    inner.arrange(DOWN, buff=0.24, aligned_edge=LEFT)
    layout.fit_width(inner, width - 2 * pad)
    height = max(min_height or 0.0, inner.height + 2 * pad)
    surface = panel(width, height, accent=accent)
    inner.move_to(surface.get_center())
    return VGroup(surface, inner)


def badge(text: str, *, accent: ManimColor | None = None, size: int | None = None,
          max_width: float | None = None) -> VGroup:
    """A small pill label (e.g. "IPv4", "32-bit").

    The pill is sized from its text, so a long label can exceed a narrow frame
    on its own: a 30-character badge measures 4.4 units, which is wider than the
    whole 4.5-unit 9:16 frame.  It is therefore fitted to the safe area by
    default, like every other component that can grow.
    """
    accent = accent or THEME.accent
    t = typography.label(text, size=size or THEME.sizes.small, color=accent, weight="BOLD")
    surface = RoundedRectangle(
        width=t.width + 0.42, height=t.height + 0.26, corner_radius=0.14,
        fill_color=accent, fill_opacity=0.14, stroke_color=accent, stroke_width=1.4,
    )
    t.move_to(surface.get_center())
    pill = VGroup(surface, t)
    limit = max_width if max_width is not None else layout.safe_width() * 0.94
    layout.fit_width(pill, limit)
    return pill


# --------------------------------------------------------------------------
# connectors
# --------------------------------------------------------------------------
def connector(a: Mobject, b: Mobject, *, accent: ManimColor | None = None,
              buff: float = 0.12, arrow: bool = True, dashed: bool = False,
              stroke_width: float = 3.0, tip_size: float = 0.2) -> Mobject:
    """A line (or arrow) from mobject ``a`` to mobject ``b``."""
    accent = accent or THEME.accent
    cls = DashedLine if dashed else (Arrow if arrow else Line)
    kwargs = dict(color=accent, buff=buff, stroke_width=stroke_width)
    if arrow:
        kwargs["tip_length"] = tip_size
        kwargs["max_tip_length_to_length_ratio"] = 0.25
    return cls(a.get_center(), b.get_center(), **kwargs)


def elbow_connector(a: Mobject, b: Mobject, *, accent: ManimColor | None = None,
                    direction: str = "auto") -> VGroup:
    """Right-angled connector for flowcharts / topology diagrams.

    Built from two line segments with an arrow head, so it works on any Manim
    version (``ElbowArrow`` is not available in all releases).
    """
    accent = accent or THEME.accent
    start, end = a.get_center(), b.get_center()
    mid = [end[0], start[1], 0] if direction in ("auto", "hv") else [start[0], end[1], 0]
    leg1 = Line(start, mid, color=accent, stroke_width=3.0)
    leg2 = Arrow(mid, end, color=accent, stroke_width=3.0, buff=0.0,
                 tip_length=0.2, max_tip_length_to_length_ratio=0.3)
    return VGroup(leg1, leg2)


def flow_arrow(start, end, *, accent: ManimColor | None = None,
               stroke_width: float = 3.0, tip_size: float = 0.22) -> Arrow:
    """A standalone arrow between two points."""
    return Arrow(
        start, end, color=accent or THEME.accent,
        buff=0.0, stroke_width=stroke_width, tip_length=tip_size,
        max_tip_length_to_length_ratio=0.3,
    )


# --------------------------------------------------------------------------
# callouts / annotation
# --------------------------------------------------------------------------
def callout(text: str, *, accent: ManimColor | None = None, size: int | None = None,
            max_width: float = 3.6) -> VGroup:
    """A small annotated note with an accent edge; meant to point at a target."""
    accent = accent or THEME.amber
    t = typography.body(text, size=size or THEME.sizes.small, color=THEME.text)
    layout.fit_width(t, max_width - 0.5)
    surface = RoundedRectangle(
        width=t.width + 0.5, height=t.height + 0.42, corner_radius=0.12,
        fill_color=THEME.surface_alt, fill_opacity=1.0,
        stroke_color=accent, stroke_width=1.4,
    )
    edge = RoundedRectangle(
        width=0.075, height=t.height + 0.42, corner_radius=0.03,
        fill_color=accent, fill_opacity=1.0, stroke_width=0,
    )
    edge.align_to(surface, LEFT).shift(RIGHT * 0.03)
    t.move_to(surface.get_center()).shift(RIGHT * 0.06)
    return VGroup(surface, edge, t)


def annotation_arrow(target: Mobject, text: str, *, direction=DOWN,
                     accent: ManimColor | None = None, distance: float = 1.5,
                     max_width: float = 3.4) -> VGroup:
    """A callout box joined to ``target`` by a short arrow.

    Returns ``VGroup(callout, arrow)`` positioned ``distance`` away from the
    target in ``direction``.
    """
    accent = accent or THEME.amber
    box = callout(text, accent=accent, max_width=max_width)
    box.next_to(target, direction, buff=distance)
    arrow = Arrow(
        box.get_edge_center(-direction), target.get_edge_center(direction),
        color=accent, buff=0.08, stroke_width=2.6, tip_length=0.18,
    )
    return VGroup(box, arrow)


def pointer(target: Mobject, *, accent: ManimColor | None = None,
            size: float = 0.28) -> Triangle:
    """A small triangle that points down at a target from above."""
    tri = Triangle(color=accent or THEME.amber, fill_opacity=1, stroke_width=0)
    tri.scale(size)
    tri.rotate(3.14159)  # point downward
    tri.next_to(target, UP, buff=0.14)
    return tri


def bracket(target: Mobject, *, accent: ManimColor | None = None,
            height: float = 0.9, side=LEFT) -> VGroup:
    """A curly-free bracket marking a span (used to group address bytes)."""
    accent = accent or THEME.accent
    span = target.height + 0.3
    vertical = Line([0, -span / 2, 0], [0, span / 2, 0], color=accent, stroke_width=3)
    top = Line([0, span / 2, 0], [0.22, span / 2, 0], color=accent, stroke_width=3)
    bot = Line([0, -span / 2, 0], [0.22, -span / 2, 0], color=accent, stroke_width=3)
    g = VGroup(vertical, top, bot)
    if side is LEFT:
        g.flip(RIGHT)
        g.next_to(target, LEFT, buff=0.18)
    else:
        g.next_to(target, RIGHT, buff=0.18)
    return g


def divider(width: float, *, accent: ManimColor | None = None) -> Line:
    """A thin horizontal rule."""
    return Line(
        [-width / 2, 0, 0], [width / 2, 0, 0],
        color=accent or THEME.border_soft, stroke_width=2,
    )


def progress_track(total: int, filled: int, *, width: float = 4.0,
                   accent: ManimColor | None = None, gap: float = 0.1) -> VGroup:
    """A row of ``total`` segments with ``filled`` highlighted."""
    accent = accent or THEME.accent
    seg_w = (width - gap * (total - 1)) / total
    g = VGroup()
    for i in range(total):
        seg = RoundedRectangle(
            width=seg_w, height=0.22, corner_radius=0.05,
            fill_color=accent if i < filled else THEME.surface_alt,
            fill_opacity=1.0 if i < filled else 0.8,
            stroke_color=accent if i < filled else THEME.border_soft,
            stroke_width=1.2,
        )
        g.add(seg)
    g.arrange(RIGHT, buff=gap)
    return g
