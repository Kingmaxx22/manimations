"""gdu — vertical 9:16 short for Reels / Shorts / TikTok.

Five scenes, built from the shared component library so the palette, type scale
and motion match the rest of the channel.  Everything is positioned from the
safe area (never absolute x), because a 9:16 frame is only ~4.5 scene units wide.

Facts on screen come from the gdu README (dundee/gdu): ``d`` deletes, arrow keys
navigate, and the benchmark is a 90 GB tree in ~4.7s cold / ~0.5s warm.  The
video therefore claims "seconds", not "two seconds".
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
    GrowFromCenter,
    Indicate,
    Rectangle,
    RoundedRectangle,
    Transform,
    VGroup,
    Write,
)

from manimations import ExplainerScene
from manimations.components import data, surfaces, typography
from manimations.helpers import layout, timing
from manimations.theme import THEME


# --------------------------------------------------------------------------
# small local building blocks (kept here, not in the framework, because they are
# specific to this explainer's terminal aesthetic)
# --------------------------------------------------------------------------
def _window_chrome(width: float, accent, title: str) -> VGroup:
    """A fake window title bar with traffic-light dots."""
    bar = RoundedRectangle(
        width=width, height=0.46, corner_radius=0.1,
        fill_color=accent, fill_opacity=0.12,
        stroke_color=accent, stroke_width=1.4,
    )
    dots = VGroup()
    for i, c in enumerate((accent, accent, accent)):
        dot = RoundedRectangle(
            width=0.11, height=0.11, corner_radius=0.055,
            fill_color=c, fill_opacity=0.85 - i * 0.2, stroke_width=0,
        )
        dots.add(dot)
    dots.arrange(RIGHT, buff=0.09)
    dots.move_to(bar.get_center())
    dots.align_to(bar, LEFT).shift(RIGHT * 0.22)
    label = typography.label(title, size=19, color=accent)
    label.move_to(bar.get_center())
    return VGroup(bar, dots, label)


def _progress_bar(width: float, fraction: float, accent) -> VGroup:
    """A track with a filled portion; the fill can be animated by width."""
    track = RoundedRectangle(
        width=width, height=0.2, corner_radius=0.1,
        fill_color=accent, fill_opacity=0.14,
        stroke_color=accent, stroke_width=1.2,
    )
    fill = RoundedRectangle(
        width=max(0.05, width * fraction), height=0.2, corner_radius=0.1,
        fill_color=accent, fill_opacity=0.9, stroke_width=0,
    )
    fill.align_to(track, LEFT)
    return VGroup(track, fill)


def _spinner(radius: float, accent) -> VGroup:
    """A ring plus an arc that rotates forever — the 'Calculating...' ring.

    The arc rotates about ``get_arc_center()`` (the circle's centre), not
    ``get_center()`` (the bounding-box centre of the swept angle).  For a partial
    arc those differ, so rotating about the bounding box would make the arc swing
    off the ring as it turned.

    The group is re-centred on the ring so a ``move_to`` on the group lands the
    ring exactly where asked, rather than on the asymmetric combined box.
    """
    from manim import Arc, Circle, TAU

    ring = Circle(radius=radius, color=accent, stroke_width=3.5, stroke_opacity=0.22)
    arc = Arc(radius=radius, start_angle=0, angle=TAU * 0.28,
              color=accent, stroke_width=4.5)
    arc.add_updater(lambda m, dt: m.rotate(dt * 3.4, about_point=m.get_arc_center()))
    group = VGroup(ring, arc)
    # make the group's box symmetric about the ring's centre
    group.shift(ring.get_center() - group.get_center())
    return group


def _content_band() -> tuple[float, float]:
    """The vertical band content may occupy: (top, bottom) in scene units.

    ``content_top`` is the first safe row under the header; the bottom is the
    safe-area floor.  Laying a stack out inside this band is what keeps a
    multi-part composition from colliding with itself.
    """
    return THEME.spacing.content_top, -layout.safe_height() / 2


def _content_centre(offset: float = 0.0) -> list[float]:
    """Vertical centre of the band below the scene header.

    The header sits at ``spacing.header_y`` (~3.15) and content is only safe
    below ``content_top`` (~2.55), so the usable band is *not* centred on y=0:
    its centre is roughly -0.5.  Centring on 0 pushes every composition upward
    and leaves a dead strip at the bottom of a 9:16 frame.
    """
    top, bottom = _content_band()
    return [0.0, (top + bottom) / 2 + offset, 0.0]


def _terminal_frame(width: float, height: float, accent) -> VGroup:
    """A rounded terminal body with a title bar."""
    body = surfaces.panel(width, height, accent=accent, fill=None)
    bar = _window_chrome(width, accent, "terminal")
    bar.next_to(body.get_top(), DOWN, buff=0.0)
    return VGroup(body, bar)


def _tree_row(name: str, size: str, *, accent, depth: int = 0,
              highlight: bool = False, bar_fraction: float = 0.0,
              width: float = 3.6) -> VGroup:
    """One line of the gdu listing: indent, name, size bar, size."""
    row = VGroup()
    indent = Rectangle(width=0.001 + depth * 0.22, height=0.01, stroke_width=0)
    name_t = typography.mono(name, size=21,
                             color=accent if highlight else None)
    size_t = typography.mono(size, size=19,
                             color=accent if highlight else None)
    # size bar sits between the name and the number
    track_w = 0.9
    bar = RoundedRectangle(
        width=max(0.02, track_w * bar_fraction), height=0.12, corner_radius=0.06,
        fill_color=accent, fill_opacity=0.85 if highlight else 0.45, stroke_width=0,
    )
    bar_track = Rectangle(width=track_w, height=0.12, stroke_width=0,
                          fill_color=accent, fill_opacity=0.10)
    bar.align_to(bar_track, LEFT)
    bar_g = VGroup(bar_track, bar)

    row.add(indent, name_t)
    row.arrange(RIGHT, buff=0.1, aligned_edge=DOWN)
    tail = VGroup(bar_g, size_t).arrange(RIGHT, buff=0.12)
    row.add(tail)
    # right-align the tail inside the row
    row.arrange(RIGHT, buff=0.12, aligned_edge=DOWN)
    layout.fit_width(row, width)
    if highlight:
        band = RoundedRectangle(
            width=width + 0.14, height=0.36, corner_radius=0.08,
            fill_color=accent, fill_opacity=0.16, stroke_width=0,
        )
        band.move_to(row.get_center())
        return VGroup(band, row)
    return VGroup(row)


def _keycap(text: str, accent, *, size: float = 0.52) -> VGroup:
    """A keyboard key cap."""
    cap = RoundedRectangle(
        width=size, height=size, corner_radius=0.1,
        fill_color=accent, fill_opacity=0.16,
        stroke_color=accent, stroke_width=1.6,
    )
    t = typography.mono(text, size=24, color=accent, weight="BOLD")
    t.move_to(cap.get_center())
    return VGroup(cap, t)


# --------------------------------------------------------------------------
# 01 — the hook: a frozen "Calculating..." dialog
# --------------------------------------------------------------------------
class SceneHook(ExplainerScene):
    """Windows Explorer frozen on 'Calculating...' — the universal pain."""

    def construct(self) -> None:
        t = self.theme
        self.add_header("The pain", accent=t.rose, index="01")

        w = layout.safe_width()
        # Content runs at ~86% of the safe width: at 100% it spans 87% of the
        # whole frame, which reads as edge-to-edge and crowds a 9:16 crop.
        card_w = min(w, 3.15)
        frame = _terminal_frame(card_w, 2.15, t.rose)
        frame.move_to(_content_centre(0.55))

        spinner = _spinner(0.30, t.rose)
        spinner.move_to(frame[0].get_center()).shift(UP * 0.30)
        status = typography.mono("Calculating...", size=25, color=t.rose)
        status.next_to(spinner, DOWN, buff=0.30)

        detail = typography.label("1 folder  ·  412,908 items", size=20)
        detail.next_to(status, DOWN, buff=0.14)

        self.register_content(frame)
        self.play(FadeIn(frame), run_time=t.motion.base)
        self.play(GrowFromCenter(spinner), FadeIn(status), run_time=t.motion.base)
        self.play(FadeIn(detail, shift=UP * 0.1), run_time=t.motion.quick)

        # the count creeps — the joke is that it never finishes
        self.wait(0.9)

        headline = typography.headline("STOP WAITING", size=46, color=t.rose)
        sub = typography.body("Windows will not tell you the size.", size=24)
        block = VGroup(headline, sub).arrange(DOWN, buff=0.14)
        layout.fit_width(block, w * 0.92)
        block.move_to(_content_centre(-1.45))
        self.register_content(block)
        self.play(FadeIn(headline, shift=DOWN * 0.18), run_time=t.motion.medium)
        self.play(FadeIn(sub), run_time=t.motion.quick)
        self.settle()


# --------------------------------------------------------------------------
# 02 — the problem: a bar that does not move
# --------------------------------------------------------------------------
class SceneProblem(ExplainerScene):
    """The loading bar crawls; the CPU fans start screaming."""

    def construct(self) -> None:
        t = self.theme
        self.add_header("Why it hurts", accent=t.amber, index="02")

        w = layout.safe_width()
        bar_w = min(w, 3.15)

        self.play(FadeIn(typography.label("Calculating folder size", size=21)
                         .move_to(_content_centre(1.45))), run_time=t.motion.quick)

        bar = _progress_bar(bar_w, 0.02, t.amber)
        bar.move_to(_content_centre(0.95))
        pct = typography.mono("2%", size=25, color=t.amber)
        pct.next_to(bar, DOWN, buff=0.20)
        self.register_content(VGroup(bar, pct))
        self.play(Create(bar[0]), FadeIn(bar[1]), FadeIn(pct),
                  run_time=t.motion.base)

        # it barely moves — that is the whole point
        self.play(bar[1].animate.stretch_to_fit_width(bar_w * 0.09)
                  .align_to(bar[0], LEFT),
                  Transform(pct, typography.mono("7%", size=25, color=t.amber)
                            .move_to(pct.get_center())),
                  run_time=1.6)

        # CPU meter pinned at 100%
        meter = data.meter(1.0, width=bar_w, accent=t.rose)
        meter.move_to(_content_centre(-0.15))
        cpu = typography.label("CPU: one core, 100%", size=20, color=t.rose)
        cpu.next_to(meter, DOWN, buff=0.18)
        self.register_content(VGroup(meter, cpu))
        self.play(FadeIn(meter, shift=UP * 0.12), run_time=t.motion.medium)
        self.play(FadeIn(cpu), run_time=t.motion.quick)

        dead = typography.headline("Minutes of nothing.", size=32, color=t.amber)
        layout.fit_width(dead, w * 0.92)
        dead.move_to(_content_centre(-1.35))
        self.register_content(dead)
        self.play(FadeIn(dead, shift=UP * 0.14), run_time=t.motion.medium)
        self.settle()


# --------------------------------------------------------------------------
# 03 — the solution: type gdu
# --------------------------------------------------------------------------
class SceneSolution(ExplainerScene):
    """`gdu` fills the screen with a size-sorted tree."""

    ROWS = [
        ("node_modules", "4.1G", 0, 1.00),
        ("  .cache", "2.3G", 1, 0.62),
        ("  dist", "1.8G", 1, 0.48),
        ("  src", "204M", 1, 0.10),
        ("Downloads", "1.2G", 0, 0.34),
        ("  disk.img", "980M", 1, 0.28),
        ("Documents", "310M", 0, 0.09),
    ]

    def construct(self) -> None:
        t = self.theme
        self.add_header("The fix", accent=t.green, index="03")

        w = layout.safe_width()
        frame_w = min(w, 3.35)
        top, bottom = _content_band()

        prompt = typography.mono("$ gdu", size=28, color=t.green)
        self.register_content(prompt)

        # the listing appears
        rows = VGroup()
        for name, size, depth, frac in self.ROWS:
            rows.add(_tree_row(name, size, accent=t.green, depth=depth,
                               bar_fraction=frac, width=frame_w - 0.42))
        rows.arrange(DOWN, buff=0.13, aligned_edge=LEFT)
        layout.fit_width(rows, frame_w - 0.42)

        body = surfaces.panel(frame_w, rows.height + 0.62, accent=t.green)
        rows.move_to(body.get_center())
        listing = VGroup(body, rows)

        stat = typography.stat_number("4.7s", size=58, color=t.green)
        cap = typography.label("for a 90 GB tree", size=20)
        block = VGroup(stat, cap).arrange(DOWN, buff=0.08)
        layout.fit_width(block, w * 0.92)
        self.register_content(listing)
        self.register_content(block)

        # Stack prompt / listing / stat inside the band.  Fixed offsets put the
        # prompt through the top of the panel (measured overlap +0.17u).
        gaps = 0.34
        total = prompt.height + listing.height + block.height + 2 * gaps
        avail = top - bottom
        if total > avail:
            scale = avail / total
            for g in (prompt, listing, block):
                g.scale(scale)
            gaps *= scale
        y = top
        for g in (prompt, listing, block):
            g.move_to([0, y - g.height / 2, 0])
            y -= g.height + gaps

        self.play(Write(prompt), run_time=0.9)
        self.wait(0.25)
        self.play(FadeIn(body), run_time=t.motion.quick)
        self.play(timing.fade_in_stagger(list(rows), lag=0.09),
                  run_time=t.motion.slow)
        self.play(FadeIn(block, shift=UP * 0.16), run_time=t.motion.medium)
        self.settle()


# --------------------------------------------------------------------------
# 04 — features: arrows navigate, `d` deletes
# --------------------------------------------------------------------------
class SceneFeatures(ExplainerScene):
    """Arrow keys drill in; `d` wipes the junk folder."""

    ROWS = [
        ("node_modules", "4.1G", 0),
        (".cache", "2.3G", 1),
        ("dist", "1.8G", 1),
        ("old_backups", "1.1G", 1),
        ("Documents", "310M", 0),
    ]

    def construct(self) -> None:
        t = self.theme
        self.add_header("Drill in. Delete.", accent=t.cyan, index="04")

        w = layout.safe_width()
        frame_w = min(w, 3.35)
        top, bottom = _content_band()

        rows = VGroup()
        for i, (name, size, depth) in enumerate(self.ROWS):
            rows.add(_tree_row(name, size, accent=t.cyan, depth=depth,
                               highlight=(i == 0), bar_fraction=0.9 - i * 0.16,
                               width=frame_w - 0.42))
        rows.arrange(DOWN, buff=0.15, aligned_edge=LEFT)
        layout.fit_width(rows, frame_w - 0.42)
        body = surfaces.panel(frame_w, rows.height + 0.56, accent=t.cyan)
        rows.move_to(body.get_center())
        listing = VGroup(body, rows)

        keys = VGroup(
            _keycap("←", t.cyan), _keycap("↓", t.cyan), _keycap("→", t.cyan)
        ).arrange(RIGHT, buff=0.18)
        nav = typography.label("arrow keys to navigate", size=20)
        nav.next_to(keys, DOWN, buff=0.18)
        keygroup = VGroup(keys, nav)

        d_key = _keycap("d", t.rose, size=0.58)
        dele = typography.label("delete on the spot", size=20, color=t.rose)
        dele.next_to(d_key, DOWN, buff=0.16)
        dgroup = VGroup(d_key, dele)

        self.register_content(listing)
        self.register_content(keygroup)
        self.register_content(dgroup)

        # Three stacked groups again: guessed centres had the arrow keys sitting
        # 0.50u inside the `d` keycap.
        gaps = 0.34
        total = listing.height + keygroup.height + dgroup.height + 2 * gaps
        avail = top - bottom
        if total > avail:
            scale = avail / total
            for g in (listing, keygroup, dgroup):
                g.scale(scale)
            gaps *= scale
        y = top
        for g in (listing, keygroup, dgroup):
            g.move_to([0, y - g.height / 2, 0])
            y -= g.height + gaps

        self.play(FadeIn(listing), run_time=t.motion.medium)
        self.play(FadeIn(keys, shift=UP * 0.12), run_time=t.motion.quick)
        self.play(FadeIn(nav), run_time=t.motion.quick)

        # the highlight walks down to old_backups
        for idx in (1, 2, 3):
            self.play(
                Indicate(rows[idx], color=t.cyan, scale_factor=1.02),
                run_time=0.34,
            )

        # `d` deletes it
        self.play(FadeIn(d_key, shift=UP * 0.12), run_time=t.motion.quick)
        self.play(FadeIn(dele), run_time=t.motion.quick)

        gone = typography.mono("deleted old_backups", size=21, color=t.rose)
        gone.next_to(dele, DOWN, buff=0.14)
        self.play(FadeOut(rows[3]), FadeIn(gone, shift=UP * 0.1),
                  run_time=t.motion.base)
        self.settle()


# --------------------------------------------------------------------------
# 05 — outro: install lines + CTA
# --------------------------------------------------------------------------
class SceneOutro(ExplainerScene):
    """Free, open source — and the follow prompt."""

    INSTALLS = [
        ("Debian / Ubuntu", "sudo apt install gdu"),
        ("Arch", "pacman -S gdu"),
        ("macOS", "brew install gdu"),
    ]

    def construct(self) -> None:
        t = self.theme
        self.add_header("Get it", accent=t.violet, index="05")

        w = layout.safe_width()
        top, bottom = _content_band()
        avail = top - bottom

        badge = surfaces.badge("FREE  ·  OPEN SOURCE", accent=t.violet, size=20)
        self.register_content(badge)

        cards = VGroup()
        for os_name, cmd in self.INSTALLS:
            c = surfaces.card(os_name, cmd, width=min(w, 3.20), accent=t.violet,
                              title_size=21, body_size=20)
            cards.add(c)
        cards.arrange(DOWN, buff=0.18)
        layout.fit_width(cards, w * 0.94)

        cta = typography.headline("Follow for more", size=32, color=t.violet)
        cta2 = typography.body("terminal black magic", size=23)
        block = VGroup(cta, cta2).arrange(DOWN, buff=0.10)
        layout.fit_width(block, w * 0.92)
        self.register_content(cards)
        self.register_content(block)

        # Lay the three groups out from their measured heights rather than from
        # fixed offsets: the cards are ~4.8u tall on their own, so guessed
        # centres pushed them straight through the badge and the CTA.
        gaps = 0.40
        total = badge.height + cards.height + block.height + 2 * gaps
        if total > avail:                      # shrink the stack to fit the band
            scale = avail / total
            for g in (badge, cards, block):
                g.scale(scale)
            gaps *= scale
            total = avail
        y = top
        for g in (badge, cards, block):
            g.move_to([0, y - g.height / 2, 0])
            y -= g.height + gaps

        self.play(GrowFromCenter(badge), run_time=t.motion.medium)
        self.play(timing.fade_in_stagger(list(cards), lag=0.16),
                  run_time=t.motion.slow)
        self.play(FadeIn(block, shift=UP * 0.16), run_time=t.motion.medium)
        self.settle()
