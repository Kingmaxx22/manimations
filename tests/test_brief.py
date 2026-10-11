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


def test_scaffold_header_titles_are_short(tmp_path):
    """Generated headers must fit the frame: a long note becomes a short title."""
    from manimations.brief import _short_title
    from manimations.config import SceneSpec

    spec = SceneSpec(
        id="01_x", cls="S",
        notes="Build the resolution tree from the root downward, one level at a time.",
    )
    title = _short_title(spec)
    assert len(title) <= 38
    assert "." not in title  # first clause only
    # falls back to the scene id when there are no notes
    assert _short_title(SceneSpec(id="02_hierarchy", cls="S")) == "Hierarchy"


def test_scaffolded_scenes_import_layout(tmp_path):
    """The placeholder card is sized from layout.safe_width(), so the import
    must be present or every generated scene raises NameError."""
    brief = Brief.from_dict({"title": "T", "slug": "t"})
    root = scaffold_project(tmp_path / "t", brief)
    source = (root / "scenes.py").read_text(encoding="utf-8")
    assert "from manimations.helpers import layout, timing" in source
    assert "layout.safe_width()" in source


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


def test_build_srt_prefers_subtitle_text_over_narration(tmp_path, project_dir):
    """A phonetic respelling spoken for the TTS engine must not reach the screen.

    A product name is sometimes respelled so the voice pronounces it correctly
    ("mise" -> "meez").  The subtitles are read, not heard, so they have to carry
    the real spelling or the video shows a misspelled name.
    """
    proj = ProjectConfig.load(project_dir)
    proj.scenes[0].narration = "One tool replaces them all. meez handles Node."
    proj.scenes[0].subtitle_text = "One tool replaces them all. mise handles Node."

    srt = build_srt(proj, out_path=tmp_path / "s.srt")
    text = srt.read_text(encoding="utf-8")
    # _wrap() breaks cues across lines, so compare with whitespace normalised.
    flat = " ".join(text.split())

    assert "mise handles Node" in flat      # the real spelling is shown
    assert "meez" not in flat               # the respelling never is


def test_build_srt_falls_back_to_narration_without_subtitle_text(tmp_path, project_dir):
    """The override is opt-in; an untouched brief is unaffected."""
    proj = ProjectConfig.load(project_dir)
    assert not proj.scenes[0].subtitle_text
    srt = build_srt(proj, out_path=tmp_path / "s.srt")
    flat = " ".join(srt.read_text(encoding="utf-8").split())
    assert proj.scenes[0].narration.split(".")[0] in flat

