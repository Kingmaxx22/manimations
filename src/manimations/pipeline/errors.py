"""Render error classification and diagnostic capture.

The pipeline must not stop at the first failure: it captures the real Manim
stderr, classifies the failure, and decides whether an automatic retry can
plausibly succeed.  Only *recoverable* failures are retried, and at most three
times per scene (per the spec).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum


class FailureKind(str, Enum):
    SYNTAX = "syntax"
    IMPORT = "import"
    ATTRIBUTE = "attribute"
    TYPE = "type"
    LAYOUT = "layout"
    MISSING_CLASS = "missing_class"
    TIMEOUT = "timeout"
    UNKNOWN = "unknown"


#: Failures where re-running is unlikely to help on its own.
_FATAL = {FailureKind.MISSING_CLASS}

_PATTERNS: list[tuple[FailureKind, re.Pattern[str]]] = [
    (FailureKind.SYNTAX, re.compile(r"SyntaxError|IndentationError")),
    (FailureKind.IMPORT, re.compile(r"ImportError|ModuleNotFoundError")),
    (FailureKind.MISSING_CLASS, re.compile(r"No scenes? (?:matching|named)|is not in the script|no such scene")),
    (FailureKind.ATTRIBUTE, re.compile(r"AttributeError")),
    (FailureKind.TYPE, re.compile(r"TypeError|ValueError")),
    (FailureKind.TIMEOUT, re.compile(r"timed out|TimeoutExpired")),
]


@dataclass
class RenderError:
    """A captured render failure with everything needed to diagnose it."""

    scene_id: str
    kind: FailureKind
    message: str
    returncode: int = 1
    stderr_tail: str = ""
    stdout_tail: str = ""
    attempts: int = 1
    log_path: str | None = None

    @property
    def recoverable(self) -> bool:
        """Whether an automatic retry is worth attempting."""
        return self.kind not in _FATAL

    def summary(self) -> str:
        head = f"[{self.kind.value}] scene {self.scene_id}: {self.message}"
        if self.stderr_tail:
            last = self.stderr_tail.strip().splitlines()[-1]
            head += f" | last stderr: {last[:200]}"
        return head


def classify(stderr: str, stdout: str = "") -> tuple[FailureKind, str]:
    """Map raw render output to a failure kind and a short message."""
    blob = f"{stderr}\n{stdout}"
    for kind, pat in _PATTERNS:
        m = pat.search(blob)
        if m:
            # grab the last exception line for context
            lines = [ln for ln in stderr.strip().splitlines() if ln.strip()]
            msg = lines[-1] if lines else m.group(0)
            return kind, msg.strip()[:300]
    lines = [ln for ln in stderr.strip().splitlines() if ln.strip()]
    return FailureKind.UNKNOWN, (lines[-1][:300] if lines else "render failed")


@dataclass
class RepairLog:
    """Accumulates the story of every failure for one run (actionable logs)."""

    entries: list[RenderError] = field(default_factory=list)

    def add(self, err: RenderError) -> None:
        self.entries.append(err)

    @property
    def failed(self) -> list[RenderError]:
        return [e for e in self.entries if e.attempts >= 3]

    def write(self, path) -> None:
        from pathlib import Path

        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        lines = []
        for e in self.entries:
            lines.append(f"=== scene {e.scene_id} (attempts={e.attempts}, {e.kind.value}) ===")
            lines.append(e.message)
            if e.stderr_tail:
                lines.append("--- stderr ---")
                lines.append(e.stderr_tail)
            if e.stdout_tail:
                lines.append("--- stdout ---")
                lines.append(e.stdout_tail)
            lines.append("")
        path.write_text("\n".join(lines), encoding="utf-8")

    def __len__(self) -> int:
        return len(self.entries)
