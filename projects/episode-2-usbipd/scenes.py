"""usbipd — vertical 9:16 short for Reels / Shorts / TikTok.

"The WSL trick that feels illegal": pass a physical USB device straight through
to WSL 2 with usbipd-win, no dual-boot.

Commands on screen are the real ones, checked against usbipd-win 5.3.0's own
``--help`` output on this machine and Microsoft's "Connect USB devices" doc:

  * ``usbipd list``                       — find the bus ID (no elevation)
  * ``usbipd bind --busid 4-4``           — share it (needs Administrator)
  * ``usbipd attach --wsl --busid 4-4``   — pipe it into WSL (no elevation)
  * ``lsusb``                             — it appears in Linux

The pre-4.0 ``usbipd wsl list`` / ``usbipd wsl attach`` spelling that older
tutorials (and the first draft of this script) use was **removed** in 4.0.0 and
errors out on 5.x, so the video shows the current syntax.

Everything is positioned from the safe area (never an absolute x), because a
9:16 frame is only ~4.5 scene units wide.
"""

from __future__ import annotations

from manim import (
    DOWN,
    LEFT,
    RIGHT,
    UP,
    DashedLine,
    Dot,
    FadeIn,
    GrowFromCenter,
    Indicate,
    Line,
    RoundedRectangle,
    VGroup,
    Write,
)

from manimations import ExplainerScene
from manimations.components import surfaces, typography
from manimations.helpers import layout, timing
from manimations.theme import THEME


# --------------------------------------------------------------------------
# local building blocks — the terminal aesthetic for this explainer.  Kept here
# rather than in the framework because no other project wants them (the
# framework never imports a project, and a project only imports the framework).
# --------------------------------------------------------------------------
def _window_chrome(width: float, accent, title: str) -> VGroup:
    """A window title bar with three traffic-light dots and a label."""
    bar = RoundedRectangle(
        width=width, height=0.42, corner_radius=0.1,
        fill_color=accent, fill_opacity=0.12,
        stroke_color=accent, stroke_width=1.4,
    )
    dots = VGroup()
    for i in range(3):
        dots.add(RoundedRectangle(
            width=0.10, height=0.10, corner_radius=0.05,
            fill_color=accent, fill_opacity=0.85 - i * 0.2, stroke_width=0,
        ))
    dots.arrange(RIGHT, buff=0.08)
    dots.move_to(bar.get_center())
    dots.align_to(bar, LEFT).shift(RIGHT * 0.20)
    label = typography.label(title, size=17, color=accent)
    label.move_to(bar.get_center())
    return VGroup(bar, dots, label)


def _terminal_frame(width: float, height: float, accent, title: str) -> VGroup:
    """A rounded terminal body with a title bar along its top edge."""
    body = surfaces.panel(width, height, accent=accent, fill=None)
    bar = _window_chrome(width, accent, title)
    bar.next_to(body.get_top(), DOWN, buff=0.0)
    return VGroup(body, bar)


def _console_line(text: str, *, accent, size: int = 20,
                  prompt: str | None = None) -> VGroup:
    """One terminal line: an optional prompt plus the text.

    Returns ``VGroup(prompt, text)`` or ``VGroup(text)``, so a stack of these
    reads as a real console once arranged with ``aligned_edge=LEFT``.
    """
    t = typography.mono(text, size=size, color=accent)
    if prompt is None:
        return VGroup(t)
    p = typography.mono(prompt, size=size, color=THEME.text_muted)
    return VGroup(p, t).arrange(RIGHT, buff=0.12, aligned_edge=DOWN)


def _content_band() -> tuple[float, float]:
    """The vertical band content may occupy: (top, bottom) in scene units."""
    return THEME.spacing.content_top, -layout.safe_height() / 2


def _content_centre(offset: float = 0.0) -> list[float]:
    """Vertical centre of the band below the scene header.

    The header occupies the top ~1.45 units, so the usable band is not centred
    on y=0 — its centre sits near -0.5.  Centring on 0 pushes every composition
    upward and leaves a dead strip at the bottom of a 9:16 frame.
    """
    top, bottom = _content_band()
    return [0.0, (top + bottom) / 2 + offset, 0.0]


def _stack(groups: list[VGroup], gap: float = 0.34) -> None:
    """Lay groups out top-to-bottom inside the content band, in place.

    Laid out from *measured* heights rather than guessed centres, and scaled
    down as a set when the stack does not fit.  Hand-guessed offsets are what
    put the gdu short's prompt through its own listing panel — they go stale the
    moment a type size changes.
    """
    top, bottom = _content_band()
    avail = top - bottom
    total = sum(g.height for g in groups) + gap * (len(groups) - 1)
    if total > avail:
        scale = avail / total
        for g in groups:
            g.scale(scale)
        gap *= scale
    y = top
    for g in groups:
        g.move_to([0, y - g.height / 2, 0])
        y -= g.height + gap


def _usb_stick(accent, size: float = 0.46) -> VGroup:
    """A little USB stick: a plug nub on a rounded body."""
    body = RoundedRectangle(
        width=size * 1.55, height=size * 0.6, corner_radius=0.08,
        fill_color=accent, fill_opacity=0.16,
        stroke_color=accent, stroke_width=1.6,
    )
    plug = RoundedRectangle(
        width=size * 0.3, height=size * 0.34, corner_radius=0.04,
        fill_color=accent, fill_opacity=0.5, stroke_width=0,
    )
    plug.next_to(body, LEFT, buff=0.0)
    return VGroup(plug, body)


def _device_row(busid: str, name: str, state: str, *, accent,
                highlight: bool = False, width: float = 3.1) -> VGroup:
    """One line of ``usbipd list``: BUSID, DEVICE, STATE."""
    cells = VGroup(
        typography.mono(busid, size=19, color=accent if highlight else THEME.text),
        typography.mono(name, size=19,
                        color=accent if highlight else THEME.text_secondary),
        typography.mono(state, size=17,
                        color=accent if highlight else THEME.text_muted),
    )
    row = cells.arrange(RIGHT, buff=0.22, aligned_edge=DOWN)
    layout.fit_width(row, width)
    if highlight:
        band = RoundedRectangle(
            width=width + 0.12, height=0.30, corner_radius=0.06,
            fill_color=accent, fill_opacity=0.16, stroke_width=0,
        )
        band.move_to(row.get_center())
        return VGroup(band, row)
    return VGroup(row)


# --------------------------------------------------------------------------
# 01 — the hook: lsusb comes back empty
# --------------------------------------------------------------------------
class SceneHook(ExplainerScene):
    """A WSL terminal where the device simply is not there."""

    def construct(self) -> None:
        t = self.theme
        self.add_header("The problem", accent=t.rose, index="01")

        w = layout.safe_width()
        # Content runs at ~86% of the safe width: filling it spans 87% of the
        # whole frame, which reads as edge-to-edge on a phone.
        win_w = min(w, 3.3)

        frame = _terminal_frame(win_w, 1.5, t.rose, "WSL 2 — linux")
        typed = _console_line("lsusb", accent=t.rose, size=21, prompt="$ ")
        empty = typography.mono("no USB devices found", size=19, color=t.rose)
        cursor = Dot(radius=0.035, color=t.rose)
        inner = VGroup(typed, empty).arrange(DOWN, buff=0.22, aligned_edge=LEFT)
        layout.fit_width(inner, win_w - 0.5)
        inner.move_to(frame[0].get_center()).shift(DOWN * 0.06)
        cursor.next_to(empty, DOWN, buff=0.10).align_to(empty, LEFT)

        headline = typography.headline("YOUR USB DEVICE", size=40, color=t.rose)
        sub = typography.body("is invisible to WSL", size=25)
        block = VGroup(headline, sub).arrange(DOWN, buff=0.12)
        layout.fit_width(block, w * 0.92)

        console = VGroup(frame, inner, cursor)
        self.register_content(console)
        self.register_content(block)
        _stack([console, block], gap=0.55)

        self.play(FadeIn(frame), run_time=t.motion.base)
        self.play(Write(typed), run_time=0.7)
        self.play(FadeIn(empty, shift=UP * 0.08), GrowFromCenter(cursor),
                  run_time=t.motion.quick)
        self.play(FadeIn(headline, shift=DOWN * 0.16), run_time=t.motion.medium)
        self.play(FadeIn(sub), run_time=t.motion.quick)
        self.settle()


# --------------------------------------------------------------------------
# 02 — why: Windows holds the hardware, WSL sees nothing
# --------------------------------------------------------------------------
class SceneProblem(ExplainerScene):
    """Windows owns the device; the Linux side is locked out."""

    def construct(self) -> None:
        t = self.theme
        self.add_header("Why it happens", accent=t.amber, index="02")

        w = layout.safe_width()
        card_w = min(w, 3.2)

        stick = _usb_stick(t.amber)
        device = surfaces.card("USB device", "plugged into Windows",
                               width=card_w, accent=t.amber,
                               title_size=21, body_size=18, icon=stick)
        win = surfaces.card("Windows", "claims every USB device",
                            width=card_w, accent=t.amber,
                            title_size=21, body_size=18)
        lin = surfaces.card("WSL 2", "sees none of them",
                            width=card_w, accent=t.rose,
                            title_size=21, body_size=18)

        # A short dashed link with a cross through it: the picture says "this
        # path does not exist" without a word of narration.
        cut = DashedLine([0, 0, 0], [0, 0.36, 0], color=t.rose,
                         stroke_width=2.4, dash_length=0.09)
        cross = VGroup(
            Line([-0.13, -0.13, 0], [0.13, 0.13, 0], color=t.rose, stroke_width=3),
            Line([-0.13, 0.13, 0], [0.13, -0.13, 0], color=t.rose, stroke_width=3),
        )
        link = VGroup(cut, cross)

        note = typography.label("claimed by Windows  ·  locked out of Linux",
                                size=19, color=t.rose)
        layout.fit_width(note, w * 0.92)

        for g in (device, win, lin):
            self.register_content(g)
        self.register_content(link)
        self.register_content(note)
        _stack([device, win, link, lin, note], gap=0.22)

        self.play(FadeIn(device, shift=UP * 0.14), run_time=t.motion.medium)
        self.play(FadeIn(win, shift=UP * 0.12), run_time=t.motion.quick)
        self.play(FadeIn(lin, shift=UP * 0.12), run_time=t.motion.quick)
        self.play(FadeIn(link), FadeIn(cross, scale=0.6), run_time=t.motion.medium)
        self.play(FadeIn(note), run_time=t.motion.quick)
        self.settle()


# --------------------------------------------------------------------------
# 03 — the fix: PowerShell, list → bind → attach
# --------------------------------------------------------------------------
class SceneSolution(ExplainerScene):
    """The three commands, in order, in an elevated PowerShell."""

    def construct(self) -> None:
        t = self.theme
        self.add_header("The fix", accent=t.green, index="03")

        w = layout.safe_width()
        win_w = min(w, 3.4)

        cmd_list = _console_line("usbipd list", accent=t.green, size=19,
                                 prompt="PS> ")
        head = typography.mono("BUSID   DEVICE            STATE", size=15,
                               color=THEME.text_muted)
        row = _device_row("4-4", "Arduino Uno", "Not shared",
                          accent=t.green, highlight=True, width=win_w - 0.5)
        cmd_bind = _console_line("usbipd bind --busid 4-4", accent=t.green,
                                 size=19, prompt="PS> ")
        cmd_attach = _console_line("usbipd attach --wsl --busid 4-4",
                                   accent=t.green, size=19, prompt="PS> ")

        inner = VGroup(cmd_list, head, row, cmd_bind, cmd_attach)
        inner.arrange(DOWN, buff=0.20, aligned_edge=LEFT)
        layout.fit_width(inner, win_w - 0.46)

        frame = _terminal_frame(win_w, inner.height + 0.85, t.green,
                                "PowerShell — Administrator")
        inner.move_to(frame[0].get_center()).shift(DOWN * 0.10)

        admin = surfaces.badge("ADMIN ONCE", accent=t.amber, size=18)
        note = typography.label("one command needs Administrator", size=19,
                                color=t.amber)
        layout.fit_width(note, w * 0.92)

        console = VGroup(frame, inner)
        self.register_content(console)
        self.register_content(VGroup(admin, note))
        _stack([console, admin, note], gap=0.34)

        self.play(FadeIn(frame), run_time=t.motion.base)
        self.play(Write(cmd_list), run_time=0.7)
        self.play(FadeIn(head), FadeIn(row, shift=UP * 0.08),
                  run_time=t.motion.medium)
        self.play(Write(cmd_bind), run_time=0.8)
        self.play(Write(cmd_attach), run_time=0.9)
        self.play(FadeIn(admin, shift=UP * 0.1), run_time=t.motion.quick)
        self.play(FadeIn(note), run_time=t.motion.quick)
        self.settle()


# --------------------------------------------------------------------------
# 04 — the payoff: the device shows up in Linux
# --------------------------------------------------------------------------
class ScenePayoff(ExplainerScene):
    """``lsusb`` now lists the hardware, and it is usable."""

    def construct(self) -> None:
        t = self.theme
        self.add_header("The payoff", accent=t.cyan, index="04")

        w = layout.safe_width()
        win_w = min(w, 3.4)

        cmd = _console_line("lsusb", accent=t.cyan, size=21, prompt="$ ")
        dev1 = typography.mono("Bus 001 Device 002: ID 2341:0043", size=17,
                               color=t.cyan)
        dev2 = typography.mono("Arduino SA Uno R3", size=17, color=t.cyan)
        inner = VGroup(cmd, dev1, dev2).arrange(DOWN, buff=0.20, aligned_edge=LEFT)
        layout.fit_width(inner, win_w - 0.46)

        frame = _terminal_frame(win_w, inner.height + 0.80, t.cyan, "WSL 2 — linux")
        inner.move_to(frame[0].get_center()).shift(DOWN * 0.10)

        port = surfaces.badge("/dev/ttyUSB0", accent=t.cyan, size=19)

        uses = VGroup()
        for text in ("flash firmware", "read raw drives", "run hardware scripts"):
            uses.add(typography.label(text, size=19, color=THEME.text_secondary))
        uses.arrange(DOWN, buff=0.14)
        layout.fit_width(uses, w * 0.92)

        console = VGroup(frame, inner)
        self.register_content(console)
        self.register_content(port)
        self.register_content(uses)
        _stack([console, port, uses], gap=0.30)

        self.play(FadeIn(frame), run_time=t.motion.base)
        self.play(Write(cmd), run_time=0.6)
        self.play(FadeIn(dev1, shift=UP * 0.10), run_time=t.motion.quick)
        self.play(FadeIn(dev2, shift=UP * 0.10), run_time=t.motion.quick)
        self.play(Indicate(dev1, color=t.cyan, scale_factor=1.03),
                  run_time=t.motion.quick)
        self.play(GrowFromCenter(port), run_time=t.motion.quick)
        self.play(timing.fade_in_stagger(list(uses), lag=0.18),
                  run_time=t.motion.slow)
        self.settle()


# --------------------------------------------------------------------------
# 05 — outro: the tool name, the install line, the CTA
# --------------------------------------------------------------------------
class SceneOutro(ExplainerScene):
    """Name the tool, show how to get it, ask for the follow."""

    def construct(self) -> None:
        t = self.theme
        self.add_header("Get it", accent=t.violet, index="05")

        w = layout.safe_width()

        badge = surfaces.badge("FREE  ·  OPEN SOURCE", accent=t.violet, size=19)

        tool = surfaces.card("usbipd-win", "winget install usbipd",
                             width=min(w, 3.2), accent=t.violet,
                             title_size=24, body_size=20)
        repo = typography.label("github.com/dorssel/usbipd-win", size=18,
                                color=THEME.text_muted)
        layout.fit_width(repo, w * 0.92)

        cta = typography.headline("Follow for Episode 3", size=30, color=t.violet)
        layout.fit_width(cta, w * 0.92)

        self.register_content(badge)
        self.register_content(tool)
        self.register_content(repo)
        self.register_content(cta)
        _stack([badge, tool, repo, cta], gap=0.36)

        self.play(GrowFromCenter(badge), run_time=t.motion.medium)
        self.play(FadeIn(tool, shift=UP * 0.14), run_time=t.motion.medium)
        self.play(FadeIn(repo), run_time=t.motion.quick)
        self.play(FadeIn(cta, shift=UP * 0.14), run_time=t.motion.medium)
        self.settle()
