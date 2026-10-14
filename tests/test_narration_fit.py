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


# ---------------------------------------------------------------------------
# the timeline must follow what was RENDERED, not what the brief declared
#
# A declared duration is a target, not a promise.  ExplainerScene._pad_to_target
# holds the final frame until the target, but when the scene's own animation
# already runs longer it applies a minimum hold INSTEAD of the pad, so the scene
# renders longer than declared.  Everything downstream that builds a timeline
# has to use the rendered numbers.
#
# Regression: episode-32-lazydocker.  Scene 01 was declared 3.6s but animated
# for 3.77s, so it rendered 4.90s.  The narration track and the subtitles were
# built on the declared timeline, so scene 03's voice began 1.1s before scene 03
# appeared on screen and the last 2.5s of the video had no audio.
# ---------------------------------------------------------------------------
def test_scene_timeline_uses_rendered_durations(project_dir):
    proj = ProjectConfig.load(project_dir)

    # no override: the brief's declared durations, 12s each
    assert [(sid, start, end) for sid, start, end in audio.scene_timeline(proj)] == [
        ("01_intro", 0.0, 12.0),
        ("02_body", 12.0, 24.0),
    ]

    # scene 01 overran by 1.3s -> scene 02 starts 1.3s later, not at 12.0
    timeline = audio.scene_timeline(proj, {"01_intro": 13.3, "02_body": 12.0})
    assert [sid for sid, _, _ in timeline] == ["01_intro", "02_body"]
    assert timeline[0][1] == 0.0
    assert timeline[0][2] == pytest.approx(13.3)
    assert timeline[1][1] == pytest.approx(13.3)
    assert timeline[1][2] == pytest.approx(25.3)


def test_scene_timeline_is_contiguous(project_dir):
    """No gaps or overlaps, whatever mix of declared and rendered is supplied."""
    proj = ProjectConfig.load(project_dir)
    timeline = audio.scene_timeline(proj, {"02_body": 9.0})
    for (_sid, _start, end), (_nid, nstart, _nend) in zip(timeline, timeline[1:]):
        assert nstart == pytest.approx(end)


def test_scene_timeline_honours_a_floor(project_dir):
    """A zero or absurd duration cannot collapse the timeline."""
    proj = ProjectConfig.load(project_dir)
    timeline = audio.scene_timeline(proj, {"01_intro": 0.0})
    assert timeline[0][2] == pytest.approx(0.5)


def test_build_srt_cue_times_follow_rendered_durations(project_dir, tmp_path):
    proj = ProjectConfig.load(project_dir)
    out = audio.build_srt(proj, out_path=tmp_path / "s.srt",
                          durations={"01_intro": 13.3, "02_body": 12.0})
    text = out.read_text(encoding="utf-8")
    # second cue starts where the FIRST scene actually ended
    assert "00:00:13,300 --> 00:00:25,300" in text
    assert "00:00:12,000 --> 00:00:24,000" not in text


def test_scene_durations_skips_unreadable_files(tmp_path):
    """Unreadable or missing files are omitted so callers fall back."""
    from manimations.pipeline import probe

    bogus = tmp_path / "01_intro.mp4"
    bogus.write_text("not a video", encoding="utf-8")
    assert probe.scene_durations([bogus, tmp_path / "missing.mp4"]) == {}
