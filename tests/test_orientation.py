"""Tests for orientation (landscape 16:9 / vertical 9:16) support."""

from __future__ import annotations

import pytest
from manim import config

from manimations.theme import (
    LANDSCAPE,
    ORIENTATION_ENV,
    ORIENTATIONS,
    VERTICAL,
    apply_theme,
)


def test_landscape_contract():
    assert (LANDSCAPE.width, LANDSCAPE.height, LANDSCAPE.fps) == (1920, 1080, 30)
    assert not LANDSCAPE.is_vertical
    assert LANDSCAPE.aspect == pytest.approx(16 / 9)


def test_vertical_contract():
    assert (VERTICAL.width, VERTICAL.height, VERTICAL.fps) == (1080, 1920, 30)
    assert VERTICAL.is_vertical
    assert VERTICAL.aspect == pytest.approx(9 / 16)


def test_frame_widths_share_frame_height():
    """Both orientations use frame_height 8; vertical is simply narrower."""
    assert LANDSCAPE.frame_height == VERTICAL.frame_height == 8.0
    assert VERTICAL.frame_width < LANDSCAPE.frame_width


def test_apply_theme_vertical_sets_frame():
    apply_theme(orientation=VERTICAL)
    assert config.frame_height == 8.0
    assert config.frame_width == pytest.approx(4.5)


def test_apply_theme_reads_orientation_env(monkeypatch):
    monkeypatch.setenv(ORIENTATION_ENV, "vertical")
    apply_theme()
    assert config.frame_width == pytest.approx(4.5)
    monkeypatch.setenv(ORIENTATION_ENV, "landscape")
    apply_theme()
    assert config.frame_width == pytest.approx(16 * 8 / 9)


def test_orientation_env_unknown_falls_back_to_landscape(monkeypatch):
    monkeypatch.setenv(ORIENTATION_ENV, "sideways")
    apply_theme()
    assert config.frame_width == pytest.approx(16 * 8 / 9)


def test_preview_resolution_matches_aspect():
    from manimations.pipeline.renderer import preview_resolution

    lw, lh = preview_resolution(LANDSCAPE)
    vw, vh = preview_resolution(VERTICAL)
    # short side is pinned at 480; the long side follows the aspect ratio
    assert lh == 480 and vh == 480
    assert lw / lh == pytest.approx(16 / 9, abs=0.01)
    assert vw / vh == pytest.approx(9 / 16, abs=0.01)
    # even dimensions (H.264 chroma subsampling requires it)
    assert lw % 2 == 0 and vw % 2 == 0


def test_orientations_registry():
    assert ORIENTATIONS["landscape"] is LANDSCAPE
    assert ORIENTATIONS["vertical"] is VERTICAL


def test_project_orientation_from_yaml(tmp_path):
    import textwrap
    from manimations.config import ProjectConfig

    root = tmp_path / "v"
    root.mkdir()
    (root / "project.yaml").write_text(
        textwrap.dedent(
            """
            title: "Vertical Demo"
            slug: v
            orientation: vertical
            scenes:
              - id: 01_a
                class: SceneA
                duration: 8
                narration: "A short vertical scene used to check that the orientation field is read and validated correctly by the loader."
            """
        ).strip(),
        encoding="utf-8",
    )
    (root / "scenes.py").write_text("class SceneA:\n    pass\n", encoding="utf-8")
    proj = ProjectConfig.load(root)
    assert proj.orientation == "vertical"
    assert proj.orient is VERTICAL
    assert proj.validate() == []


def test_project_rejects_bad_orientation(tmp_path):
    import textwrap
    from manimations.config import ProjectConfig

    root = tmp_path / "b"
    root.mkdir()
    (root / "project.yaml").write_text(
        textwrap.dedent(
            """
            title: "Bad"
            slug: b
            orientation: diagonal
            scenes:
              - id: 01_a
                class: SceneA
                duration: 8
                narration: "A short scene that exists only so the orientation check has something to validate."
            """
        ).strip(),
        encoding="utf-8",
    )
    (root / "scenes.py").write_text("class SceneA:\n    pass\n", encoding="utf-8")
    proj = ProjectConfig.load(root)
    problems = proj.validate()
    assert any("orientation" in p for p in problems)
