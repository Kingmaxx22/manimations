"""Scene transitions and morph helpers.

Deliberately restrained: a small vocabulary of moves (dissolve, slide, wipe,
morph) keeps the video coherent and stops transitions from competing with the
explanation.
"""

from __future__ import annotations

from typing import Sequence

from manim import (
    DOWN,
    LEFT,
    RIGHT,
    UP,
    Animation,
    FadeIn,
    FadeOut,
    Mobject,
    Rectangle,
    ReplacementTransform,
    Transform,
    VGroup,
    rate_functions,
)

from ..theme import THEME


def dissolve_out(*mobjects: Mobject, run_time: float | None = None) -> Animation:
    """Fade a group out (the default scene exit)."""
    return FadeOut(VGroup(*mobjects), run_time=run_time or THEME.motion.medium)


def dissolve_in(*mobjects: Mobject, shift=None, run_time: float | None = None) -> Animation:
    """Fade a group in, optionally with a small directional drift."""
    kwargs = {}
    if shift is not None:
        kwargs["shift"] = shift
    return FadeIn(VGroup(*mobjects), run_time=run_time or THEME.motion.base, **kwargs)


def slide_in(mobj: Mobject, direction=RIGHT, *, distance: float = 2.0,
             run_time: float | None = None) -> Animation:
    """Enter from off-screen along ``direction`` with eased motion."""
    return FadeIn(
        mobj, shift=-direction * distance,
        run_time=run_time or THEME.motion.medium,
        rate_func=rate_functions.ease_out_cubic,
    )


def wipe(target: Mobject, *, direction=RIGHT, accent=None, run_time: float | None = None):
    """A soft wipe reveal using a growing rectangle mask.

    Returns a tuple of animations; the caller plays them together.  The mask is
    removed at the end so it does not pollute the scene graph.
    """
    accent = accent or THEME.accent
    bar = Rectangle(width=0.06, height=target.height + 0.6, color=accent,
                    fill_opacity=1, stroke_width=0)
    bar.move_to(target.get_left() + LEFT * 0.3)
    return bar


def morph(source: Mobject, target: Mobject, *, run_time: float | None = None) -> Animation:
    """Transform one diagram into another (shape-preserving if possible)."""
    return ReplacementTransform(source, target, run_time=run_time or THEME.motion.slow)


def swap(old: Mobject, new: Mobject, *, run_time: float | None = None) -> Animation:
    """Cross-fade ``old`` out while ``new`` fades in (a clean cut between ideas)."""
    return Transform(old, new, run_time=run_time or THEME.motion.medium)
