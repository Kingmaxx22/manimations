"""Tests for the theme / design system."""

from __future__ import annotations

import pytest
from manim import ManimColor, config

from manimations.theme import (
    VIDEO_FPS,
    VIDEO_HEIGHT,
    VIDEO_WIDTH,
    THEME,
    apply_theme,
    body_font,
    heading_font,
    mono_font,
)


def test_apply_theme_sets_background():
    apply_theme()
    assert config.background_color == THEME.bg


def test_apply_theme_keeps_aspect_ratio():
    apply_theme()
    assert config.frame_width / config.frame_height == pytest.approx(16 / 9)


def test_apply_theme_does_not_override_resolution():
    """Resolution belongs to the render quality flags, not the theme."""
    config.pixel_width = 854
    config.pixel_height = 480
    apply_theme()
    assert config.pixel_width == 854
    assert config.pixel_height == 480


def test_output_contract_constants():
    assert (VIDEO_WIDTH, VIDEO_HEIGHT, VIDEO_FPS) == (1920, 1080, 30)


def test_palette_colors_are_manim_colors():
    for name in ("bg", "text", "cyan", "amber", "violet"):
        assert isinstance(getattr(THEME, name), ManimColor)


def test_accent_named_falls_back_to_accent():
    assert THEME.accent_named("amber") == THEME.amber
    assert THEME.accent_named("does-not-exist") == THEME.accent


def test_fonts_resolve_to_non_empty_strings():
    for fn in (heading_font, body_font, mono_font):
        assert isinstance(fn(), str) and fn()


# --------------------------------------------------------------------------
# Style switching (neumorphism is opt-in per project; classic must stay exact)
# --------------------------------------------------------------------------
def test_set_style_switches_palette_and_restores():
    from manimations.theme import set_style

    classic_bg = THEME.bg
    classic_cyan = THEME.cyan
    set_style("neumorphic")
    try:
        assert THEME.style == "neumorphic"
        assert THEME.is_neumorphic
        assert THEME.bg != classic_bg
        assert THEME.palette.bg == "#202432"  # raw hex token, not a ManimColor
        assert THEME.cyan == classic_cyan  # accents survive the style switch
    finally:
        set_style("classic")
    assert THEME.style == "classic"
    assert THEME.bg == classic_bg


def test_unknown_style_falls_back_to_classic():
    """A typo in `theme:` must never re-skin a delivered episode."""
    from manimations.theme import set_style

    set_style("neumorphic")
    try:
        set_style("dracula")
        assert THEME.style == "classic"
    finally:
        set_style("classic")


def test_apply_theme_reads_style_from_env(monkeypatch):
    from manimations.theme import set_style

    monkeypatch.setenv("MANIMATIONS_THEME", "neumorphic")
    try:
        apply_theme()
        assert THEME.style == "neumorphic"
        assert config.background_color == THEME.bg
    finally:
        set_style("classic")


def test_panel_is_plain_rectangle_in_classic_and_shadowed_in_neumorphic():
    from manim import RoundedRectangle, VGroup

    from manimations.components.surfaces import panel
    from manimations.theme import set_style

    # classic: byte-identical to the original design system
    classic = panel(2.0, 1.0)
    assert isinstance(classic, RoundedRectangle)

    set_style("neumorphic")
    try:
        neu = panel(2.0, 1.0)
        assert isinstance(neu, VGroup)
        assert isinstance(neu[-1], RoundedRectangle)  # plate stays on top
        assert len(neu) == 6  # 3 dark + 2 light + plate
        # a translucent panel gets no shadow layers (they would read as a
        # filled box behind a transparent plate)
        assert isinstance(panel(2.0, 1.0, fill_opacity=0.0), RoundedRectangle)
    finally:
        set_style("classic")
