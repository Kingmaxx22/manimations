"""Tests for the ExplainerScene base class (timing, chrome, QA hooks)."""

from __future__ import annotations

import json

import pytest

from manimations.scene import SPEC_ENV, ExplainerScene, SceneBrief, _spec_from_env


def test_spec_from_env_reads_json(monkeypatch):
    monkeypatch.setenv(SPEC_ENV, json.dumps({"id": "01_x", "duration": 12.5, "accent": "amber"}))
    brief = _spec_from_env()
    assert brief is not None
    assert brief.id == "01_x"
    assert brief.duration == 12.5
    assert brief.accent == "amber"


def test_spec_from_env_absent(monkeypatch):
    monkeypatch.delenv(SPEC_ENV, raising=False)
    assert _spec_from_env() is None


def test_spec_from_env_tolerates_garbage(monkeypatch):
    monkeypatch.setenv(SPEC_ENV, "not json at all")
    assert _spec_from_env() is None


def test_subclass_construct_is_wrapped():
    """Every subclass gets its construct wrapped so padding is automatic."""

    class Probe(ExplainerScene):
        def construct(self):
            pass

    assert getattr(Probe.construct, "_manimations_wrapped", False) is True


def test_wrapping_is_idempotent():
    class Probe(ExplainerScene):
        def construct(self):
            pass

    first = Probe.construct
    # re-applying __init_subclass__ must not double-wrap
    ExplainerScene.__init_subclass__.__func__(Probe)
    assert Probe.construct is first


def test_scene_brief_defaults():
    b = SceneBrief()
    assert b.duration == 0.0
    assert b.accent == "cyan"
