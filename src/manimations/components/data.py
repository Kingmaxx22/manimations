"""Data-visualisation components: counters, timelines, comparisons, meters.

These carry the quantitative and structural parts of an explanation — how many
addresses exist, when something happened, how two systems differ — without
resorting to a table of numbers.
"""

from __future__ import annotations

from typing import Sequence

from manim import (
    DOWN,
    LEFT,
    RIGHT,
    UP,
    DecimalNumber,
    ManimColor,
    Mobject,
    RoundedRectangle,
    ValueTracker,
    VGroup,
)

from ..helpers import layout
from ..theme import THEME
from . import surfaces, typography


# --------------------------------------------------------------------------
# counters
# --------------------------------------------------------------------------
def counter(value: float = 0.0, *, label: str | None = None, unit: str | None = None,
            accent: ManimColor | None = None, size: int | None = None,
            decimals: int = 0, compact: bool = False,
            max_width: float | None = None) -> VGroup:
    """An animated number with an optional label and unit.

    Returns a ``VGroup`` whose index 0 is the live number; the ``ValueTracker``
    that drives it is attached as ``.tracker`` so callers can animate it::

        cnt = data.counter(0, label="addresses")
        scene.play(cnt.tracker.animate.set_value(4_294_967_296))
    """
    accent = accent or THEME.accent
    tracker = ValueTracker(value)
    max_w = max_width if max_width is not None else layout.safe_width()

    def _render() -> VGroup:
        n = DecimalNumber(
            tracker.get_value(),
            num_decimal_places=decimals,
            font_size=size or THEME.sizes.stat,
            color=accent,
        )
        row = VGroup(n)
        if unit:
            row.add(typography.label(unit, size=THEME.sizes.subheading,
                                     color=THEME.text_secondary))
        row.arrange(RIGHT, buff=0.18, aligned_edge=DOWN)
        # A counter grows as digits are added (0 -> 4,294,967,296 is 10x wider),
        # so fit it on every redraw or the final value overflows the frame.
        if row.width > max_w:
            row.scale(max_w / row.width)
        return row

    number = _render()
    # Redraw in place: replace the old glyphs but keep the mobject's position so
    # the number never drifts to the origin as it counts.
    def _update(_mob: Mobject) -> None:
        fresh = _render()
        fresh.move_to(number.get_center())
        number.become(fresh)

    number.add_updater(_update)
    parts = VGroup(number)
    if label:
        lab = typography.label(label, size=THEME.sizes.body, color=THEME.text_secondary)
        lab.next_to(number, DOWN, buff=0.24)
        parts.add(lab)
    # The ValueTracker is not a VMobject, so it cannot live inside the VGroup;
    # expose it as an attribute instead: ``counter_obj.tracker``.
    parts.tracker = tracker  # type: ignore[attr-defined]
    return parts


def count_to(tracker: ValueTracker, target: float, *, run_time: float = 1.6):
    """Animation that animates a counter's tracker to ``target``."""
    return tracker.animate.set_value(target)


# --------------------------------------------------------------------------
# timelines
# --------------------------------------------------------------------------
def timeline(markers: Sequence[tuple[str, str]], *, width: float | None = None,
             accent: ManimColor | None = None, up: bool = True,
             label_size: int | None = None) -> VGroup:
    """A horizontal timeline.

    ``markers`` is a sequence of ``(when, what)`` pairs, e.g.
    ``("1998", "IPv6 standardised")``.  Returns a VGroup of the axis plus one
    sub-VGroup per marker so they can be revealed one at a time.
    """
    accent = accent or THEME.accent
    width = width or layout.safe_width() - 1.0
    axis = RoundedRectangle(width=width, height=0.07, corner_radius=0.03,
                            fill_color=THEME.border, fill_opacity=1, stroke_width=0)
    n = len(markers)
    g = VGroup(axis)
    positions = [(-width / 2) + width * (i / (n - 1 if n > 1 else 1)) for i in range(n)]
    for x, (when, what) in zip(positions, markers):
        dot = VGroup()
        marker_dot = RoundedRectangle(width=0.16, height=0.16, corner_radius=0.08,
                                      fill_color=accent, fill_opacity=1, stroke_width=0)
        marker_dot.move_to([x, 0, 0])
        stem = typography.mono(when, size=label_size or THEME.sizes.label, color=accent, weight="BOLD")
        stem.next_to(marker_dot, UP if up else DOWN, buff=0.24)
        txt = typography.label(what, size=THEME.sizes.small, color=THEME.text)
        txt.next_to(stem, UP if up else DOWN, buff=0.12)
        layout.fit_width(txt, 3.0)
        dot.add(marker_dot, stem, txt)
        g.add(dot)
    return g


# --------------------------------------------------------------------------
# comparison
# --------------------------------------------------------------------------
def comparison_column(title: str, items: Sequence[str], *, accent: ManimColor | None = None,
                      width: float = 5.2, height: float | None = None) -> VGroup:
    """One column of a side-by-side comparison."""
    accent = accent or THEME.accent
    heading = typography.headline(title, size=THEME.sizes.subheading)
    head_rule = surfaces.divider(width - 0.8, accent=accent)
    rows = VGroup()
    for it in items:
        t = typography.body(it, size=THEME.sizes.body)
        layout.fit_width(t, width - 1.0)
        rows.add(t)
    rows.arrange(DOWN, buff=0.26, aligned_edge=LEFT)
    content = VGroup(heading, head_rule, rows).arrange(DOWN, buff=0.28, aligned_edge=LEFT)
    h = height or content.height + 2 * THEME.spacing.card_pad
    surface = surfaces.panel(width, h, accent=accent)
    content.move_to(surface.get_center())
    return VGroup(surface, content)


def comparison(left_title: str, left_items: Sequence[str], right_title: str,
               right_items: Sequence[str], *, left_accent: ManimColor | None = None,
               right_accent: ManimColor | None = None, gap: float = 0.6) -> VGroup:
    """Two labelled columns side by side, sized to the safe area."""
    lc = comparison_column(left_title, left_items, accent=left_accent)
    rc = comparison_column(right_title, right_items, accent=right_accent)
    lc.move_to([-(lc.width + gap) / 2, 0, 0])
    rc.move_to([(rc.width + gap) / 2, 0, 0])
    return VGroup(lc, rc)


# --------------------------------------------------------------------------
# meters / progress
# --------------------------------------------------------------------------
def meter(fraction: float, *, width: float = 4.0, accent: ManimColor | None = None,
          label: str | None = None, height: float = 0.3) -> VGroup:
    """A horizontal progress bar filled to ``fraction`` (0-1)."""
    accent = accent or THEME.accent
    track = RoundedRectangle(width=width, height=height, corner_radius=0.12,
                             fill_color=THEME.surface_alt, fill_opacity=1.0,
                             stroke_color=THEME.border_soft, stroke_width=1.2)
    fill_w = max(0.02, width * max(0.0, min(1.0, fraction)))
    fill = RoundedRectangle(width=fill_w, height=height, corner_radius=0.12,
                            fill_color=accent, fill_opacity=1.0, stroke_width=0)
    fill.align_to(track, LEFT).shift(RIGHT * 0.02)
    g = VGroup(track, fill)
    if label:
        t = typography.label(label, size=THEME.sizes.small, color=THEME.text_secondary)
        t.next_to(track, UP, buff=0.16)
        g.add(t)
    return g


def stat_block(value: str, caption: str, *, accent: ManimColor | None = None,
               size: int | None = None) -> VGroup:
    """A big number over a caption, centred."""
    num = typography.stat_number(value, size=size or THEME.sizes.stat_small, color=accent)
    cap = typography.label(caption, size=THEME.sizes.body, color=THEME.text_secondary)
    layout.fit_width(cap, 4.6)
    g = VGroup(num, cap).arrange(DOWN, buff=0.22)
    return g
