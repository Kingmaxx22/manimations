"""Pre-flight validation: check a project before spending time rendering.

Two layers:

* **static** — scene spec structure, narration pace, required files, and the
  external tools (manim, ffmpeg) the pipeline shells out to.
* **source** — parse ``scenes.py`` to confirm every declared scene class exists.

Both return plain lists of :class:`Check` records so the CLI can print an
actionable report instead of a stack trace.
"""

from __future__ import annotations

import ast
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

from ..config import ProjectConfig


@dataclass
class Check:
    """One validation result."""

    name: str
    ok: bool
    detail: str = ""
    severity: str = "error"  # "error" | "warning"

    def __str__(self) -> str:  # pragma: no cover - display helper
        mark = "OK  " if self.ok else ("WARN" if self.severity == "warning" else "FAIL")
        return f"[{mark}] {self.name}: {self.detail}"


def _which(cmd: str) -> str | None:
    return shutil.which(cmd)


def check_dependencies() -> list[Check]:
    """Verify the external tools the pipeline depends on."""
    checks: list[Check] = []

    try:
        import manim  # noqa: F401

        checks.append(Check("manim", True, f"manim {manim.__version__} importable"))
    except Exception as exc:  # pragma: no cover
        checks.append(Check("manim", False, f"cannot import manim: {exc}"))

    ffmpeg = _which("ffmpeg")
    checks.append(
        Check("ffmpeg", bool(ffmpeg), ffmpeg or "ffmpeg not found on PATH")
    )
    ffprobe = _which("ffprobe")
    checks.append(
        Check("ffprobe", bool(ffprobe), ffprobe or "ffprobe not found on PATH")
    )
    checks.append(
        Check("python", True, f"{sys.version.split()[0]} ({sys.executable})")
    )
    return checks


def check_manim_version() -> Check:
    """Manim must be new enough for the APIs the framework uses."""
    try:
        import manim

        major, minor = (int(x) for x in manim.__version__.split(".")[:2])
        ok = (major, minor) >= (0, 18)
        return Check("manim version", ok, f"{manim.__version__} (need >= 0.18)")
    except Exception as exc:  # pragma: no cover
        return Check("manim version", False, str(exc))


def check_fonts() -> list[Check]:
    """Confirm the theme's font stack resolves on this machine."""
    from ..theme import body_font, heading_font, mono_font

    checks = []
    for name, getter in (("heading font", heading_font),
                         ("body font", body_font),
                         ("mono font", mono_font)):
        try:
            font = getter()
            checks.append(Check(name, True, font))
        except Exception as exc:  # pragma: no cover
            checks.append(Check(name, False, str(exc)))
    return checks


def check_scene_classes(project: ProjectConfig) -> list[Check]:
    """Parse ``scenes.py`` and confirm each declared class is defined."""
    checks: list[Check] = []
    path = project.scenes_file
    if not path.exists():
        return [Check("scenes.py", False, f"missing {path}")]

    try:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    except SyntaxError as exc:
        return [Check("scenes.py syntax", False, f"line {exc.lineno}: {exc.msg}")]

    defined = {
        node.name for node in ast.walk(tree) if isinstance(node, ast.ClassDef)
    }
    for spec in project.scenes:
        ok = spec.cls in defined
        checks.append(
            Check(
                f"class {spec.cls}",
                ok,
                "defined" if ok else f"not found in {path.name}",
            )
        )
    return checks


def check_project(project: ProjectConfig) -> list[Check]:
    """Full validation of a project: spec, files, dependencies, fonts, classes."""
    checks: list[Check] = []

    problems = project.validate()
    checks.append(
        Check(
            "scene brief",
            not problems,
            "valid" if not problems else "; ".join(problems),
        )
    )

    checks.append(Check("project.yaml", True, str(project.root / "project.yaml")))
    checks.append(Check("scenes.py", project.scenes_file.exists(), str(project.scenes_file)))

    checks.extend(check_dependencies())
    checks.append(check_manim_version())
    checks.extend(check_fonts())
    checks.extend(check_scene_classes(project))

    # timing sanity (informational)
    total = project.total_duration
    checks.append(
        Check(
            "total duration",
            total > 0,
            f"{total:.0f}s across {len(project.scenes)} scenes",
            severity="warning" if total > 900 else "error",
        )
    )
    return checks


def errors(checks: list[Check]) -> list[Check]:
    return [c for c in checks if not c.ok and c.severity == "error"]


def warnings(checks: list[Check]) -> list[Check]:
    return [c for c in checks if not c.ok and c.severity == "warning"]
