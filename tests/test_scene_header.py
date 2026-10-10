"""Tests for the persistent scene header.

The header is the first thing every scene draws, so its reveal animation decides
what the very first frame of every scene looks like.  A plain ``FadeIn`` starts
at zero opacity, which means the frame renders as pure background — and since a
scene boundary is exactly where the assembled video cuts, that shipped as a
black flash at the head of every scene (measured on a real render: ~0.14s of
blank frames at each cut).

The pixel assertion renders a real clip, because a synthetic
``camera.capture_mobjects`` call is not a reliable frame: Pango text outlines are
produced at render time, and capturing a lone top-level ``VGroup`` by hand
reports an empty frame even when the same mobject renders correctly.
"""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from manimations import ExplainerScene
from manimations.components import typography


class _HeaderOnly(ExplainerScene):
    def construct(self) -> None:
        self.add_header("The problem", accent=self.theme.rose, index="01")


def test_header_is_in_the_scene_before_it_animates():
    """``add_header`` must put the header on screen at t=0, not only animate it in.

    ``FadeIn`` starts at zero opacity and ``GrowFromEdge`` collapses to a point,
    so either would leave the first frame blank; the header has to be added to
    the scene before its settle-in animation runs.
    """
    scene = _HeaderOnly()
    played = []
    scene.play = lambda *a, **k: played.append(a)  # type: ignore[method-assign]
    scene.construct()

    assert scene._header is not None, "add_header must record the header"
    assert scene._header in scene.mobjects, (
        "the header must be added to the scene immediately, so frame 0 shows it"
    )
    assert played, "the settle-in animation should still run"


def test_scene_header_component_still_builds():
    """The component itself is unchanged by the scene-level fix."""
    h = typography.scene_header("Title", accent="#FB7185", index="01")
    assert len(h) == 3  # bar + title + index


# --------------------------------------------------------------------------
# the pixel-level regression: a real render, sampled at the scene's first frame
# --------------------------------------------------------------------------
@pytest.fixture
def header_project(tmp_path: Path) -> Path:
    """A one-scene project whose only content is the header."""
    root = tmp_path / "hdr"
    root.mkdir()
    (root / "project.yaml").write_text(
        textwrap.dedent(
            """
            title: "Header"
            slug: hdr
            orientation: vertical
            scenes:
              - id: 01_a
                class: SceneA
                accent: rose
                duration: 2
                narration: ""
                visuals: [header]
            """
        ).strip(),
        encoding="utf-8",
    )
    (root / "scenes.py").write_text(
        textwrap.dedent(
            """
            from manimations import ExplainerScene

            class SceneA(ExplainerScene):
                def construct(self):
                    self.add_header("The problem", accent=self.theme.rose,
                                    index="01")
            """
        ).strip(),
        encoding="utf-8",
    )
    return root


@pytest.mark.slow
def test_first_rendered_frame_contains_the_header(header_project):
    """Frame 0 of a real render must show the header, not pure background."""
    import subprocess

    import numpy as np
    from PIL import Image

    from manimations.config import ProjectConfig
    from manimations.pipeline import renderer

    proj = ProjectConfig.load(header_project)
    res = renderer.render_scene(proj, proj.scenes[0], quality="l", timeout=300)
    assert res.ok, res.error and res.error.summary()

    png = header_project / "build" / "frame0.png"
    png.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        ["ffmpeg", "-y", "-v", "error", "-i", str(res.path),
         "-vframes", "1", str(png)],
        check=True, capture_output=True,
    )

    arr = np.asarray(Image.open(png).convert("RGB")).astype(int)
    bg = arr[0, 0]
    non_bg = int((np.abs(arr - bg).sum(axis=2) > 24).sum())
    assert non_bg > 200, (
        f"frame 0 of the scene is blank ({non_bg} non-background pixels); the "
        f"header must be visible without a fade from zero opacity"
    )
