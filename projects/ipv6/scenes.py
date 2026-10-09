"""What Is IPv6, and Why Is Adoption So Slow? — scene definitions.

Each class is a real visual explanation, not a narration transcript on screen.
The narration carries the detail; these scenes build diagrams, move packets and
compare representations so the idea lands visually.

Preview::

    manimations preview ipv6

Render one scene at final quality::

    uv run manim -qh -r 1920,1080 --fps 30 projects/ipv6/scenes.py SceneBitWidth
"""

from __future__ import annotations

from manim import (
    DOWN,
    LEFT,
    RIGHT,
    UP,
    Create,
    FadeIn,
    FadeOut,
    Indicate,
    LaggedStart,
    Transform,
    VGroup,
    Write,
)

from manimations import ExplainerScene
from manimations.components import data, network, surfaces, typography
from manimations.helpers import layout, timing

#: Recurring concept colours, kept identical across every scene.
IPV4 = "amber"
IPV6 = "violet"
ADDRESS = "cyan"
NETWORK = "green"
LEGACY = "rose"
COEXIST = "blue"


# ==========================================================================
# 00 — cold open (title card, no narration)
# ==========================================================================
class SceneColdOpen(ExplainerScene):
    """Title card shown before the first narrated scene."""

    def construct(self) -> None:
        t = self.theme
        card = typography.title_card(
            "Internet Infrastructure",
            "What Is IPv6?",
            accent=t.cyan,
            subtitle="And why is adoption so slow?",
            max_width=layout.safe_width(),
        )
        card.move_to([0, 0.15, 0])
        self.register_content(card)

        self.play(FadeIn(card, shift=DOWN * 0.35), run_time=t.motion.medium)
        self.wait(0.4)
        # a small flourish: the two address families resolve side by side
        row = VGroup(
            surfaces.badge("IPv4 · 32-bit", accent=t.amber),
            surfaces.badge("IPv6 · 128-bit", accent=t.violet),
        )
        layout.spread(list(row), gap=0.5)
        row.next_to(card, DOWN, buff=0.9)
        layout.fit_width(row, layout.safe_width())
        self.register_content(row)
        self.play(timing.fade_in_stagger(list(row), lag=0.4), run_time=0.8)
        self.settle(1.2)


# ==========================================================================
# 01 — IPv4 address scarcity
# ==========================================================================
class SceneScarcity(ExplainerScene):
    """The problem of IPv4 address scarcity."""

    def construct(self) -> None:
        t = self.theme
        self.add_header("Address exhaustion", accent=t.amber, index="01")

        # counter climbs to 2^32
        counter = data.counter(0, label="IPv4 addresses", accent=t.amber,
                               size=t.sizes.stat)
        counter.move_to([0, 0.55, 0])
        layout.fit_width(counter, layout.safe_width())
        self.register_content(counter)
        self.play(FadeIn(counter))
        self.play(counter.tracker.animate.set_value(4_294_967_296), run_time=2.2)
        self.wait(0.3)

        # the pool fills up
        meter_w = min(9.0, layout.safe_width())
        meter = data.meter(0.0, width=meter_w, accent=t.amber,
                           label="allocated address pool")
        meter.move_to([0, -1.35, 0])
        self.register_content(meter)
        self.play(FadeIn(meter[0]), FadeIn(meter[2]))
        # grow the fill by transforming a narrow bar to a full one
        full = data.meter(1.0, width=meter_w, accent=t.amber)
        full[0].move_to(meter[0].get_center())
        full[1].move_to(meter[0].get_center())
        self.play(Transform(meter[1], full[1]), run_time=1.4)

        stamp = surfaces.badge("all allocated", accent=t.rose)
        stamp.next_to(meter, DOWN, buff=0.5)
        layout.fit_width(stamp, layout.safe_width())
        self.register_content(stamp)
        self.play(FadeIn(stamp, scale=1.2), run_time=0.5)

        note = typography.body(
            "A ceiling set in the 1970s — before the devices that would need it.",
            size=t.sizes.body,
        )
        note.move_to([0, -2.75, 0])
        layout.fit_width(note, layout.safe_width())
        self.register_content(note)
        self.play(FadeIn(note))
        self.settle()


# ==========================================================================
# 02 — what an IP address represents
# ==========================================================================
class SceneAddressMeaning(ExplainerScene):
    """An IP address is a location, not a name."""

    def construct(self) -> None:
        t = self.theme
        self.add_header("An address is a location", accent=t.cyan, index="02")

        # topology: host -> router -> server, laid out inside the safe area so it
        # also fits a narrow vertical frame
        host = network.device(network.icon_monitor(t.cyan), "device", accent=t.cyan)
        router = network.router("router", accent=t.violet)
        server = network.device(network.icon_server(t.green), "destination", accent=t.green)
        layout.spread([host, router, server], gap=0.7, y=0.2)
        hops = VGroup(
            network.link(host[0], router[0], accent=t.violet),
            network.link(router[0], server[0], accent=t.violet),
        )
        self.register_content(host, router, server, hops)
        self.play(timing.fade_in_stagger([host, router, server], lag=0.18),
                  Create(hops), run_time=1.2)

        # a packet travels hop by hop
        pkt = network.packet("→", accent=t.cyan).move_to(host[0].get_center())
        self.play(FadeIn(pkt, scale=1.4), run_time=0.3)
        self.play(pkt.animate.move_to(router[0].get_center()), run_time=0.8)
        self.play(pkt.animate.move_to(server[0].get_center()), run_time=0.8)

        caption = typography.highlight_phrase(
            "An address tells the network where to send the packet — not who you are.",
            "where to send the packet", color=t.cyan, size=t.sizes.body,
        )
        caption.move_to([0, -2.0, 0])
        layout.fit_width(caption, layout.safe_width() - 0.4)
        self.register_content(caption)
        self.play(FadeOut(pkt), FadeIn(caption))

        # relocate the device: the address changes
        addr = surfaces.badge("address changes", accent=t.amber)
        addr.next_to(host, UP, buff=0.4)
        layout.fit_width(addr, layout.safe_width() - 0.4)
        # Keep the badge inside the frame even when the host sits at the edge of a
        # narrow vertical frame.
        half = layout.safe_width() / 2 - addr.width / 2
        addr.shift(RIGHT * (max(-half, min(half, addr.get_center()[0])) - addr.get_center()[0]))
        self.register_content(addr)
        self.play(FadeIn(addr), Indicate(host[0], color=t.amber), run_time=0.8)
        self.play(host.animate.shift(DOWN * 0.9), run_time=0.9)
        self.settle()


# ==========================================================================
# 03 — 32-bit vs 128-bit
# ==========================================================================
class SceneBitWidth(ExplainerScene):
    """The difference between 32-bit IPv4 and 128-bit IPv6 addresses."""

    def construct(self) -> None:
        t = self.theme
        self.add_header("32 bits vs 128 bits", accent=t.violet, index="03")

        # --- IPv4 side -------------------------------------------------
        v4_label = surfaces.badge("IPv4 · 32-bit", accent=t.amber)
        v4_block = network.address_block(
            ["192", "168", "1", "1"], accent=t.amber,
            cell_width=1.0, cell_height=0.62, mono_size=t.sizes.mono_small,
        )
        v4_grid = network.bit_grid(4, 8, cell=0.14, gap=0.04, accent=t.amber)
        v4 = VGroup(v4_label, v4_block, v4_grid).arrange(DOWN, buff=0.34)

        # --- IPv6 side -------------------------------------------------
        v6_label = surfaces.badge("IPv6 · 128-bit", accent=t.violet)
        v6_block = network.address_block(
            ["2001", "db8", "1", "0", "0", "0", "0", "1"],
            dot=False, group_size=1, accent=t.violet,
            cell_width=0.6, cell_height=0.56, mono_size=t.sizes.mono_tiny,
            buff=0.08, group_buff=0.2,
        )
        v6_grid = network.bit_grid(8, 16, cell=0.075, gap=0.03, accent=t.violet)
        v6 = VGroup(v6_label, v6_block, v6_grid).arrange(DOWN, buff=0.34)

        # Fit both columns inside their half of the safe area so nothing clips.
        half = (layout.safe_width() - 0.7) / 2
        for col in (v4, v6):
            layout.fit_width(col, half)
        v4.move_to([-half / 2 - 0.35, 0.1, 0])
        v6.move_to([half / 2 + 0.35, 0.1, 0])

        self.register_content(v4, v6)
        self.play(FadeIn(v4_label), FadeIn(v6_label))
        self.play(
            LaggedStart(*[FadeIn(c) for c in v4_block], lag_ratio=0.12),
            LaggedStart(*[FadeIn(c) for c in v6_block], lag_ratio=0.05),
            run_time=1.4,
        )
        self.play(
            LaggedStart(*[FadeIn(s) for s in v4_grid], lag_ratio=0.01),
            LaggedStart(*[FadeIn(s) for s in v6_grid], lag_ratio=0.002),
            run_time=1.4,
        )

        note = typography.highlight_phrase(
            "Four times the width — an almost unimaginably larger space.",
            "unimaginably larger space", color=t.violet, size=t.sizes.body,
        )
        note.move_to([0, -2.65, 0])
        layout.fit_width(note, layout.safe_width() - 0.4)
        self.register_content(note)
        self.play(FadeIn(note))
        self.settle()


# ==========================================================================
# 04 — prefixes and connectivity
# ==========================================================================
class ScenePrefixAndConnectivity(ExplainerScene):
    """How IPv6 addresses and network connectivity work."""

    def construct(self) -> None:
        t = self.theme
        self.add_header("Prefix and connectivity", accent=t.green, index="04")

        hextets = ["2001", "db8", "1", "0", "0", "0", "0", "1"]
        vertical = layout.is_vertical()

        if vertical:
            # 8 hextets will not fit one 9:16 row; split into two rows of four,
            # which also makes the /64 boundary read naturally.
            top = network.address_block(
                hextets[:4], dot=False, accent=t.violet,
                cell_width=0.72, cell_height=0.6, mono_size=t.sizes.mono_small,
                buff=0.12,
            )
            bottom = network.address_block(
                hextets[4:], dot=False, accent=t.violet,
                cell_width=0.72, cell_height=0.6, mono_size=t.sizes.mono_small,
                buff=0.12,
            )
            for r in (top, bottom):
                layout.fit_width(r, layout.safe_width())
            block = VGroup(top, bottom).arrange(DOWN, buff=0.24)
            block.move_to([0, 1.75, 0])
            self.register_content(block)
            self.play(LaggedStart(*[FadeIn(c) for c in block], lag_ratio=0.08))

            prefix_lbl = typography.label("/64 network prefix", color=t.green, weight="BOLD")
            prefix_lbl.next_to(top, UP, buff=0.2)
            iface_lbl = typography.label("interface identifier", color=t.cyan, weight="BOLD")
            iface_lbl.next_to(bottom, DOWN, buff=0.2)
            layout.fit_width(prefix_lbl, layout.safe_width())
            layout.fit_width(iface_lbl, layout.safe_width())
            self.register_content(prefix_lbl, iface_lbl)
            self.play(FadeIn(prefix_lbl), FadeIn(iface_lbl), run_time=0.8)

            net_cells = VGroup(*top)
            self.play(
                LaggedStart(*[Indicate(c, color=t.green) for c in net_cells], lag_ratio=0.15),
                run_time=1.2,
            )
            stat_y, note_y, router_y = -0.55, -1.5, -2.7
        else:
            block = network.address_block(
                hextets, dot=False, group_size=1, accent=t.violet,
                cell_width=0.8, cell_height=0.66, mono_size=t.sizes.mono_small,
                buff=0.12, group_buff=0.34,
            )
            layout.fit_width(block, layout.safe_width())
            block.move_to([0, 1.7, 0])
            self.register_content(block)
            self.play(LaggedStart(*[FadeIn(c) for c in block], lag_ratio=0.08))

            # split marker at bit 64: first four hextets are the network
            split = surfaces.divider(0.06, accent=t.green)
            split.rotate(3.14159 / 2)
            split.scale(6.0)
            x_split = (block[6].get_right()[0] + block[8].get_left()[0]) / 2
            split.move_to([x_split, 1.7, 0])

            prefix_lbl = typography.label("/64 network prefix", color=t.green, weight="BOLD")
            prefix_lbl.move_to([block[0].get_left()[0] + 2.6, 2.55, 0])
            iface_lbl = typography.label("interface identifier", color=t.cyan, weight="BOLD")
            iface_lbl.move_to([block[-1].get_right()[0] - 2.5, 2.55, 0])

            self.register_content(split, prefix_lbl, iface_lbl)
            self.play(Create(split), FadeIn(prefix_lbl), FadeIn(iface_lbl), run_time=0.8)

            # highlight the network half
            net_cells = VGroup(*[block[i] for i in range(0, 7, 2)])
            self.play(
                LaggedStart(*[Indicate(c, color=t.green) for c in net_cells], lag_ratio=0.15),
                run_time=1.2,
            )
            stat_y, note_y, router_y = -0.5, None, -2.6

        # a /64 holds more than the whole IPv4 internet
        stat = data.stat_block("2⁶⁴", "addresses in one /64 prefix", accent=t.green,
                               size=t.sizes.stat_small)
        stat.move_to([0, stat_y, 0])
        layout.fit_width(stat, layout.safe_width())
        cmp_note = typography.body(
            "— more than the entire IPv4 internet, in a single home allocation.",
            size=t.sizes.small, color=t.text_secondary,
        )
        layout.fit_width(cmp_note, layout.safe_width())
        cmp_note.next_to(stat, DOWN, buff=0.35)
        self.register_content(stat, cmp_note)
        self.play(FadeIn(stat), FadeIn(cmp_note), run_time=0.8)

        # router hands out addresses inside the prefix
        router = network.router("home router", accent=t.violet)
        router.move_to([0, router_y, 0])
        self.register_content(router)
        self.play(FadeIn(router, shift=UP * 0.3), run_time=0.6)
        self.play(Indicate(router[0], color=t.violet), run_time=0.6)
        self.settle()


# ==========================================================================
# 05 — why adoption is gradual
# ==========================================================================
class SceneSlowAdoption(ExplainerScene):
    """Legacy infrastructure, compatibility, migration cost, operational complexity."""

    def construct(self) -> None:
        t = self.theme
        self.add_header("Why the transition is slow", accent=t.rose, index="05")

        factors = [
            ("Legacy kit", "Hardware and software\nthat only speak IPv4", t.rose),
            ("Compatibility", "Two stacks to test\nand keep working", t.amber),
            ("Migration cost", "Real spend, no\nvisible daily gain", t.violet),
            ("Operations", "New tooling,\ntraining and runbooks", t.blue),
        ]
        cards = VGroup(*[
            surfaces.card(title, body, accent=accent, width=2.9,
                          title_size=t.sizes.subheading, body_size=t.sizes.small,
                          min_height=2.2)
            for title, body, accent in factors
        ])
        if layout.is_vertical():
            # Four side-by-side cards cannot fit a 9:16 frame; use a 2x2 grid.
            cw = (layout.safe_width() - 0.3) / 2
            for c in cards:
                layout.fit_width(c, cw)
            xs = layout.columns(2, total_width=layout.safe_width(), gap=0.3)
            ys = [0.75, -1.35]
            for i, c in enumerate(cards):
                c.move_to([xs[i % 2], ys[i // 2], 0])
        else:
            xs = layout.columns(4, total_width=layout.safe_width() - 0.4, gap=0.3)
            for c, x in zip(cards, xs):
                c.move_to([x, 0.15, 0])
        self.register_content(cards)
        self.play(timing.fade_in_stagger(list(cards), lag=0.35, run_time=1.8))
        self.wait(0.2)

        # timeline: IPv6 is not new
        tl = data.timeline(
            [("1998", "IPv6 standardised"),
             ("2011", "IANA frees its last IPv4 blocks"),
             ("today", "still migrating")],
            accent=t.rose, label_size=t.sizes.small,
        )
        tl.move_to([0, -2.45 if not layout.is_vertical() else -2.75, 0])
        layout.fit_width(tl, layout.safe_width())
        self.register_content(tl)
        self.play(FadeIn(tl), run_time=0.8)

        note = typography.highlight_phrase(
            "The internet cannot pause for the upgrade.",
            "cannot pause", color=t.rose, size=t.sizes.body,
        )
        note.move_to([0, -3.15 if not layout.is_vertical() else -3.35, 0])
        layout.fit_width(note, layout.safe_width() - 0.3)
        self.register_content(note)
        self.play(FadeIn(note))
        self.settle()


# ==========================================================================
# 06 — dual stack
# ==========================================================================
class SceneDualStack(ExplainerScene):
    """How dual-stack networking lets IPv4 and IPv6 coexist."""

    def construct(self) -> None:
        t = self.theme
        self.add_header("Dual stack: both at once", accent=t.blue, index="06")

        # one device, two addresses — placed at the safe-area edges so the
        # two-endpoint diagram also fits a narrow vertical frame
        client = network.device(network.icon_monitor(t.cyan), "your device", accent=t.cyan)
        server = network.device(network.icon_cloud(t.green), "the internet", accent=t.green)
        layout.pair(client, server, y=0.3, gap=0.5)

        addrs = VGroup(
            surfaces.badge("IPv4 203.0.113.7", accent=t.amber),
            surfaces.badge("IPv6 2001:db8::1", accent=t.violet),
        )
        layout.stacked(list(addrs), gap=0.22)
        layout.fit_width(addrs, layout.safe_width())
        # Anchor the address stack to the client vertically but keep it centred
        # horizontally, so it never hangs off the edge of a narrow frame.
        addrs.move_to([0, client.get_top()[1] + 0.45 + addrs.height / 2, 0])
        self.register_content(client, server, addrs)
        self.play(FadeIn(client), FadeIn(server), run_time=0.7)
        self.play(timing.fade_in_stagger(list(addrs), lag=0.3))

        # two routes
        v6_route = network.link(client[0], server[0], accent=t.violet, buff=0.35)
        v6_route.shift(UP * 0.35)
        v4_route = network.link(client[0], server[0], accent=t.amber, buff=0.35)
        v4_route.shift(DOWN * 0.5)
        v6_tag = surfaces.badge("preferred", accent=t.violet).scale(0.85)
        v6_tag.move_to([0, 1.25, 0])
        v4_tag = surfaces.badge("fallback", accent=t.amber).scale(0.85)
        v4_tag.move_to([0, -0.95, 0])

        self.register_content(v6_route, v4_route, v6_tag, v4_tag)
        self.play(Create(v6_route), FadeIn(v6_tag), run_time=0.7)
        self.play(Create(v4_route), FadeIn(v4_tag), run_time=0.7)

        # packet prefers IPv6
        pkt = network.packet("→", accent=t.violet).move_to(client[0].get_center() + UP * 0.35)
        self.play(FadeIn(pkt, scale=1.3), run_time=0.25)
        self.play(pkt.animate.move_to(server[0].get_center() + UP * 0.35), run_time=1.0)
        self.play(FadeOut(pkt), run_time=0.3)

        note = typography.highlight_phrase(
            "Where IPv6 is missing, traffic quietly falls back to IPv4.",
            "falls back", color=t.amber, size=t.sizes.body,
        )
        note.move_to([0, -2.5, 0])
        layout.fit_width(note, layout.safe_width() - 0.4)
        self.register_content(note)
        self.play(FadeIn(note))
        self.play(Indicate(v4_route, color=t.amber), run_time=0.8)
        self.settle()


# ==========================================================================
# 07 — conclusion
# ==========================================================================
class SceneConclusion(ExplainerScene):
    """A concise conclusion."""

    def construct(self) -> None:
        t = self.theme
        self.add_header("The takeaway", accent=t.cyan, index="07")

        lines = [
            ("IPv6 is not faster or more secure by itself.", t.text_secondary, None),
            ("It solves one problem: address exhaustion.", t.text_secondary, "address exhaustion"),
            ("The internet cannot pause — so the move is slow.", t.text, "cannot pause"),
        ]
        rows = VGroup()
        for text, base, emph in lines:
            if emph:
                t_mob = typography.highlight_phrase(
                    text, emph, color=t.cyan, base_color=base, size=t.sizes.subheading)
            else:
                t_mob = typography.body(text, size=t.sizes.subheading, color=base)
            rows.add(t_mob)
        rows.arrange(DOWN, buff=0.55, aligned_edge=LEFT)
        rows.move_to([0, 0.35, 0])
        layout.fit_width(rows, layout.safe_width() - 0.6)
        self.register_content(rows)
        self.play(timing.fade_in_stagger(list(rows), lag=0.6, run_time=2.0))
        self.wait(0.3)

        closing = VGroup(
            surfaces.badge("IPv4 · exhausted", accent=t.amber),
            surfaces.badge("IPv6 · the long migration", accent=t.violet),
            surfaces.badge("dual stack · today", accent=t.blue),
        )
        if layout.is_vertical():
            layout.stacked(list(closing), gap=0.3)
            closing.move_to([0, -2.6, 0])
        else:
            closing.arrange(RIGHT, buff=0.45)
            closing.move_to([0, -2.3, 0])
        layout.fit_width(closing, layout.safe_width() - 0.6)
        self.register_content(closing)
        self.play(timing.fade_in_stagger(list(closing), lag=0.35))
        self.settle(1.3)
