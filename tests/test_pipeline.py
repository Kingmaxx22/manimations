"""Tests for the pipeline: validation, caching, error handling, probing."""

from __future__ import annotations

from pathlib import Path

import pytest

from manimations.config import ProjectConfig
from manimations.pipeline import cache, errors, probe, validator


def test_check_project_passes_for_valid_project(project_dir):
    proj = ProjectConfig.load(project_dir)
    checks = validator.check_project(proj)
    assert not validator.errors(checks)


def test_check_scene_classes_detects_missing(project_dir):
    proj = ProjectConfig.load(project_dir)
    proj.scenes[0].cls = "DoesNotExist"
    checks = validator.check_scene_classes(proj)
    assert any(not c.ok and "DoesNotExist" in c.name for c in checks)


def test_check_scene_classes_detects_syntax_error(project_dir):
    proj = ProjectConfig.load(project_dir)
    proj.scenes_file.write_text("def broken(:\n", encoding="utf-8")
    checks = validator.check_scene_classes(proj)
    assert checks and not checks[0].ok


def test_check_dependencies_reports_manim_and_ffmpeg():
    checks = validator.check_dependencies()
    names = {c.name for c in checks}
    assert {"manim", "ffmpeg", "ffprobe", "python"} <= names


def test_scene_key_changes_with_narration(project_dir):
    proj = ProjectConfig.load(project_dir)
    k1 = cache.scene_key(proj, proj.scenes[0], "l")
    proj.scenes[0].narration = "completely different narration text here"
    k2 = cache.scene_key(proj, proj.scenes[0], "l")
    assert k1 != k2


def test_scene_key_changes_with_quality(project_dir):
    proj = ProjectConfig.load(project_dir)
    assert cache.scene_key(proj, proj.scenes[0], "l") != cache.scene_key(
        proj, proj.scenes[0], "h"
    )


def test_cache_roundtrip_and_freshness(project_dir, tmp_path):
    proj = ProjectConfig.load(project_dir)
    c = cache.RenderCache(tmp_path / "cache.json")
    out = tmp_path / "scene.mp4"
    out.write_bytes(b"fake")
    assert not c.is_fresh(proj, proj.scenes[0], "l")
    c.record(proj, proj.scenes[0], "l", out, duration=1.0)
    assert c.is_fresh(proj, proj.scenes[0], "l")
    # removing the file invalidates freshness
    out.unlink()
    assert not c.is_fresh(proj, proj.scenes[0], "l")


def test_cache_invalidate(project_dir, tmp_path):
    proj = ProjectConfig.load(project_dir)
    c = cache.RenderCache(tmp_path / "cache.json")
    out = tmp_path / "s.mp4"
    out.write_bytes(b"x")
    c.record(proj, proj.scenes[0], "l", out, 1.0)
    c.invalidate(proj.scenes[0].id)
    assert c.get(proj.scenes[0].id) is None


@pytest.mark.parametrize(
    "stderr,expected",
    [
        ("  File x, line 1\nSyntaxError: bad", errors.FailureKind.SYNTAX),
        ("ModuleNotFoundError: No module named 'foo'", errors.FailureKind.IMPORT),
        ("AttributeError: 'X' object has no attribute 'y'", errors.FailureKind.ATTRIBUTE),
        ("TypeError: unsupported operand", errors.FailureKind.TYPE),
        ("No scenes named 'Foo' in the script", errors.FailureKind.MISSING_CLASS),
    ],
)
def test_error_classification(stderr, expected):
    kind, _ = errors.classify(stderr)
    assert kind is expected


def test_missing_class_is_not_recoverable():
    err = errors.RenderError("01_x", errors.FailureKind.MISSING_CLASS, "nope")
    assert not err.recoverable
    err2 = errors.RenderError("01_x", errors.FailureKind.TYPE, "bad")
    assert err2.recoverable


def test_repair_log_writes(project_dir, tmp_path):
    log = errors.RepairLog()
    log.add(errors.RenderError("01_x", errors.FailureKind.TYPE, "boom", stderr_tail="tb"))
    out = tmp_path / "errs.txt"
    log.write(out)
    assert "boom" in out.read_text(encoding="utf-8")


def test_probe_missing_file_returns_none(tmp_path):
    assert probe.probe_video(tmp_path / "nope.mp4") is None


def test_probe_audio_missing_returns_zero(tmp_path):
    assert probe.probe_audio_duration(tmp_path / "nope.wav") == 0.0


def test_have_ffmpeg():
    assert probe.have_ffmpeg() is True
