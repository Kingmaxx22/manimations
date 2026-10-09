"""Typography components: titles, headings, labels, emphasis.

All text in a Manimations video comes from here, which is what guarantees
consistent families, weights and sizes across scenes and projects.
"""

from __future__ import annotations

from typing import Iterable, Sequence

from manim import (
    DOWN,
    LEFT,
    RIGHT,
    UP,
    ManimColor,
    RoundedRectangle,
    Text,
    VGroup,
)

from ..theme import THEME, body_font, heading_font, mono_font


# --------------------------------------------------------------------------
# primitives
# --------------------------------------------------------------------------
def headline(text: str, *, size: int | None = None, color: ManimColor | None = None,
             weight: str = "BOLD", font: str | None = None) -> Text:
    """Bold display text (titles, hero text)."""
    return Text(
        text,
        font=font or heading_font(),
        font_size=size or THEME.sizes.title,
        weight=weight,
        color=color or THEME.text,
    )


def body(text: str, *, size: int | None = None, color: ManimColor | None = None,
         weight: str = "NORMAL", line_spacing: float = 0.7) -> Text:
    """Regular explanatory text."""
    return Text(
        text,
        font=body_font(),
        font_size=size or THEME.sizes.body,
        weight=weight,
        color=color or THEME.text_secondary,
        line_spacing=line_spacing,
    )


def label(text: str, *, size: int | None = None, color: ManimColor | None = None,
          weight: str = "MEDIUM") -> Text:
    """Small caption / axis / node label."""
    return Text(
        text,
        font=body_font(),
        font_size=size or THEME.sizes.label,
        weight=weight,
        color=color or THEME.text_secondary,
    )


def mono(text: str, *, size: int | None = None, color: ManimColor | None = None,
         weight: str = "NORMAL") -> Text:
    """Monospaced text for addresses, code and data."""
    return Text(
        text,
        font=mono_font(),
        font_size=size or THEME.sizes.mono,
        weight=weight,
        color=color or THEME.text,
    )


def stat_number(text: str, *, size: int | None = None, color: ManimColor | None = None) -> Text:
    """Oversized number for counters and hero statistics."""
    return Text(
        text,
        font=heading_font(),
        font_size=size or THEME.sizes.stat,
        weight="BOLD",
        color=color or THEME.accent,
    )


# --------------------------------------------------------------------------
# composite headings
# --------------------------------------------------------------------------
def eyebrow(text: str, *, color: ManimColor | None = None) -> VGroup:
    """Small uppercase kicker with a leading accent rule."""
    t = Text(
        text.upper(),
        font=body_font(),
        font_size=THEME.sizes.small,
        weight="BOLD",
        color=color or THEME.accent,
    )
    rule = RoundedRectangle(
        width=0.42, height=0.055, corner_radius=0.03,
        color=color or THEME.accent, fill_opacity=1, stroke_width=0,
    )
    rule.next_to(t, LEFT, buff=0.22)
    return VGroup(rule, t)


def scene_header(title: str, *, accent: ManimColor | None = None,
                 index: str | None = None) -> VGroup:
    """Header used by :meth:`ExplainerScene.add_header`: bar + title + index."""
    accent = accent or THEME.accent
    bar = RoundedRectangle(
        width=0.09, height=0.52, corner_radius=0.04,
        color=accent, fill_opacity=1, stroke_width=0,
    )
    title_t = Text(
        title,
        font=heading_font(),
        font_size=THEME.sizes.heading,
        weight="BOLD",
        color=THEME.text,
    )
    row = VGroup(bar, title_t).arrange(RIGHT, buff=0.28, aligned_edge=UP)
    if index:
        idx = Text(
            index, font=mono_font(), font_size=THEME.sizes.small,
            color=THEME.text_muted,
        )
        idx.next_to(row, RIGHT, buff=0.5)
        idx.align_to(bar, UP)
        row.add(idx)
    return row


def title_card(eyebrow_text: str, title: str, *, accent: ManimColor | None = None,
               subtitle: str | None = None, max_width: float = 12.0) -> VGroup:
    """Large centred title block for scene openers and the cold open."""
    accent = accent or THEME.accent
    parts = VGroup()
    if eyebrow_text:
        parts.add(eyebrow(eyebrow_text, color=accent))
    t = headline(title, size=THEME.sizes.hero)
    if t.width > max_width:
        t.scale(max_width / t.width)
    parts.add(t)
    if subtitle:
        s = body(subtitle, size=THEME.sizes.subheading, color=THEME.text_secondary)
        if s.width > max_width:
            s.scale(max_width / s.width)
        parts.add(s)
    parts.arrange(DOWN, buff=0.42, aligned_edge=LEFT)
    return parts


def footer_note(text: str, *, color: ManimColor | None = None) -> VGroup:
    """Muted footer caption."""
    t = Text(text, font=body_font(), font_size=THEME.sizes.tiny,
             color=color or THEME.text_muted)
    return VGroup(t)


# --------------------------------------------------------------------------
# emphasis
# --------------------------------------------------------------------------
def keyword(text: str, *, color: ManimColor | None = None, size: int | None = None) -> Text:
    """A single emphasised word, used for keyword highlighting."""
    return Text(
        text,
        font=heading_font(),
        font_size=size or THEME.sizes.heading,
        weight="BOLD",
        color=color or THEME.accent,
    )


def highlight_phrase(text: str, phrase: str, *, color: ManimColor | None = None,
                     base_color: ManimColor | None = None, size: int | None = None) -> Text:
    """Text with ``phrase`` recoloured via Manim's ``t2c``.

    Used to emphasise the exact words the narration stresses without animating
    a separate object over the top of the sentence.
    """
    color = color or THEME.accent
    return Text(
        text,
        font=body_font(),
        font_size=size or THEME.sizes.body,
        color=base_color or THEME.text_secondary,
        t2c={phrase: color},
    )


def bullet_list(items: Iterable[str], *, color: ManimColor | None = None,
                marker: str = "—", size: int | None = None,
                buff: float = 0.3) -> VGroup:
    """A left-aligned list with accent markers; returns a VGroup of rows."""
    color = color or THEME.accent
    rows = VGroup()
    for item in items:
        m = Text(marker, font=body_font(), font_size=size or THEME.sizes.body,
                 weight="BOLD", color=color)
        t = body(item, size=size or THEME.sizes.body)
        row = VGroup(m, t).arrange(RIGHT, buff=0.28, aligned_edge=UP)
        rows.add(row)
    rows.arrange(DOWN, buff=buff, aligned_edge=LEFT)
    return rows
