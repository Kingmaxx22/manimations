"""Tests for the PNGtuber avatar rig (sprite card + scene integration)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from manim import Group, RoundedRectangle, VGroup

from manimations.components.avatar import AvatarRig, load_config
from manimations.scene import AVATAR_ENV, ExplainerScene

SPRITES = Path(__file__).resolve().parents[1] / "pngtuber"
_REQUIRED = ("idle", "talking", "blink", "gesture", "pointing", "excited")
HAVE_SPRITES = all((SPRITES / f"avatar_{s}.png").exists() for s in _REQUIRED)


def _states() -> dict[str, str]:
    return {s: str(SPRITES / f"avatar_{s}.png") for s in _REQUIRED}


def test_load_config_none_empty_garbage():
    assert load_config(None) is None
    assert load_config("") is None
    assert load_config("{not json") is None
    assert load_config('{"states": 3}') is None
    assert load_config('["idle"]') is None


def test_load_config_valid_payload():
    raw = json.dumps({"states": {"idle": "x.png"}, "default": "idle"})
    assert load_config(raw) == {"states": {"idle": "x.png"}, "default": "idle"}


def test_rig_fails_loud_when_no_sprite_loads(tmp_path):
    with pytest.raises(FileNotFoundError):
        AvatarRig(states={"idle": str(tmp_path / "missing.png")})


@pytest.mark.skipif(not HAVE_SPRITES, reason="pngtuber sprites not present")
def test_rig_structure_and_defaults():
    rig = AvatarRig(_states(), default="talking")
    assert isinstance(rig, Group)
    assert rig.base_state == "talking"
    assert rig._current == "talking"
    # plate is a RoundedRectangle in some style; rig always has sprites stacked
    assert any(isinstance(m, RoundedRectangle) for m in rig.submobjects)
    assert all(img in rig for img in rig.images.values())


@pytest.mark.skipif(not HAVE_SPRITES, reason="pngtuber sprites not present")
def test_rig_talk_cadence_flips_mouth():
    rig = AvatarRig(_states(), default="talking")
    rig.tick(0.35)
    assert rig._current == "idle"  # mouth-closed half of speech cadence
    rig.tick(0.3)
    assert rig._current == "talking"  # t=0.65 -> even step -> mouth open
    assert rig._blink_until < 0  # no blink before the first cadence beat


@pytest.mark.skipif(not HAVE_SPRITES, reason="pngtuber sprites not present")
def test_rig_blinks_when_scheduled():
    rig = AvatarRig(_states(), default="talking")
    rig._next_blink = 0.0  # force an immediate blink
    rig.tick(0.01)
    assert rig._current == "blink"
    assert rig._blink_until > rig._t
    rig.tick(0.3)  # past the blink length
    assert rig._current != "blink"


@pytest.mark.skipif(not HAVE_SPRITES, reason="pngtuber sprites not present")
def test_rig_scene_state_overrides_default():
    rig = AvatarRig(_states(), default="talking", scene_state="pointing")
    assert rig.base_state == "pointing"
    rig.tick(0.1)
    assert rig._current == "pointing"  # non-talking poses hold still


@pytest.mark.skipif(not HAVE_SPRITES, reason="pngtuber sprites not present")
def test_scene_builds_avatar_from_env(monkeypatch):
    payload = json.dumps({"states": _states(), "default": "talking",
                          "state": "pointing"})
    monkeypatch.setenv(AVATAR_ENV, payload)

    class Probe(ExplainerScene):
        def construct(self) -> None:
            pass

    scene = Probe()
    assert scene._avatar is not None
    assert scene._avatar.base_state == "pointing"
    assert scene._avatar in scene.mobjects, "avatar must be in frame 1"
    assert scene._avatar in scene.content_mobjects(), "bounds-checked as chrome"
    # collision pairs stay content-only: the card is chrome, not a diagram
    assert scene._avatar not in scene._content


def test_scene_without_avatar_env(monkeypatch):
    monkeypatch.delenv(AVATAR_ENV, raising=False)

    class Probe(ExplainerScene):
        def construct(self) -> None:
            pass

    scene = Probe()
    assert scene._avatar is None


def test_scene_survives_bad_avatar_payload(monkeypatch):
    monkeypatch.setenv(AVATAR_ENV, "{broken json")

    class Probe(ExplainerScene):
        def construct(self) -> None:
            pass

    scene = Probe()
    assert scene._avatar is None, "a bad payload disables the rig, not the render"