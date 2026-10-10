"""Base scene class that enforces the design system on every render.

Topic scenes subclass :class:`ExplainerScene`.  It applies the theme, draws the
optional header/footer chrome, tracks content mobjects for the QA pass, keeps the
scene's runtime in sync with its declared (narration) duration, and provides
small conveniences so scene code stays declarative.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
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
    Scene,
    VGroup,
    config,
)

from .components import typography
from .helpers import layout
from .theme import THEME, Theme, apply_theme

#: Environment variable the render pipeline sets so a scene knows its declared
#: duration.  Keeping this out-of-band means scene files need no project import.
SPEC_ENV = "MANIMATIONS_SCENE_SPEC"

#: Environment variable naming a file the scene should write its overlap report
#: to.  Pixel QA cannot detect two mobjects drawn on top of each other — they sit
#: inside the safe area and still read as "content" — so the scene itself reports
#: its collisions and the QA pass reads the sidecar.
OVERLAP_ENV = "MANIMATIONS_OVERLAP_REPORT"


@dataclass
class SceneBrief:
    """The bit of the scene spec a scene needs at runtime."""

    id: str = ""
    duration: float = 0.0
    accent: str = "cyan"


def _spec_from_env() -> SceneBrief | None:
    raw = os.environ.get(SPEC_ENV)
    if not raw:
        return None
    try:
        data = json.loads(raw)
        return SceneBrief(
            id=str(data.get("id", "")),
            duration=float(data.get("duration", 0.0)),
            accent=str(data.get("accent", "cyan")),
        )
    except (json.JSONDecodeError, TypeError, ValueError):
        return None


class ExplainerScene(Scene):
    """Base class for all Manimations scenes.

    Attributes
    ----------
    spec:
        A :class:`SceneBrief` with the scene's declared duration, injected by the
        render pipeline via the ``MANIMATIONS_SCENE_SPEC`` environment variable.
        ``None`` when a scene is run directly through the Manim CLI, in which
        case the scene simply runs as authored.
    """

    spec: SceneBrief | None = None

    def __init_subclass__(cls, **kwargs):
        """Wrap each subclass's ``construct`` so it always ends on time.

        Padding to the declared duration must not depend on the author
        remembering to call ``settle()``, so we wrap ``construct`` here: run the
        scene, then hold the final frame until the clock reaches the scene's
        declared (narration) duration.
        """
        super().__init_subclass__(**kwargs)
        user_construct = cls.__dict__.get("construct")
        if user_construct is None or getattr(user_construct, "_manimations_wrapped", False):
            return

        def construct(self, _user=user_construct):  # type: ignore[override]
            _user(self)
            self._pad_to_target()
            self._write_overlap_report()

        construct._manimations_wrapped = True  # type: ignore[attr-defined]
        cls.construct = construct

    def __init__(self, *args, **kwargs):  # noqa: D401
        # Apply the theme BEFORE Scene.__init__ so the camera picks up the
        # background colour at construction time (it reads config.background_color
        # once, when the camera is created).
        apply_theme()
        super().__init__(*args, **kwargs)
        self.theme: Theme = THEME
        # Belt and braces: some Manim versions build the camera lazily.
        if hasattr(self, "camera"):
            self.camera.background_color = THEME.bg
        #: Content mobjects registered for safe-area QA.
        self._content: list[Mobject] = []
        self._header: VGroup | None = None
        self._footer: VGroup | None = None
        #: Runtime bookkeeping for narration sync.
        self._elapsed: float = 0.0
        self._spec = self.spec or _spec_from_env()

    @property
    def target_duration(self) -> float:
        """Declared duration for this scene (0 when unknown)."""
        return self._spec.duration if self._spec else 0.0

    # ------------------------------------------------------------------
    # runtime tracking (keeps animation time aligned with narration)
    # ------------------------------------------------------------------
    def play(self, *args, **kwargs):  # type: ignore[override]
        """Run animations and accumulate their runtime.

        This is the single source of truth for elapsed time: Manim's
        ``Scene.wait`` is implemented on top of ``play`` (it plays a ``Wait``),
        so waiting is counted here too and must not be counted separately.
        """
        run_time = kwargs.get("run_time")
        if run_time is None and args:
            run_time = max(
                (getattr(a, "run_time", 1.0) for a in args if isinstance(a, Animation)),
                default=1.0,
            )
        result = super().play(*args, **kwargs)
        self._elapsed += float(run_time or 1.0)
        return result

    # ------------------------------------------------------------------
    # content registration / QA
    # ------------------------------------------------------------------
    def register_content(self, *mobjects: Mobject) -> Mobject:
        """Track mobjects so the pipeline can check them for clipping."""
        for m in mobjects:
            self._content.append(m)
        return mobjects[0] if len(mobjects) == 1 else VGroup(*mobjects)

    def content_mobjects(self) -> list[Mobject]:
        """Everything that must fit inside the safe area."""
        extra = [m for m in (self._header, self._footer) if m is not None]
        return self._content + extra

    def qa_report(self) -> dict:
        """Off-screen / collision summary for this scene (used by the pipeline)."""
        offending = layout.offending_mobjects(self._content)
        pairs = layout.collision_pairs(self._content, tol=-0.05)
        return {
            "offending": [type(m).__name__ for m in offending],
            "collisions": pairs,
            "n_content": len(self._content),
        }

    def _write_overlap_report(self) -> None:
        """Persist :meth:`qa_report` for the pipeline, when asked to.

        Overlapping text/graphics is invisible to the frame-level QA (both
        mobjects are inside the safe area and both count as "content"), so the
        scene is the only place that can detect it.  Silent when the env var is
        unset, i.e. when a scene is run directly through the Manim CLI.
        """
        target = os.environ.get(OVERLAP_ENV)
        if not target:
            return
        try:
            report = self.qa_report()
            path = Path(target)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(report), encoding="utf-8")
        except Exception as exc:  # never fail a render over diagnostics
            print(f"warning: could not write overlap report: {exc}")

    # ------------------------------------------------------------------
    # chrome
    # ------------------------------------------------------------------
    def add_header(self, title: str, *, accent=None, index: str | None = None) -> VGroup:
        """Draw the persistent scene header: accent bar + section title.

        The header is added to the scene *before* it animates, so it is already
        visible in the scene's first frame.  A plain ``FadeIn`` starts from zero
        opacity, which renders the frame completely blank — and because the
        header is the first thing every scene draws, that put a pure-background
        frame at the head of *every* scene in the assembled video (measured:
        ~0.14s of black at each scene boundary, since a fade-out-cubic easing is
        still near-transparent for the first ~15% of its run).  The same applies
        to ``GrowFromEdge``, which collapses a mobject to a point at t=0.

        Only a small settle-in slide is animated, so the frame always carries the
        header.  Text that never disappears also reads as chrome rather than as
        one more element arriving.
        """
        accent = accent or self.theme.accent
        header = typography.scene_header(title, accent=accent, index=index)
        max_w = layout.safe_width()
        # Safety net: a long title must never run off the frame.
        if header.width > max_w:
            header.scale(max_w / header.width)
        left = -max_w / 2
        header.move_to([left + header.width / 2, self.theme.spacing.header_y, 0])
        self._header = header
        # Add at a slightly raised position, then settle down into place: the
        # motion reads the same as the old fade-in but never blanks the frame.
        header.shift(UP * 0.18)
        self.add(header)
        self.play(header.animate.shift(DOWN * 0.18), run_time=self.theme.motion.base)
        return header

    def add_footer(self, text: str, *, accent=None) -> VGroup:
        """Draw the persistent footer caption (chapter label / source note)."""
        accent = accent or self.theme.text_muted
        footer = typography.footer_note(text, color=accent)
        footer.to_edge(DOWN, buff=max(0.15, layout.margin_y() - 0.1))
        self._footer = footer
        self.play(FadeIn(footer), run_time=self.theme.motion.quick)
        return footer

    # ------------------------------------------------------------------
    # transitions
    # ------------------------------------------------------------------
    def clear_content(self, run_time: float | None = None) -> None:
        """Fade out everything registered as content and reset the tracker."""
        if not self._content:
            return
        self.play(
            FadeOut(VGroup(*self._content)),
            run_time=run_time if run_time is not None else self.theme.motion.medium,
        )
        self._content.clear()

    def _pad_to_target(self, minimum_hold: float | None = None) -> None:
        """Hold the final frame until the scene reaches its declared duration."""
        target = self.target_duration
        if target <= 0:
            return
        hold = minimum_hold if minimum_hold is not None else self.theme.motion.breath
        pad = target - self._elapsed
        if pad > 0.02:
            self.wait(pad)
        elif hold > 0:
            self.wait(hold)

    def settle(self, seconds: float | None = None) -> None:
        """Optional mid-scene hold; the final padding is applied automatically.

        Kept for authors who want an explicit beat at the end of a scene.  The
        base class already pads every scene to its declared duration, so this is
        only needed for an extra pause beyond that.
        """
        self.wait(seconds if seconds is not None else self.theme.motion.breath)

    # ------------------------------------------------------------------
    # authoring guard rails
    # ------------------------------------------------------------------
    def warn_if_outside_safe_area(self) -> list[str]:
        bad = layout.offending_mobjects(self.content_mobjects())
        names = [type(m).__name__ for m in bad]
        if names:
            self.logger.warning("content outside safe area: %s", names)
        return names
