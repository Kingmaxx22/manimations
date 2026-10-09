"""Tests for narration-driven scene timing (removing silent tails)."""

from __future__ import annotations

import pytest

from manimations.config import ProjectConfig
from manimations.pipeline import audio


def _clip(scene_id: str, duration: float) -> audio.NarrationClip:
    return audio.NarrationClip(scene_id, None, duration, "text", True)


def test_fit_scene_durations_shortens_to_narration(project_dir):
    proj = ProjectConfig.load(project_dir)
    # scenes are declared 12s each; narration is much shorter
    clips = [_clip("01_intro", 6.0), _clip("02_body", 8.0)]
    changes = audio.fit_scene_durations(proj, clips, tail=0.5, write=False)
    assert len(changes) == 2
    assert proj.scene_by_id("01_intro").duration == pytest.approx(6.5)
    assert proj.scene_by_id("02_body").duration == pytest.approx(8.5)


def test_fit_scene_durations_honours_minimum(project_dir):
    proj = ProjectConfig.load(project_dir)
    clips = [_clip("01_intro", 0.4), _clip("02_body", 0.4)]
    audio.fit_scene_durations(proj, clips, tail=0.5, min_duration=3.0, write=False)
    assert proj.scene_by_id("01_intro").duration == pytest.approx(3.0)


def test_fit_scene_durations_skips_silent_scenes(project_dir):
    """A title card with no narration keeps its declared duration."""
    proj = ProjectConfig.load(project_dir)
    original = proj.scene_by_id("02_body").duration
    clips = [_clip("01_intro", 6.0)]  # only scene 1 has narration
    audio.fit_scene_durations(proj, clips, write=False)
    assert proj.scene_by_id("02_body").duration == original


def test_fit_scene_durations_ignores_failed_clips(project_dir):
    proj = ProjectConfig.load(project_dir)
    bad = audio.NarrationClip("01_intro", None, 0.0, "text", False, "boom")
    changes = audio.fit_scene_durations(proj, [bad], write=False)
    assert changes == []


def test_fit_scene_durations_persists_to_yaml(project_dir):
    proj = ProjectConfig.load(project_dir)
    clips = [_clip("01_intro", 6.0), _clip("02_body", 8.0)]
    audio.fit_scene_durations(proj, clips, tail=0.5, write=True)
    reloaded = ProjectConfig.load(project_dir)
    assert reloaded.scene_by_id("01_intro").duration == pytest.approx(6.5)
    assert reloaded.scene_by_id("02_body").duration == pytest.approx(8.5)


def test_persist_preserves_yaml_comments(project_dir):
    """The hand-authored brief keeps its comments and structure."""
    yaml_path = project_dir / "project.yaml"
    text = yaml_path.read_text(encoding="utf-8")
    yaml_path.write_text("# my precious comment\n" + text, encoding="utf-8")

    proj = ProjectConfig.load(project_dir)
    audio.fit_scene_durations(proj, [_clip("01_intro", 6.0)], write=True)

    after = yaml_path.read_text(encoding="utf-8")
    assert "# my precious comment" in after
    assert "class: SceneBody" in after


def test_fit_reduces_total_dead_air(project_dir):
    """The whole point: total duration drops toward the narration total."""
    proj = ProjectConfig.load(project_dir)
    before = proj.total_duration
    clips = [_clip("01_intro", 6.0), _clip("02_body", 8.0)]
    audio.fit_scene_durations(proj, clips, tail=0.5, write=False)
    after = proj.total_duration
    assert after < before
    assert after == pytest.approx(15.0)  # 6.5 + 8.5
