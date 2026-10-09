"""Project configuration: load, validate, and expose a typed scene brief.

A topic project is described by a ``project.yaml`` file.  This module turns it
into dataclasses so the rest of the framework never touches raw dicts, and so
the pipeline can validate a brief *before* spending time rendering.

Schema (see ``projects/ipv6/project.yaml`` for a full example)::

    title: "What Is IPv6, and Why Is Adoption So Slow?"
    slug: ipv6
    scenes:
      - id: 01_scarcity
        class: SceneScarcity        # class name in scenes.py
        narration: "..."            # what the voiceover says
        duration: 18                # approximate seconds
        accent: amber
        visuals: [address-block, counter]
        notes: "build the block progressively"
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

#: Accepts ``01_scarcity`` style ids; the class name is supplied separately.
_ID_RE = re.compile(r"^[0-9]{2}_[a-z0-9_]+$")
_CLASS_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")

ACCENTS = ("cyan", "violet", "amber", "green", "rose", "blue", "slate")

#: Words-per-minute band used to sanity-check narration against duration.
WPM_MIN, WPM_MAX = 105, 185


class ConfigError(Exception):
    """Raised when a project brief is structurally invalid."""


@dataclass
class SceneSpec:
    """One scene in the explainer."""

    id: str
    cls: str
    narration: str = ""
    duration: float = 15.0
    accent: str = "cyan"
    visuals: list[str] = field(default_factory=list)
    notes: str = ""

    # --- derived / validation -------------------------------------------
    @property
    def index(self) -> int:
        return int(self.id.split("_", 1)[0])

    @property
    def word_count(self) -> int:
        return len([w for w in re.split(r"\s+", self.narration.strip()) if w])

    @property
    def wpm(self) -> float:
        """Narration pace implied by word count and declared duration."""
        if self.duration <= 0:
            return 0.0
        return self.word_count / (self.duration / 60.0)

    @property
    def suggested_duration(self) -> float:
        """Duration that matches the narration at ~150 wpm (3.5 wps), min 6s."""
        if not self.word_count:
            return self.duration
        return max(6.0, round(self.word_count / 2.5, 1))

    def validate(self) -> list[str]:
        """Return a list of problems; empty means the spec is sound."""
        problems: list[str] = []
        if not _ID_RE.match(self.id):
            problems.append(
                f"scene id {self.id!r} must match NN_name (two digits, lowercase)"
            )
        if not _CLASS_RE.match(self.cls):
            problems.append(f"scene {self.id}: invalid class name {self.cls!r}")
        if self.accent not in ACCENTS:
            problems.append(
                f"scene {self.id}: accent {self.accent!r} not in {ACCENTS}"
            )
        if self.duration <= 0:
            problems.append(f"scene {self.id}: duration must be > 0")
        if self.word_count and not (WPM_MIN <= self.wpm <= WPM_MAX):
            problems.append(
                f"scene {self.id}: narration is {self.wpm:.0f} wpm for "
                f"{self.duration:g}s (aim for {WPM_MIN}-{WPM_MAX}); "
                f"suggested duration ~{self.suggested_duration:g}s"
            )
        return problems

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SceneSpec":
        if not isinstance(data, dict):
            raise ConfigError(f"scene entry must be a mapping, got {type(data).__name__}")
        for required in ("id", "class"):
            if required not in data:
                raise ConfigError(f"scene entry missing required key {required!r}: {data}")
        return cls(
            id=str(data["id"]),
            cls=str(data["class"]),
            narration=str(data.get("narration", "")),
            duration=float(data.get("duration", 15.0)),
            accent=str(data.get("accent", "cyan")),
            visuals=list(data.get("visuals", []) or []),
            notes=str(data.get("notes", "")),
        )


@dataclass
class ProjectConfig:
    """A whole topic project."""

    title: str
    slug: str
    scenes: list[SceneSpec]
    root: Path
    narration_voice: str = "alba"
    music: str | None = None
    subtitle_lang: str = "en"
    author: str = ""
    description: str = ""

    # --- paths -----------------------------------------------------------
    @property
    def scenes_file(self) -> Path:
        return self.root / "scenes.py"

    @property
    def build_dir(self) -> Path:
        return self.root / "build"

    @property
    def preview_dir(self) -> Path:
        return self.build_dir / "preview"

    @property
    def final_dir(self) -> Path:
        return self.build_dir / "final"

    @property
    def audio_dir(self) -> Path:
        return self.build_dir / "audio"

    @property
    def qa_dir(self) -> Path:
        return self.build_dir / "qa"

    @property
    def cache_file(self) -> Path:
        return self.build_dir / "render_cache.json"

    @property
    def output_name(self) -> str:
        return f"{self.slug}_final.mp4"

    def scene_by_id(self, scene_id: str) -> SceneSpec:
        for s in self.scenes:
            if s.id == scene_id:
                return s
        raise KeyError(scene_id)

    @property
    def total_duration(self) -> float:
        return sum(s.duration for s in self.scenes)

    # --- validation ------------------------------------------------------
    def validate(self) -> list[str]:
        problems: list[str] = []
        if not self.title.strip():
            problems.append("project title must not be empty")
        if not self.slug.strip():
            problems.append("project slug must not be empty")
        if not self.scenes:
            problems.append("project has no scenes")
        ids = [s.id for s in self.scenes]
        dupes = {i for i in ids if ids.count(i) > 1}
        if dupes:
            problems.append(f"duplicate scene ids: {sorted(dupes)}")
        order = [s.index for s in self.scenes]
        if order != sorted(order):
            problems.append(f"scenes are not in numeric order: {order}")
        for s in self.scenes:
            problems.extend(s.validate())
        return problems

    @classmethod
    def load(cls, root: str | Path) -> "ProjectConfig":
        """Load ``<root>/project.yaml`` into a :class:`ProjectConfig`."""
        import yaml  # imported lazily so the core works without pyyaml

        root = Path(root).resolve()
        yaml_path = root / "project.yaml"
        if not yaml_path.exists():
            raise ConfigError(f"no project.yaml found in {root}")
        with yaml_path.open("r", encoding="utf-8") as fh:
            data = yaml.safe_load(fh) or {}
        if not isinstance(data, dict):
            raise ConfigError(f"{yaml_path} must contain a mapping at the top level")

        scenes_raw = data.get("scenes", [])
        if not isinstance(scenes_raw, list):
            raise ConfigError("'scenes' must be a list")

        slug = str(data.get("slug", root.name))
        return cls(
            title=str(data.get("title", slug)),
            slug=slug,
            scenes=[SceneSpec.from_dict(s) for s in scenes_raw],
            root=root,
            narration_voice=str(data.get("narration_voice", "alba")),
            music=data.get("music"),
            subtitle_lang=str(data.get("subtitle_lang", "en")),
            author=str(data.get("author", "")),
            description=str(data.get("description", "")),
        )
