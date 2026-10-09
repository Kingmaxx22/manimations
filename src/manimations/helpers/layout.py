"""Layout helpers: safe areas, centring, grids, and clipping checks.

The QA pass in the pipeline calls :func:`offending_mobjects` on every rendered
scene to catch text that overflows the frame or objects that collide.  Scenes
can also call it themselves during development.
"""

from __future__ import annotations

from typing import Iterable, Sequence

from manim import Mobject, Rectangle, VGroup, config

from ..theme import THEME

#: The rectangle every scene must keep its content inside.
def safe_area(
    margin_x: float | None = None, margin_y: float | None = None
) -> Rectangle:
    sp = THEME.spacing
    w = config.frame_width - 2 * (margin_x if margin_x is not None else sp.margin_x)
    h = config.frame_height - 2 * (margin_y if margin_y is not None else sp.margin_y)
    return Rectangle(width=w, height=h)


def safe_width(margin_x: float | None = None) -> float:
    return safe_area(margin_x=margin_x).width


def safe_height(margin_y: float | None = None) -> float:
    return safe_area(margin_y=margin_y).height


def is_inside_safe_area(mob: Mobject, tol: float = 0.02) -> bool:
    """True when ``mob`` lies fully within the safe area.

    Uses plain coordinate comparison (``Rectangle.contains`` is not a point test
    in Manim CE).
    """
    area = safe_area()
    return bool(
        mob.get_left()[0] >= area.get_left()[0] - tol
        and mob.get_right()[0] <= area.get_right()[0] + tol
        and mob.get_bottom()[1] >= area.get_bottom()[1] - tol
        and mob.get_top()[1] <= area.get_top()[1] + tol
    )


def offending_mobjects(
    mobjects: Iterable[Mobject], tol: float = 0.02
) -> list[Mobject]:
    """Return mobjects that escape the safe area (text clipping / off-screen)."""
    return [m for m in mobjects if m.width > 0 and m.height > 0 and not is_inside_safe_area(m, tol)]


def overlaps(a: Mobject, b: Mobject, tol: float = 0.02) -> bool:
    """Bounding-box overlap test between two mobjects."""
    return bool(
        a.get_right()[0] - tol > b.get_left()[0]
        and b.get_right()[0] - tol > a.get_left()[0]
        and a.get_top()[1] - tol > b.get_bottom()[1]
        and b.get_top()[1] - tol > a.get_bottom()[1]
    )


def collision_pairs(
    mobjects: Sequence[Mobject], tol: float = 0.02
) -> list[tuple[int, int]]:
    """Index pairs of mobjects whose bounding boxes overlap."""
    pairs: list[tuple[int, int]] = []
    for i in range(len(mobjects)):
        for j in range(i + 1, len(mobjects)):
            if overlaps(mobjects[i], mobjects[j], tol):
                pairs.append((i, j))
    return pairs


def fit_width(mob: Mobject, max_width: float) -> Mobject:
    """Scale a mobject down so it fits ``max_width`` (never scales up)."""
    if mob.width > max_width:
        mob.scale(max_width / mob.width)
    return mob


def fit_height(mob: Mobject, max_height: float) -> Mobject:
    if mob.height > max_height:
        mob.scale(max_height / mob.height)
    return mob


def columns(count: int, *, total_width: float, gap: float) -> list[float]:
    """x-centres for ``count`` equal columns spanning ``total_width``."""
    col_w = (total_width - gap * (count - 1)) / count
    start = -total_width / 2 + col_w / 2
    return [start + i * (col_w + gap) for i in range(count)]


def rows(count: int, *, total_height: float, gap: float) -> list[float]:
    """y-centres for ``count`` equal rows spanning ``total_height``."""
    row_h = (total_height - gap * (count - 1)) / count
    start = total_height / 2 - row_h / 2
    return [start - i * (row_h + gap) for i in range(count)]


def two_column_split(
    left: Mobject, right: Mobject, *, gap: float = 0.5, y: float = 0.0
) -> VGroup:
    """Place two blocks side by side, vertically centred, within the safe area."""
    total = safe_width() - 0.2
    col_w = (total - gap) / 2
    fit_width(left, col_w)
    fit_width(right, col_w)
    left.move_to([-total / 2 + left.width / 2, y, 0])
    right.move_to([total / 2 - right.width / 2, y, 0])
    return VGroup(left, right)
