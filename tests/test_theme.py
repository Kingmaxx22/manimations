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
