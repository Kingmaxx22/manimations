"""Tests for brief scaffolding and narration text handling."""

from __future__ import annotations

from pathlib import Path

from manimations.brief import Brief, scaffold_project, slugify
from manimations.config import ProjectConfig
from manimations.pipeline.audio import build_srt, normalise_for_tts, NarrationClip


def test_slugify():
    assert slugify("What Is IPv6, and Why Is Adoption So Slow?") == (
        "what_is_ipv6_and_why_is_adoption_so_slow"
    )


def test_brief_from_dict_defaults():
    brief = Brief.from_dict({"title": "Test Topic"})
    assert brief.scenes  # default brief supplies scenes
    assert brief.slug == "test_topic"


def test_brief_outline_contains_scenes():
    brief = Brief.from_dict({"title": "T", "slug": "t"})
    out = brief.outline()
    assert "T" in out and "01_intro" in out


def test_scaffold_creates_runnable_project(tmp_path):
    brief = Brief.from_dict({"title": "New Topic", "slug": "new_topic"})
    root = scaffold_project(tmp_path / "new_topic", brief)
    assert (root / "project.yaml").exists()
    assert (root / "scenes.py").exists()
    proj = ProjectConfig.load(root)
    assert proj.slug == "new_topic"
    assert proj.validate() == []


def test_scaffold_refuses_overwrite(tmp_path):
    brief = Brief.from_dict({"title": "T", "slug": "t"})
    root = scaffold_project(tmp_path / "t", brief)
    import pytest

    with pytest.raises(Exception):
        scaffold_project(root, brief, overwrite=False)


def test_normalise_for_tts_expands_acronyms():
    out = normalise_for_tts("IPv6 and IPv4 use NAT")
    assert "I P version six" in out
    assert "I P version four" in out
    assert "N A T" in out


def test_build_srt_covers_all_scenes(tmp_path, project_dir):
    proj = ProjectConfig.load(project_dir)
    srt = build_srt(proj, out_path=tmp_path / "s.srt")
    text = srt.read_text(encoding="utf-8")
    assert "-->" in text
    assert "01" in text or "introduction" in text
    # two scenes -> two cues
    assert text.count("-->") == 2


def test_build_srt_uses_declared_scene_durations(tmp_path, project_dir):
    """Cue times follow the scene timeline, so subtitles line up with the video."""
    proj = ProjectConfig.load(project_dir)
    srt = build_srt(proj, out_path=tmp_path / "s.srt")
    text = srt.read_text(encoding="utf-8")
    # scene 1 is 12s, scene 2 is 12s -> second cue starts at 12s
    assert "00:00:00,000 --> 00:00:12,000" in text
    assert "00:00:12,000 --> 00:00:24,000" in text
