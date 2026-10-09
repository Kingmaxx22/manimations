"""Layout helpers: safe areas, centring, grids, and clipping checks.

The QA pass in the pipeline calls :func:`offending_mobjects` on every rendered
scene to catch text that overflows the frame or objects that collide.  Scenes
can also call it themselves during development.
"""

from __future__ import annotations

from typing import Iterable, Sequence

from manim import DOWN, RIGHT, Mobject, Rectangle, VGroup, config

from ..theme import THEME

#: Safe-area margins as a *fraction of the frame*, not fixed scene units.
#: A fixed 0.85-unit margin is 5% of a 16-unit-wide landscape frame but 19% of a
#: 4.5-unit-wide vertical one, which would starve vertical layouts of room.
MARGIN_X_FRACTION = 0.07
MARGIN_Y_FRACTION = 0.07


def margin_x() -> float:
    """Horizontal safe-area inset for the current frame."""
    return config.frame_width * MARGIN_X_FRACTION


def margin_y() -> float:
    """Vertical safe-area inset for the current frame."""
    return config.frame_height * MARGIN_Y_FRACTION


#: The rectangle every scene must keep its content inside.
def safe_area(
    margin_x_override: float | None = None, margin_y_override: float | None = None
) -> Rectangle:
    mx = margin_x_override if margin_x_override is not None else margin_x()
    my = margin_y_override if margin_y_override is not None else margin_y()
    w = config.frame_width - 2 * mx
    h = config.frame_height - 2 * my
    return Rectangle(width=w, height=h)


def safe_width(margin: float | None = None) -> float:
    return config.frame_width - 2 * (margin if margin is not None else margin_x())


def safe_height(margin: float | None = None) -> float:
    return config.frame_height - 2 * (margin if margin is not None else margin_y())


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


def is_vertical() -> bool:
    """True when the frame is taller than it is wide (9:16)."""
    return config.frame_height > config.frame_width


def spread(items: "Sequence[Mobject]", *, gap: float | None = None,
           y: float = 0.0, margin: float | None = None) -> VGroup:
    """Lay mobjects out horizontally, fitted inside the safe area.

    Unlike ``VGroup.arrange`` this never lets the row exceed the frame: it
    arranges first, then scales the assembled group down to fit.  That ordering
    matters — scaling the items individually and arranging afterwards lets the
    gaps push the row back over the limit.

    Returns the group; the caller positions it (e.g. ``.move_to([0, y, 0])``).
    """
    group = VGroup(*items)
    margin = margin if margin is not None else margin_x()
    available = config.frame_width - 2 * margin
    if not items:
        return group
    gap = gap if gap is not None else THEME.spacing.lg
    group.arrange(RIGHT, buff=gap)
    if group.width > available:
        group.scale(available / group.width)
    group.move_to([0, y, 0])
    return group


def stacked(items: "Sequence[Mobject]", *, gap: float | None = None,
            margin: float | None = None) -> VGroup:
    """Lay mobjects out vertically, fitted inside the safe area.

    Arranges first, then scales the assembled group so the gaps cannot push it
    back over the limit.
    """
    group = VGroup(*items)
    margin = margin if margin is not None else margin_y()
    available = config.frame_height - 2 * margin
    if not items:
        return group
    gap = gap if gap is not None else THEME.spacing.md
    group.arrange(DOWN, buff=gap)
    if group.height > available:
        group.scale(available / group.height)
    return group


def pair(left: Mobject, right: Mobject, *, y: float = 0.0, gap: float = 0.4,
         margin: float | None = None) -> VGroup:
    """Place two mobjects at the left and right of the safe area.

    Both are scaled down if the pair cannot fit, so a two-endpoint diagram
    (device <-> server, IPv4 <-> IPv6) survives a vertical frame where the
    horizontal room is much smaller.
    """
    margin = margin if margin is not None else margin_x()
    available = config.frame_width - 2 * margin
    col_w = (available - gap) / 2
    fit_width(left, col_w)
    fit_width(right, col_w)
    left.move_to([-available / 2 + left.width / 2, y, 0])
    right.move_to([available / 2 - right.width / 2, y, 0])
    return VGroup(left, right)


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
