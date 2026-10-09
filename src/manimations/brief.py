"""Scene briefs: the structured input that drives a video.

A brief is a list of scenes, each with narration, an approximate duration,
visual elements and animation notes.  This module can:

* validate a brief (reusing :mod:`manimations.config` rules)
* scaffold a brand-new project directory (``project.yaml`` + ``scenes.py`` stub
  + README) from a topic, so a new explainer starts from the framework rather
  than from a blank file
* render a human-readable outline for review

The generated ``scenes.py`` contains real, runnable scene classes built from the
component library — one working placeholder per brief entry — which the author
then fills in.  It is deliberately not pseudo-code.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from .config import ACCENTS, ConfigError, ProjectConfig, SceneSpec

#: A compact starter brief used by ``manimations new`` when none is supplied.
#: Narration is written at a natural speaking pace (~150 wpm) for its duration so
#: the scaffold passes validation out of the box.
DEFAULT_BRIEF: list[dict] = [
    {
        "id": "01_intro",
        "class": "SceneIntro",
        "narration": "Start by naming the topic and saying why it matters, in a couple of sentences that set up the question this video will answer.",
        "duration": 12,
        "accent": "cyan",
        "visuals": ["title-card"],
        "notes": "Title card with the topic name; no diagram yet.",
    },
    {
        "id": "02_concept",
        "class": "SceneConcept",
        "narration": "Explain the core idea here, building the diagram element by element as the narration walks through what each part represents and how it connects.",
        "duration": 12,
        "accent": "violet",
        "visuals": ["diagram"],
        "notes": "Reveal the central diagram element by element.",
    },
    {
        "id": "03_conclusion",
        "class": "SceneConclusion",
        "narration": "Close with the single takeaway you want the viewer to remember, stated plainly and supported by the diagram that is still on screen.",
        "duration": 11,
        "accent": "green",
        "visuals": ["summary"],
        "notes": "Three short takeaways, then settle.",
    },
]

_SLUG_RE = re.compile(r"[^a-z0-9]+")


def slugify(topic: str) -> str:
    return _SLUG_RE.sub("_", topic.lower()).strip("_")[:40] or "explainer"


def title_from_slug(slug: str) -> str:
    return slug.replace("_", " ").strip().title()


@dataclass
class Brief:
    """A validated scene brief for one video."""

    title: str
    slug: str
    scenes: list[SceneSpec] = field(default_factory=list)
    description: str = ""
    voice: str = "alba"

    def validate(self) -> list[str]:
        problems: list[str] = []
        if not self.scenes:
            problems.append("brief has no scenes")
        ids = [s.id for s in self.scenes]
        dupes = {i for i in ids if ids.count(i) > 1}
        if dupes:
            problems.append(f"duplicate scene ids: {sorted(dupes)}")
        for s in self.scenes:
            problems.extend(s.validate())
        return problems

    def outline(self) -> str:
        lines = [f"{self.title}  [{self.slug}]  ({len(self.scenes)} scenes)"]
        for s in self.scenes:
            lines.append(
                f"  {s.id:<18} {s.cls:<22} {s.duration:>5.0f}s  "
                f"{s.word_count:>3} words ({s.wpm:>3.0f} wpm)  accent={s.accent}"
            )
            if s.narration:
                lines.append(f"      \"{s.narration[:90]}{'…' if len(s.narration) > 90 else ''}\"")
        return "\n".join(lines)

    @classmethod
    def from_dict(cls, data: dict) -> "Brief":
        if not isinstance(data, dict):
            raise ConfigError("brief must be a mapping")
        topic = str(data.get("title", "Untitled Explainer"))
        slug = str(data.get("slug", slugify(topic)))
        scenes_raw = data.get("scenes")
        if scenes_raw is None:
            scenes_raw = DEFAULT_BRIEF
        return cls(
            title=topic,
            slug=slug,
            scenes=[SceneSpec.from_dict(s) for s in scenes_raw],
            description=str(data.get("description", "")),
            voice=str(data.get("voice", "alba")),
        )

    @classmethod
    def load(cls, path: str | Path) -> "Brief":
        import yaml

        data = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
        return cls.from_dict(data)


# --------------------------------------------------------------------------
# scaffolding
# --------------------------------------------------------------------------
_YAML_HEADER = """\
# Manimations project brief.
#
# Each scene maps to a class in scenes.py.  Keep narration concise: the
# animation reinforces it, it does not repeat it.  Aim for 105-185 words per
# minute of declared duration.

title: "{title}"
slug: {slug}
description: "{description}"
narration_voice: alba          # any pocket-tts voice name or a path to a wav
subtitle_lang: en
# music: assets/music_bed.mp3  # optional background bed (looped, mixed low)

scenes:
"""


def _yaml_scene(spec: SceneSpec) -> str:
    visuals = ", ".join(spec.visuals)
    narration = spec.narration.replace('"', '\\"')
    notes = spec.notes.replace('"', '\\"')
    return (
        f"  - id: {spec.id}\n"
        f"    class: {spec.cls}\n"
        f"    accent: {spec.accent}\n"
        f"    duration: {spec.duration:g}\n"
        f'    narration: "{narration}"\n'
        f"    visuals: [{visuals}]\n"
        f'    notes: "{notes}"\n'
    )


_SCENES_TEMPLATE = '''\
"""{title} — scene definitions.

Generated by ``manimations new``.  Each class is a runnable scene built from the
shared component library; replace the placeholder bodies with the real visual
explanation.  Run a preview with::

    manimations preview {slug}
"""

from __future__ import annotations

from manim import DOWN, LEFT, RIGHT, UP, FadeIn, FadeOut, VGroup

from manimations import ExplainerScene
from manimations.components import data, network, surfaces, typography
from manimations.helpers import timing


{scenes}

class SceneColdOpen(ExplainerScene):
    """Title card shown before the first narrated scene (optional)."""

    def construct(self) -> None:
        t = self.theme
        card = typography.title_card(
            "{eyebrow}", "{title}",
            accent=t.cyan,
            subtitle="{subtitle}",
        )
        card.move_to([0, 0.2, 0])
        self.register_content(card)
        self.play(FadeIn(card, shift=DOWN * 0.3), run_time=t.motion.medium)
        self.settle(1.0)
'''


def _scene_stub(spec: SceneSpec, *, eyebrow: str = "") -> str:
    """Generate one runnable scene class from a brief entry."""
    accent = spec.accent
    title = spec.notes or spec.id.split("_", 1)[-1].replace("_", " ").title()
    visuals = ", ".join(spec.visuals) or "diagram"
    return f'''\
class {spec.cls}(ExplainerScene):
    """{title}"""

    #: Brief for this scene (narration + intended visuals).
    narration = {spec.narration!r}
    visuals = [{visuals!r}]

    def construct(self) -> None:
        t = self.theme
        self.add_header({title!r}, accent=t.{accent}, index="{spec.id.split('_',1)[0]}")

        # TODO: replace with the real visual explanation for this scene.
        placeholder = surfaces.card(
            {title!r}, {visuals!r},
            accent=t.{accent}, width=8.0,
        )
        placeholder.move_to([0, 0.0, 0])
        self.register_content(placeholder)
        self.play(FadeIn(placeholder, shift=DOWN * 0.2), run_time=t.motion.medium)
        self.settle()
'''


def scaffold_project(
    root: str | Path,
    brief: Brief,
    *,
    overwrite: bool = False,
) -> Path:
    """Create a project directory from a brief; returns the project root."""
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)

    yaml_path = root / "project.yaml"
    scenes_path = root / "scenes.py"
    if not overwrite and (yaml_path.exists() or scenes_path.exists()):
        raise ConfigError(
            f"{root} already contains a project (use overwrite=True to replace)"
        )

    yaml_path.write_text(
        _YAML_HEADER.format(
            title=brief.title, slug=brief.slug, description=brief.description
        )
        + "".join(_yaml_scene(s) for s in brief.scenes),
        encoding="utf-8",
    )

    eyebrow = brief.slug.replace("_", " ").upper()
    body = "\n\n".join(_scene_stub(s) for s in brief.scenes)
    scenes_path.write_text(
        _SCENES_TEMPLATE.format(
            title=brief.title, slug=brief.slug, scenes=body,
            eyebrow=eyebrow, subtitle=brief.description or "An explainer",
        ),
        encoding="utf-8",
    )

    readme = root / "README.md"
    if not readme.exists():
        readme.write_text(
            f"# {brief.title}\n\n"
            f"Generated by `manimations new`.\n\n"
            f"```bash\n"
            f"manimations validate {brief.slug}\n"
            f"manimations preview  {brief.slug}\n"
            f"manimations voiceover {brief.slug}\n"
            f"manimations final    {brief.slug} --voiceover --subtitles\n"
            f"```\n",
            encoding="utf-8",
        )
    return root


def project_from_brief(root: str | Path, brief: Brief) -> ProjectConfig:
    """Materialise a brief and return the loaded project config."""
    root = scaffold_project(root, brief, overwrite=True)
    return ProjectConfig.load(root)
