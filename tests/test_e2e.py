"""End-to-end tests: real rendering, assembly and QA.

These are slower (they invoke Manim) but they are the only way to prove the
pipeline actually produces a video.  They are marked ``slow`` so they can be
deselected with ``-m "not slow"``.
"""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from manimations.config import ProjectConfig
from manimations.pipeline import assembler, probe, qa, renderer

pytestmark = pytest.mark.slow


@pytest.fixture
def tiny_project(tmp_path: Path) -> Path:
    """A two-scene project that renders in a few seconds."""
    root = tmp_path / "tiny"
    root.mkdir()
    (root / "project.yaml").write_text(
        textwrap.dedent(
            """
            title: "Tiny"
            slug: tiny
            scenes:
              - id: 01_a
                class: SceneA
                accent: cyan
                duration: 4
                narration: "A short first scene for the end to end test run."
                visuals: [card]
              - id: 02_b
                class: SceneB
                accent: amber
                duration: 4
                narration: "A short second scene for the end to end test run."
                visuals: [card]
            """
        ).strip(),
        encoding="utf-8",
    )
    (root / "scenes.py").write_text(
        textwrap.dedent(
            """
            from manim import FadeIn, VGroup
            from manimations import ExplainerScene
            from manimations.components import surfaces

            class SceneA(ExplainerScene):
                def construct(self):
                    c = surfaces.card("A", "first", accent=self.theme.cyan, width=5)
                    self.register_content(c)
                    self.play(FadeIn(c))
                    self.wait(0.4)

            class SceneB(ExplainerScene):
                def construct(self):
                    c = surfaces.card("B", "second", accent=self.theme.amber, width=5)
                    self.register_content(c)
                    self.play(FadeIn(c))
                    self.wait(0.4)
            """
        ).strip(),
        encoding="utf-8",
    )
    return root


def test_render_one_scene(tiny_project):
    proj = ProjectConfig.load(tiny_project)
    res = renderer.render_scene(proj, proj.scenes[0], quality="l", timeout=300)
    assert res.ok, res.error and res.error.summary()
    assert res.path is not None and res.path.exists()
    info = probe.probe_video(res.path)
    assert info is not None and info.duration > 0


def test_render_project_uses_cache(tiny_project):
    proj = ProjectConfig.load(tiny_project)
    r1 = renderer.render_project(proj, quality="l", timeout=300)
    assert r1.ok
    assert all(not r.cached for r in r1.results)
    r2 = renderer.render_project(proj, quality="l", timeout=300)
    assert r2.ok
    assert all(r.cached for r in r2.results)


def test_scene_pads_to_declared_duration(tiny_project):
    """A scene holds its final frame until its declared (narration) duration."""
    proj = ProjectConfig.load(tiny_project)
    spec = proj.scenes[0]
    spec.duration = 9.0  # the scene animates for well under a second
    res = renderer.render_scene(proj, spec, quality="l", timeout=300)
    assert res.ok, res.error and res.error.summary()
    info = probe.probe_video(res.path)
    assert info is not None
    # within one frame of the declared duration
    assert abs(info.duration - 9.0) < 0.2, info.duration


def test_assemble_and_qa(tiny_project):
    proj = ProjectConfig.load(tiny_project)
    report = renderer.render_project(proj, quality="l", timeout=300)
    assert report.ok
    files = [r.path for r in report.results]
    out = tiny_project / "build" / "tiny_final.mp4"
    result = assembler.assemble_project(proj, files, output=out)
    assert result.ok, result.message
    assert out.exists()

    qa_result = qa.analyse_video(out)
    assert qa_result is not None
    assert qa_result.n_frames_sampled > 0
    # Every sampled frame must show content.  Scenes reveal their header before
    # anything animates, so there is no blank lead-in frame at a cut; a scene
    # that fades its first mobject in from zero opacity would put one there.
    assert not [f.index for f in qa_result.frames if f.blank], (
        "no sampled frame should be blank — a scene must not open on pure "
        "background"
    )


def _tone(path: Path, seconds: float = 3.0, freq: int = 440) -> Path:
    """A real WAV, so the mux path is exercised against actual audio."""
    import subprocess

    path.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        ["ffmpeg", "-y", "-v", "error", "-f", "lavfi",
         "-i", f"sine=frequency={freq}:duration={seconds}",
         "-ar", "44100", "-ac", "1", str(path)],
        check=True, capture_output=True,
    )
    return path


def test_assemble_with_music_only_produces_audio(tiny_project, tmp_path):
    """Regression: a music bed with no narration used to be silently dropped.

    ``has_audio`` was only set when narration existed, so ffmpeg received the
    music input but no ``-map`` for it: the mux succeeded and the result had no
    audio track at all.
    """
    proj = ProjectConfig.load(tiny_project)
    report = renderer.render_project(proj, quality="l", timeout=300)
    assert report.ok
    files = [r.path for r in report.results]
    bed = _tone(tmp_path / "bed.wav", seconds=3.0)

    out = tmp_path / "music_only.mp4"
    result = assembler.assemble_project(proj, files, music=bed, output=out)
    assert result.ok, result.message
    assert result.has_audio, "music-only assembly produced no audio track"

    info = probe.probe_video(out)
    assert info is not None and info.has_audio
    # the looped bed must be trimmed to the video, not left running longer
    assert abs(info.duration - result.duration) < 0.5


def test_assemble_with_narration_and_music_mixes_both(tiny_project, tmp_path):
    proj = ProjectConfig.load(tiny_project)
    report = renderer.render_project(proj, quality="l", timeout=300)
    assert report.ok
    files = [r.path for r in report.results]
    narr = _tone(tmp_path / "narr.wav", seconds=3.0, freq=220)
    bed = _tone(tmp_path / "bed.wav", seconds=3.0, freq=880)

    out = tmp_path / "both.mp4"
    result = assembler.assemble_project(
        proj, files, narration=narr, music=bed, output=out
    )
    assert result.ok, result.message
    assert result.has_audio
    info = probe.probe_video(out)
    assert info is not None and info.has_audio
