"""Network components: nodes, devices, links, packets, address blocks.

Purpose-built primitives for internet/networking explainers so those diagrams
stay consistent and are quick to compose.
"""

from __future__ import annotations

from typing import Sequence

from manim import (
    DOWN,
    LEFT,
    RIGHT,
    UP,
    Circle,
    Dot,
    Line,
    ManimColor,
    Mobject,
    RoundedRectangle,
    Square,
    VGroup,
)

from ..theme import THEME
from . import surfaces, typography


# --------------------------------------------------------------------------
# address representation
# --------------------------------------------------------------------------
def address_block(octets: Sequence[str], *, cell_width: float = 0.86,
                  cell_height: float = 0.72, accent: ManimColor | None = None,
                  color_per_cell: Sequence[ManimColor] | None = None,
                  dot: bool = True, group_size: int = 0,
                  mono_size: int | None = None, buff: float = 0.14,
                  group_buff: float = 0.5) -> VGroup:
    """Render an address as a row of cells (e.g. IPv4 ``192 . 168 . 1 . 1``).

    Returns a ``VGroup`` of cell groups (``VGroup(surface, text)``); separators
    are *not* included, so callers can index ``block[i]`` directly for staggered
    reveals.  ``group_size`` inserts a wider ``group_buff`` gap every N cells,
    which is how IPv6 hextet groups are drawn.
    """
    accent = accent or THEME.accent
    cells = VGroup()
    for i, value in enumerate(octets):
        col = (color_per_cell[i] if color_per_cell else accent)
        cell = RoundedRectangle(
            width=cell_width, height=cell_height, corner_radius=0.1,
            fill_color=col, fill_opacity=0.12,
            stroke_color=col, stroke_width=1.8,
        )
        t = typography.mono(value, size=mono_size or THEME.sizes.mono, color=col, weight="BOLD")
        if t.width > cell_width - 0.18:
            t.scale((cell_width - 0.18) / t.width)
        t.move_to(cell.get_center())
        cells.add(VGroup(cell, t))

    sep_char = "." if dot else ":"
    row = VGroup()
    for i, cell in enumerate(cells):
        row.add(cell)
        if i < len(cells) - 1:
            sep = typography.mono(sep_char, size=mono_size or THEME.sizes.mono,
                                  color=THEME.text_muted)
            row.add(sep)

    # Lay out manually so we can vary the gap after every group_size cells.
    # Row structure is cell, sep, cell, sep, ... so odd indices are separators.
    x = 0.0
    for i, part in enumerate(row):
        part.move_to([x + part.width / 2, 0, 0])
        gap = buff
        if group_size and (i % 2 == 1) and (((i + 1) // 2) % group_size == 0):
            gap = group_buff
        x += part.width + gap
    row.move_to([0, 0, 0])
    return row


def bit_grid(rows: int, cols: int, *, cell: float = 0.2, gap: float = 0.05,
             accent: ManimColor | None = None, filled: int = 0,
             fill_opacity: float = 0.9) -> VGroup:
    """A grid of small squares representing bits (32 vs 128 comparison)."""
    accent = accent or THEME.accent
    g = VGroup()
    for i in range(rows * cols):
        sq = Square(
            side_length=cell,
            fill_color=accent if i < filled else THEME.surface_alt,
            fill_opacity=fill_opacity if i < filled else 0.55,
            stroke_color=accent if i < filled else THEME.border_soft,
            stroke_width=1.0,
        )
        g.add(sq)
    g.arrange_in_grid(rows=rows, cols=cols, buff=gap)
    return g


# --------------------------------------------------------------------------
# devices / nodes
# --------------------------------------------------------------------------
def node(text: str | None = None, *, accent: ManimColor | None = None,
         radius: float = 0.42, icon: Mobject | None = None,
         label_below: bool = True, label_size: int | None = None) -> VGroup:
    """A circular network node with an optional label.

    Returns ``VGroup(circle, label)``; the circle is index 0 so it can be
    targeted for pulses and highlights.
    """
    accent = accent or THEME.accent
    circle = Circle(
        radius=radius, fill_color=THEME.surface_alt, fill_opacity=1.0,
        stroke_color=accent, stroke_width=2.2,
    )
    if icon is not None:
        icon.scale_to_fit_height(radius * 0.9).move_to(circle.get_center())
        circle.add(icon)
    g = VGroup(circle)
    if text:
        t = typography.label(text, size=label_size or THEME.sizes.small, color=THEME.text)
        t.next_to(circle, DOWN, buff=0.14)
        g.add(t)
    return g


def router(text: str | None = None, *, accent: ManimColor | None = None,
           width: float = 1.5, height: float = 0.9) -> VGroup:
    """A router/switch box: rounded surface with four port dots."""
    accent = accent or THEME.accent
    box = RoundedRectangle(
        width=width, height=height, corner_radius=0.1,
        fill_color=THEME.surface_alt, fill_opacity=1.0,
        stroke_color=accent, stroke_width=2.2,
    )
    ports = VGroup()
    for i in range(4):
        d = Dot(radius=0.045, color=accent)
        d.move_to([box.get_left()[0] + 0.2 + i * ((width - 0.4) / 3),
                   box.get_bottom()[1] + 0.2, 0])
        ports.add(d)
    core = Line(box.get_left() + [0.18, 0.15, 0], box.get_right() + [-0.18, 0.15, 0],
                color=accent, stroke_width=2)
    g = VGroup(box, ports, core)
    if text:
        t = typography.label(text, size=THEME.sizes.small, color=THEME.text)
        t.next_to(box, DOWN, buff=0.14)
        g.add(t)
    return g


def device(icon: Mobject, text: str | None = None, *, accent: ManimColor | None = None,
           size: float = 0.95) -> VGroup:
    """A device icon in a rounded tile with an optional label."""
    accent = accent or THEME.accent
    tile = RoundedRectangle(
        width=size, height=size, corner_radius=0.14,
        fill_color=THEME.surface, fill_opacity=1.0,
        stroke_color=accent, stroke_width=2.0,
    )
    icon.scale_to_fit_height(size * 0.55).move_to(tile.get_center())
    g = VGroup(tile, icon)
    if text:
        t = typography.label(text, size=THEME.sizes.small, color=THEME.text_secondary)
        t.next_to(tile, DOWN, buff=0.12)
        g.add(t)
    return g


# --- simple programmatic icons (no external assets) ---
def icon_monitor(accent: ManimColor | None = None) -> VGroup:
    accent = accent or THEME.text_secondary
    screen = RoundedRectangle(width=0.9, height=0.6, corner_radius=0.06,
                              stroke_color=accent, stroke_width=2.4, fill_opacity=0)
    stand = Line([0, -0.3, 0], [0, -0.42, 0], color=accent, stroke_width=2.4)
    base = Line([-0.18, -0.42, 0], [0.18, -0.42, 0], color=accent, stroke_width=2.4)
    return VGroup(screen, stand, base)


def icon_cloud(accent: ManimColor | None = None) -> VGroup:
    accent = accent or THEME.text_secondary
    c1 = Circle(radius=0.24, color=accent, stroke_width=2.4, fill_opacity=0)
    c2 = Circle(radius=0.3, color=accent, stroke_width=2.4, fill_opacity=0)
    c3 = Circle(radius=0.2, color=accent, stroke_width=2.4, fill_opacity=0)
    c1.move_to([-0.26, 0, 0])
    c3.move_to([0.28, 0.02, 0])
    return VGroup(c1, c2, c3)


def icon_server(accent: ManimColor | None = None) -> VGroup:
    accent = accent or THEME.text_secondary
    boxes = VGroup()
    for i in range(3):
        b = RoundedRectangle(width=0.8, height=0.22, corner_radius=0.04,
                             stroke_color=accent, stroke_width=2.2, fill_opacity=0)
        boxes.add(b)
    boxes.arrange(DOWN, buff=0.09)
    return boxes


def icon_shield(accent: ManimColor | None = None) -> VGroup:
    accent = accent or THEME.text_secondary
    body = RoundedRectangle(width=0.6, height=0.66, corner_radius=0.16,
                            stroke_color=accent, stroke_width=2.4, fill_opacity=0)
    body.stretch(1.0, 0)
    return VGroup(body)


# --------------------------------------------------------------------------
# links & packets
# --------------------------------------------------------------------------
def link(a: Mobject, b: Mobject, *, accent: ManimColor | None = None,
         dashed: bool = False, stroke_width: float = 2.6,
         buff: float = 0.0) -> Mobject:
    """A connection line between two nodes."""
    return surfaces.connector(a, b, accent=accent, dashed=dashed,
                              arrow=False, buff=buff, stroke_width=stroke_width)


def packet(text: str | None = None, *, accent: ManimColor | None = None,
           width: float = 0.6, height: float = 0.34) -> VGroup:
    """A small envelope-like packet that can travel along a link."""
    accent = accent or THEME.accent
    body = RoundedRectangle(width=width, height=height, corner_radius=0.06,
                            fill_color=accent, fill_opacity=0.22,
                            stroke_color=accent, stroke_width=1.8)
    g = VGroup(body)
    if text:
        t = typography.mono(text, size=THEME.sizes.tiny, color=accent)
        if t.width > width - 0.1:
            t.scale((width - 0.1) / t.width)
        t.move_to(body.get_center())
        g.add(t)
    return g


def packet_path(points: Sequence, *, accent: ManimColor | None = None) -> VGroup:
    """A poly-line route that a packet can be animated along."""
    accent = accent or THEME.accent
    lines = VGroup()
    for i in range(len(points) - 1):
        lines.add(Line(points[i], points[i + 1], color=accent, stroke_width=2.4))
    return lines


def stack(labels: Sequence[str], *, accent: ManimColor | None = None,
          width: float = 2.6, height: float = 0.42, gap: float = 0.06,
          top_label: str | None = None) -> VGroup:
    """A vertical protocol stack (e.g. application/transport/network/link)."""
    accent = accent or THEME.accent
    g = VGroup()
    for lab in labels:
        surf = RoundedRectangle(width=width, height=height, corner_radius=0.06,
                                fill_color=THEME.surface_alt, fill_opacity=1.0,
                                stroke_color=accent, stroke_width=1.4)
        t = typography.label(lab, size=THEME.sizes.small, color=THEME.text)
        if t.width > width - 0.3:
            t.scale((width - 0.3) / t.width)
        t.move_to(surf.get_center())
        g.add(VGroup(surf, t))
    g.arrange(DOWN, buff=gap)
    return g
