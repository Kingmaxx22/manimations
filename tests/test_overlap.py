"""Tests for the scene self-reported overlap diagnostics.

Pixel-level QA cannot see two mobjects drawn on top of each other: both sit
inside the safe area and both count as "content".  These tests pin the mechanism
that catches it instead — the scene writes its own collision report and the
pipeline reads it back.
"""

from __future__ import annotations

import json
import os
import textwrap
from pathlib import Path

from manim import RIGHT

import pytest

from manimations.config import ProjectConfig
from manimations.pipeline import renderer
from manimations.scene import OVERLAP_ENV


def test_overlap_env_is_not_spec_env():
    """Two distinct channels: the duration spec and the diagnostics sink."""
    from manimations.scene import SPEC_ENV

    assert OVERLAP_ENV != SPEC_ENV


def test_scene_writes_report_when_env_set(tmp_path, monkeypatch):
    """A scene with overlapping content reports the colliding pair."""
    monkeypatch.setenv(OVERLAP_ENV, str(tmp_path / "rep.json"))

    from manim import VGroup
    from manimations import ExplainerScene
    from manimations.components import typography

    class _Overlapping(ExplainerScene):
        def construct(self):
            a = typography.headline("FIRST", size=40)
            b = typography.headline("SECOND", size=40)
            b.move_to(a.get_center())          # deliberately on top
            self.register_content(a)
            self.register_content(b)

    # construct() is wrapped by __init_subclass__ to also emit the report, but
    # that wrapper needs a live Scene; exercise the writer directly.
    scene = _Overlapping.__new__(_Overlapping)
    scene._content = []
    a = typography.headline("FIRST", size=40)
    b = typography.headline("SECOND", size=40)
    b.move_to(a.get_center())
    scene._content = [a, b]
    scene._write_overlap_report()

    report = json.loads((tmp_path / "rep.json").read_text(encoding="utf-8"))
    assert report["n_content"] == 2
    assert report["collisions"], "identical positions must register as a collision"


def test_scene_writes_nothing_without_env(tmp_path, monkeypatch):
    monkeypatch.delenv(OVERLAP_ENV, raising=False)
    from manimations import ExplainerScene

    scene = ExplainerScene.__new__(ExplainerScene)
    scene._content = []
    scene._write_overlap_report()          # must be a silent no-op
    assert not list(tmp_path.iterdir())


def test_write_report_never_raises(tmp_path, monkeypatch):
    """Diagnostics must never fail a render."""
    monkeypatch.setenv(OVERLAP_ENV, str(tmp_path / "nested" / "deep" / "r.json"))
    from manimations import ExplainerScene

    scene = ExplainerScene.__new__(ExplainerScene)
    scene._content = []
    scene._write_overlap_report()          # creates parents, does not raise
    assert (tmp_path / "nested" / "deep" / "r.json").exists()


def test_read_overlap_report_roundtrip(project_dir):
    proj = ProjectConfig.load(project_dir)
    log_dir = proj.qa_dir / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    (log_dir / "01_intro.overlap.json").write_text(
        json.dumps({"collisions": [[0, 1]], "offending": ["Text"], "n_content": 2}),
        encoding="utf-8",
    )
    report = renderer.read_overlap_report(proj, "01_intro")
    assert report is not None
    assert report["collisions"] == [[0, 1]]
    assert report["offending"] == ["Text"]


def test_read_overlap_report_missing_is_none(project_dir):
    proj = ProjectConfig.load(project_dir)
    assert renderer.read_overlap_report(proj, "nope") is None


def test_read_overlap_report_survives_corrupt_file(project_dir):
    proj = ProjectConfig.load(project_dir)
    log_dir = proj.qa_dir / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    (log_dir / "01_intro.overlap.json").write_text("{not json", encoding="utf-8")
    assert renderer.read_overlap_report(proj, "01_intro") is None


def test_renderer_asks_the_scene_for_a_report(project_dir, monkeypatch):
    """The render command must set the env var, or the sidecar never appears."""
    proj = ProjectConfig.load(project_dir)
    seen: dict = {}

    class _Done:
        returncode = 1          # fail fast; we only care about the env
        stdout = ""
        stderr = "SyntaxError: x"

    def fake_run(cmd, capture_output=True, text=True, timeout=None, cwd=None, env=None):
        seen["env"] = env
        return _Done()

    monkeypatch.setattr(renderer.subprocess, "run", fake_run)
    renderer.render_scene(proj, proj.scenes[0], quality="l", max_attempts=1)

    assert seen["env"] is not None
    assert OVERLAP_ENV in seen["env"]
    assert seen["env"][OVERLAP_ENV].endswith("01_intro.overlap.json")


# --------------------------------------------------------------------------
# Neumorphic shadow layers vs safe-area bounds / collision pairs
# --------------------------------------------------------------------------
def test_shadow_layers_do_not_trip_the_safe_area_check():
    """A soft card resting ON the safe-area edge must pass.

    Regression: `surfaces.soft_shadow` copies sit 0.09 units down-right of
    the plate; counting their (5-13% opaque) bounds flagged every neumorphic
    card on the boundary as "outside the safe area".
    """
    from manim import Text

    from manimations.components import surfaces
    from manimations.helpers import layout
    from manimations.theme import set_style

    set_style("neumorphic")
    try:
        card = surfaces.panel(2.0, 1.0)
        assert card.width > 2.0, "shadows must actually extend the bbox"
        card.to_edge(RIGHT, buff=layout.margin_x())  # plate flush to the edge
        assert layout.is_inside_safe_area(card)
        assert layout.offending_mobjects([card]) == []

        # ...but genuinely out-of-bounds content still flags.
        stray = Text("stray").to_edge(RIGHT, buff=-0.5)
        assert not layout.is_inside_safe_area(stray)
        assert layout.offending_mobjects([stray]) != []
    finally:
        set_style("classic")


def test_shadow_grazing_is_not_a_collision():
    """Two cards whose shadow layers only graze each other are not colliding."""
    from manimations.components import surfaces
    from manimations.helpers import layout
    from manimations.theme import set_style

    set_style("neumorphic")
    try:
        a = surfaces.panel(1.0, 1.0)
        b = surfaces.panel(1.0, 1.0)
        b.next_to(a, RIGHT, buff=0.05)  # plate gap 0.05 < shadow reach 0.09
        assert not layout.overlaps(a, b)
        b.next_to(a, RIGHT, buff=-0.2)  # real overlap
        assert layout.overlaps(a, b)
    finally:
        set_style("classic")
