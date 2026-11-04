"""PNGtuber avatar rig: a sprite card that reacts while the scene plays.

The sprite pack lives in ``pngtuber/`` (repo-level, outside both the
framework and topic projects).  Projects opt in through an ``avatar:`` block
in ``project.yaml``; the render pipeline resolves the paths and hands the rig
a JSON payload through the ``MANIMATIONS_AVATAR`` environment variable, so
the framework never imports project or repo paths itself.

States come from the project (``idle``, ``talking``, ``blink``, ``gesture``,
``pointing``, ``excited`` — whatever the pack provides).  The rig:

* flips between ``talking`` and ``idle`` at speech cadence while the base
  state is ``talking`` (mouth open/close),
* blinks ``blink`` for a short beat every few seconds when that state exists,
* bobs gently the whole time,
* never fails a render: a missing file or bad payload disables the rig with a
  warning instead of aborting.
"""

from __future__ import annotations

import json
import math
import random
from pathlib import Path

from manim import DOWN, RIGHT, Group, ImageMobject, RoundedRectangle

from ..theme import THEME, _active_orientation

#: Seconds per mouth flip while "talking".
TALK_INTERVAL = 0.30
#: Blink cadence (drawn from this range) and blink length, seconds.
BLINK_EVERY = (2.6, 4.6)
BLINK_LEN = 0.16
#: Gentle vertical bob amplitude / frequency.
BOB_AMP = 0.035
BOB_HZ = 0.55
#: Card width as a fraction of the frame width (capped in scene units).
CARD_WIDTH_FRACTION = 0.34
CARD_WIDTH_MAX = 1.6
CARD_WIDTH_MIN = 1.1
CARD_PAD = 0.10


def load_config(raw: str | None) -> dict | None:
    """Parse the ``MANIMATIONS_AVATAR`` payload; ``None`` means no avatar."""
    if not raw:
        return None
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        print("warning: avatar payload is not JSON; avatar disabled")
        return None
    if not isinstance(data, dict) or not isinstance(data.get("states"), dict):
        print("warning: avatar payload has no 'states' mapping; avatar disabled")
        return None
    return data


class AvatarRig(Group):
    """A framed sprite card with talk/blink behaviour.

    All sprites are loaded once and stacked; visibility flips between them,
    so the rig's footprint never changes and QA bounds stay stable.
    (``Group``, not ``VGroup``: it mixes ImageMobjects with vector plates.)
    """

    def __init__(self, states: dict[str, str], default: str = "talking",
                 scene_state: str = "") -> None:
        super().__init__()
        images: dict[str, ImageMobject] = {}
        for name, raw_path in states.items():
            path = Path(raw_path)
            if not path.exists():
                print(f"warning: avatar state {name!r}: missing {path}; skipped")
                continue
            try:
                images[name] = ImageMobject(str(path))
            except Exception as exc:  # unreadable/corrupt file
                print(f"warning: avatar state {name!r}: {exc}; skipped")
        if not images:
            raise FileNotFoundError("no avatar sprite could be loaded")

        base = scene_state or default
        if base not in images:
            base = default if default in images else next(iter(images))
        self.base_state = base
        self.images = images

        # Fit: sprite is 458x384; scale by width, keep aspect.  The card
        # fraction adapts to the frame so it works in 9:16 and 16:9.
        frame_w = _active_orientation().frame_width
        card_w = min(max(frame_w * CARD_WIDTH_FRACTION, CARD_WIDTH_MIN), CARD_WIDTH_MAX)
        sprite_w = card_w - 2 * CARD_PAD
        for img in images.values():
            img.scale(sprite_w / img.width)

        sprite = images[base]
        plate = RoundedRectangle(
            width=card_w, height=sprite.height + 2 * CARD_PAD,
            corner_radius=0.22 if THEME.is_neumorphic else 0.16,
            fill_color=THEME.surface, fill_opacity=1.0,
            stroke_color=THEME.border, stroke_width=1.6,
        )
        # Build: shadows (if any) under the plate, sprites on top.
        from .surfaces import soft_shadow

        self.add(*soft_shadow(plate), plate)
        for img in images.values():
            img.move_to(plate.get_center())
            self.add(img)

        self._plate = plate
        self._t = 0.0
        self._next_blink = random.uniform(*BLINK_EVERY)
        self._blink_until = -1.0
        self._current = ""
        self._anchor = None
        self._apply_state(base)

    # ------------------------------------------------------------------
    def _apply_state(self, state: str) -> None:
        if state == self._current:
            return
        self._current = state
        for name, img in self.images.items():
            img.set_opacity(1.0 if name == state else 0.0)

    def place(self, *, slack: float = 0.12) -> "AvatarRig":
        """Anchor the rig bottom-right, inside the safe area.

        Buffs come from the orientation-aware safe margins (7% of frame),
        plus slack for the neumorphic shadow layers, which extend down-right
        beyond the plate and count toward the rig's bounds.  Also records the
        anchor the bob re-centres around, so positioning must happen before
        ticking starts.
        """
        from ..helpers import layout

        self.to_edge(RIGHT, buff=layout.margin_x() + slack)
        self.to_edge(DOWN, buff=layout.margin_y() + slack)
        self._anchor = self.get_center().copy()
        return self

    def start(self) -> None:
        """Begin ticking (standalone use; the scene wires its own updater).

        Manim invokes time-based updaters as ``updater(mobject, dt)``, so the
        bound method is wrapped to keep :meth:`tick`'s plain-dt signature.
        """
        if self._anchor is None:
            self._anchor = self.get_center().copy()
        self.add_updater(lambda _mobj, dt: self.tick(dt))

    def tick(self, dt: float) -> None:
        """Advance talk/blink/bob state by ``dt`` seconds."""
        self._t += dt
        state = self.base_state

        if (state == "talking" and "idle" in self.images
                and int(self._t // TALK_INTERVAL) % 2 == 1):
            state = "idle"  # mouth-closed half of the speech cadence

        if ("blink" in self.images and state != "blink"
                and self._t >= self._next_blink):
            self._blink_until = self._t + BLINK_LEN
            self._next_blink = self._t + random.uniform(*BLINK_EVERY)
        if self._t < self._blink_until:
            state = "blink"

        self._apply_state(state)

        # Bob: absolute repositioning from the anchor (no drift).
        if self._anchor is not None:
            offset = BOB_AMP * math.sin(self._t * 2 * math.pi * BOB_HZ)
            self.move_to([self._anchor[0], self._anchor[1] + offset, 0])