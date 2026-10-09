"""Render cache: skip scenes whose inputs have not changed.

The cache key hashes everything that can change a scene's pixels or audio —
the ``scenes.py`` source, ``project.yaml``, the whole framework source tree, the
quality settings, and the narration text.  If the key matches and the output
file still exists, the scene is reused instead of re-rendered.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path

from ..config import ProjectConfig, SceneSpec


@dataclass
class CacheEntry:
    key: str
    path: str
    quality: str
    duration: float
    rendered_at: str


def _hash_file(path: Path, hasher: "hashlib._Hash") -> None:
    if not path.exists():
        hasher.update(b"<missing>")
        return
    hasher.update(path.read_bytes())


def framework_fingerprint() -> str:
    """Hash every ``.py`` in the manimations package (design system + components)."""
    import manimations

    pkg = Path(manimations.__file__).resolve().parent
    hasher = hashlib.sha256()
    for py in sorted(pkg.rglob("*.py")):
        hasher.update(py.name.encode())
        _hash_file(py, hasher)
    return hasher.hexdigest()[:16]


def scene_key(project: ProjectConfig, spec: SceneSpec, quality: str) -> str:
    """Content hash for one scene render."""
    hasher = hashlib.sha256()
    hasher.update(spec.id.encode())
    hasher.update(spec.cls.encode())
    hasher.update(spec.narration.encode("utf-8"))
    hasher.update(quality.encode())
    hasher.update(framework_fingerprint().encode())
    _hash_file(project.scenes_file, hasher)
    _hash_file(project.root / "project.yaml", hasher)
    return hasher.hexdigest()[:20]


class RenderCache:
    """JSON-backed map of scene id -> last successful render."""

    def __init__(self, path: Path):
        self.path = Path(path)
        self._data: dict[str, dict] = {}
        if self.path.exists():
            try:
                self._data = json.loads(self.path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                self._data = {}

    def get(self, scene_id: str) -> CacheEntry | None:
        raw = self._data.get(scene_id)
        if not raw:
            return None
        try:
            return CacheEntry(**raw)
        except TypeError:
            return None

    def is_fresh(self, project: ProjectConfig, spec: SceneSpec, quality: str) -> bool:
        """True when a valid, up-to-date render already exists."""
        entry = self.get(spec.id)
        if entry is None:
            return False
        if entry.key != scene_key(project, spec, quality):
            return False
        return Path(entry.path).exists()

    def record(self, project: ProjectConfig, spec: SceneSpec, quality: str,
               output: Path, duration: float) -> CacheEntry:
        from datetime import datetime, timezone

        entry = CacheEntry(
            key=scene_key(project, spec, quality),
            path=str(output.resolve()),
            quality=quality,
            duration=duration,
            rendered_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        )
        self._data[spec.id] = asdict(entry)
        self.save()
        return entry

    def invalidate(self, scene_id: str) -> None:
        self._data.pop(scene_id, None)
        self.save()

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self._data, indent=2), encoding="utf-8")
