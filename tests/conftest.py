"""Shared pytest fixtures."""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest


@pytest.fixture
def project_dir(tmp_path: Path) -> Path:
    """A minimal valid project on disk."""
    root = tmp_path / "demo"
    root.mkdir()
    (root / "project.yaml").write_text(
        textwrap.dedent(
            """
            title: "Demo Explainer"
            slug: demo
            scenes:
              - id: 01_intro
                class: SceneIntro
                accent: cyan
                duration: 12
                narration: "This is a short introduction to the demo explainer topic and it runs at a natural speaking pace so the validation rules accept it without complaint."
                visuals: [title]
              - id: 02_body
                class: SceneBody
                accent: violet
                duration: 12
                narration: "The body explains the central idea with a diagram that builds up element by element while the narration describes what each part does."
                visuals: [diagram]
            """
        ).strip(),
        encoding="utf-8",
    )
    (root / "scenes.py").write_text(
        textwrap.dedent(
            """
            from manimations import ExplainerScene

            class SceneIntro(ExplainerScene):
                def construct(self):
                    pass

            class SceneBody(ExplainerScene):
                def construct(self):
                    pass
            """
        ).strip(),
        encoding="utf-8",
    )
    return root
