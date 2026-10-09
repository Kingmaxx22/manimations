"""Smoke test for the component library.

Renders a single scene that exercises every component family.  Run it with the
CLI (``manimations demo``) or directly::

    uv run manim -ql src/manimations/demo.py ComponentDemo

It is also used by the test suite as a fast end-to-end render check.
"""

from __future__ import annotations

from manim import DOWN, LEFT, RIGHT, UP, Create, FadeIn, FadeOut, Indicate, VGroup

from manimations import ExplainerScene
from manimations.components import data, network, surfaces, typography
from manimations.helpers import timing


class ComponentDemo(ExplainerScene):
    """Exercises typography, surfaces, network and data components."""

    def construct(self) -> None:
        t = self.theme

        # --- typography -------------------------------------------------
        head = typography.scene_header("Component Library", accent=t.cyan, index="00")
        head.move_to([0, t.spacing.header_y, 0])
        self.play(FadeIn(head, shift=DOWN * 0.2))

        kw = typography.keyword("Manimations", color=t.cyan)
        sub = typography.body("A reusable 2D explainer system", size=t.sizes.subheading)
        title = VGroup(kw, sub).arrange(DOWN, buff=0.3)
        title.move_to([0, 1.4, 0])
        self.register_content(title)
        self.play(FadeIn(title))

        # --- surfaces / cards ------------------------------------------
        cards = VGroup(
            surfaces.card("Cards", "grouped ideas", accent=t.cyan, width=3.0),
            surfaces.card("Callouts", "annotate a target", accent=t.amber, width=3.0),
            surfaces.card("Badges", "small pills", accent=t.green, width=3.0),
        ).arrange(RIGHT, buff=0.4)
        cards.move_to([0, 0.0, 0])
        self.register_content(cards)
        self.play(timing.fade_in_stagger(list(cards), lag=0.12))

        # --- network ----------------------------------------------------
        r = network.router("Router", accent=t.violet)
        c1 = network.node("Host A", accent=t.cyan, radius=0.34)
        c2 = network.node("Host B", accent=t.green, radius=0.34)
        c1.move_to([-4.2, -1.6, 0])
        r.move_to([0, -1.6, 0])
        c2.move_to([4.2, -1.6, 0])
        links = VGroup(network.link(c1[0], r[0], accent=t.violet),
                       network.link(r[0], c2[0], accent=t.violet))
        pkt = network.packet("6", accent=t.cyan).move_to(c1[0].get_center())
        self.register_content(c1, r, c2)
        self.play(FadeIn(c1), FadeIn(r), FadeIn(c2), Create(links), run_time=0.8)
        self.play(pkt.animate.move_to(c2[0].get_center()), run_time=1.0)
        self.play(FadeOut(pkt))

        # --- data -------------------------------------------------------
        cnt = data.counter(0, label="addresses", accent=t.amber, size=t.sizes.stat_small)
        cnt.move_to([0, -1.9, 0])
        self.register_content(cnt)
        self.play(FadeIn(cnt))
        self.play(cnt.tracker.animate.set_value(4294967296), run_time=1.6)
        self.wait(0.4)
        self.play(FadeOut(VGroup(title, cards, c1, r, c2, links, cnt)))

        # --- stat + meter ----------------------------------------------
        sb = data.stat_block("128-bit", "IPv6 address space", accent=t.cyan)
        sb.move_to([-3.0, 0.6, 0])
        m = data.meter(0.34, width=4.0, accent=t.green, label="IPv6 adoption (illustrative)")
        m.move_to([2.6, 0.6, 0])
        self.register_content(sb, m)
        self.play(FadeIn(sb), FadeIn(m))
        self.play(Indicate(m[1], color=t.green), run_time=0.8)
        self.settle(0.5)
