"""Tests for project configuration and the scene brief schema."""

from __future__ import annotations

import pytest

from manimations.config import ConfigError, ProjectConfig, SceneSpec


def test_scene_spec_word_count_and_wpm():
    spec = SceneSpec(
        id="01_x", cls="S", narration="one two three four five", duration=2.0
    )
    assert spec.word_count == 5
    assert spec.wpm == pytest.approx(150.0)


def test_scene_spec_rejects_bad_id():
    spec = SceneSpec(id="intro", cls="S")
    problems = spec.validate()
    assert any("must match NN_name" in p for p in problems)


def test_scene_spec_flags_unreasonable_pace():
    spec = SceneSpec(id="01_x", cls="S", narration="a b c", duration=60)
    problems = spec.validate()
    assert not problems  # structural problems only; wpm is a warning now
    warnings = spec.wpm_warnings()
    assert any("wpm" in w for w in warnings)


def test_scene_spec_suggested_duration():
    spec = SceneSpec(id="01_x", cls="S", narration=" ".join(["w"] * 50))
    assert spec.suggested_duration == pytest.approx(20.0)


def test_project_load(project_dir):
    proj = ProjectConfig.load(project_dir)
    assert proj.slug == "demo"
    assert len(proj.scenes) == 2
    assert proj.total_duration == 24
    assert proj.scenes[0].cls == "SceneIntro"


def test_project_validate_ok(project_dir):
    proj = ProjectConfig.load(project_dir)
    assert proj.validate() == []


def test_project_detects_duplicate_ids(project_dir):
    proj = ProjectConfig.load(project_dir)
    proj.scenes[1].id = proj.scenes[0].id
    problems = proj.validate()
    assert any("duplicate" in p for p in problems)


def test_project_detects_out_of_order(project_dir):
    proj = ProjectConfig.load(project_dir)
    proj.scenes.reverse()
    problems = proj.validate()
    assert any("numeric order" in p for p in problems)


def test_missing_project_yaml(tmp_path):
    with pytest.raises(ConfigError):
        ProjectConfig.load(tmp_path)


def test_scene_missing_required_key(tmp_path):
    with pytest.raises(ConfigError):
        SceneSpec.from_dict({"narration": "no id or class"})
