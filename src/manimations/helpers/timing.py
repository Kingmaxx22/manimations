"""Timing, easing and reveal helpers shared by every scene.

Manim's own rate functions are good; these wrap the ones we standardise on so a
project cannot accidentally use a jarring easing curve.  Motion should feel
deliberate: things ease in and settle, nothing bounces for decoration.
"""

from __future__ import annotations

from typing import Callable, Iterable, Sequence

from manim import (
    Animation,
    AnimationGroup,
    FadeIn,
    LaggedStart,
    Mobject,
    Succession,
    Wait,
    rate_functions,
)

#: The easing curves Manimations uses.  ``smooth`` for reveals, ``ease_in_out``
#: for anything that travels, ``rush_into`` for exits.
EASE_REVEAL: Callable[[float], float] = rate_functions.ease_out_cubic
EASE_TRAVEL: Callable[[float], float] = rate_functions.ease_in_out_sine
EASE_SETTLE: Callable[[float], float] = rate_functions.ease_out_back
EASE_EMPHASIS: Callable[[float], float] = rate_functions.there_and_back

# Standard animation run time for a reveal.
DEFAULT_RUN_TIME = 0.6


def fade_in_stagger(
    mobjects: Sequence[Mobject],
    *,
    lag: float = 0.14,
    run_time: float = DEFAULT_RUN_TIME,
    shift: float = 0.0,
    direction: "object" = None,
) -> LaggedStart:
    """Reveal a group of mobjects one after another.

    This is the workhorse reveal: it builds a diagram progressively instead of
    dumping the finished picture on screen, which is what makes the visual read
    as an explanation rather than a slide.
    """
    anims = []
    for m in mobjects:
        kwargs = {}
        if shift:
            kwargs["shift"] = (direction or __import__("manim").DOWN) * shift
        anims.append(FadeIn(m, **kwargs))
    return LaggedStart(*anims, lag_ratio=lag / max(run_time, 1e-6), run_time=run_time)


def group(*anims: Animation) -> AnimationGroup:
    """Run animations simultaneously."""
    return AnimationGroup(*anims)


def sequence(*anims: Animation, waits: Sequence[float] | None = None) -> Succession:
    """Run animations back to back with optional gaps."""
    parts: list[Animation] = []
    for i, a in enumerate(anims):
        parts.append(a)
        if waits and i < len(waits):
            parts.append(Wait(waits[i]))
    return Succession(*parts)


def hold(seconds: float) -> Wait:
    """A named pause so scenes read as choreography, not magic numbers."""
    return Wait(seconds)
