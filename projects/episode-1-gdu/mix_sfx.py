"""Build the gdu short's final audio: narration + timed sound effects.

The pipeline mixes one background bed, but a Short needs *placed* cues — a
whoosh on the scene transitions and a key clack when the command is typed.  This
script derives the cue times from the rendered scene durations (so it stays
correct when narration fitting changes them) and mixes everything with ffmpeg.

Each effect is **peak-normalised before mixing**.  The Freesound previews come
back at wildly different levels (measured: one whoosh at -26.5 dB peak, another
at -5.0 dB), so a fixed per-cue gain makes the quiet ones inaudible — which is
exactly what happened on the first attempt, where three of the seven cues
vanished under the narration.  Normalising first, then applying a *relative*
gain, makes the mix independent of what the sources happen to be.

Run from the repo root, after `manimations final gdu --orientation vertical`:

    uv run python projects/episode-1-gdu/mix_sfx.py
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
BUILD = ROOT / "build"
SFX = ROOT / "assets" / "sfx"

#: Peak level each kind of effect is normalised to before its relative gain.
#: Whooshes sit back so they never mask a word; key clacks are short transients
#: and can afford to be a little hotter.
TARGET_PEAK_DB = {"whoosh": -9.0, "click": -11.0}

#: (scene_id, offset_within_scene, file, kind, relative_gain_db)
#: Scene-relative so the cues survive narration re-fitting.
CUES = [
    ("01_hook", 0.15, "whoosh2_wav.mp3", "whoosh", 0.0),
    ("03_solution", 0.05, "whoosh2_wav.mp3", "whoosh", 0.0),
    ("03_solution", 0.62, "wkey_wav.mp3", "click", 2.0),
    ("03_solution", 0.78, "spacebarkey_wav.mp3", "click", 2.0),
    ("04_features", 0.55, "wkey_wav.mp3", "click", 0.0),
    ("04_features", 1.35, "wkey_wav.mp3", "click", 0.0),
    ("05_outro", 0.05, "whoosh_1.mp3", "whoosh", 0.0),
]

_PEAK_RE = re.compile(r"max_volume:\s*(-?[\d.]+)\s*dB")


def _scene_durations() -> dict[str, float]:
    """Per-scene durations from the rendered final clips (source of truth)."""
    out: dict[str, float] = {}
    for mp4 in sorted((BUILD / "final").glob("*.mp4")):
        if mp4.name.startswith("."):
            continue
        probe = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", str(mp4)],
            capture_output=True, text=True,
        )
        try:
            out[mp4.stem] = float(probe.stdout.strip())
        except ValueError:
            continue
    return out


def peak_db(path: Path) -> float:
    """Measured peak level of an audio file in dBFS (0.0 when unreadable)."""
    proc = subprocess.run(
        ["ffmpeg", "-v", "info", "-i", str(path), "-af", "volumedetect",
         "-f", "null", "-"],
        capture_output=True, text=True,
    )
    m = _PEAK_RE.search(proc.stderr or "")
    return float(m.group(1)) if m else 0.0


def _narration() -> Path:
    p = BUILD / "audio" / "narration.wav"
    if not p.exists():
        sys.exit(f"no narration track at {p} — run `manimations final gdu --voiceover` first")
    return p


def main() -> int:
    durations = _scene_durations()
    if not durations:
        sys.exit("no rendered scenes in build/final — run `manimations final gdu` first")

    starts: dict[str, float] = {}
    t = 0.0
    for sid in sorted(durations):
        starts[sid] = t
        t += durations[sid]
    total = t
    print(f"  timeline: {total:.2f}s across {len(durations)} scenes")

    inputs = ["-i", str(_narration())]
    filters: list[str] = []
    mix_labels = ["[narr]"]

    n = 1
    for scene_id, offset, filename, kind, rel in CUES:
        src = SFX / filename
        if not src.exists():
            print(f"  ! missing cue source {src.name}, skipping")
            continue
        if scene_id not in starts:
            print(f"  ! unknown scene {scene_id}, skipping")
            continue
        measured = peak_db(src)
        gain = TARGET_PEAK_DB[kind] - measured + rel
        at = starts[scene_id] + offset
        inputs += ["-i", str(src)]
        delay = int(at * 1000)
        # aformat=mono: narration is mono and the effects are stereo, so amix
        # would otherwise mix inconsistent channel layouts.
        filters.append(
            f"[{n}:a]aformat=channel_layouts=mono,volume={gain:.1f}dB,"
            f"adelay={delay}|{delay},apad,atrim=0:{total:.3f}[c{n}]"
        )
        mix_labels.append(f"[c{n}]")
        print(f"  cue {filename:22} {kind:6} at {at:6.2f}s  "
              f"(source {measured:+6.1f}dB -> gain {gain:+6.1f}dB)")
        n += 1

    if len(mix_labels) == 1:
        sys.exit("no cues could be placed")

    # Two-stage mix, and the staging is load-bearing.
    #
    # Feeding all eight streams to a single `amix` silently loses the last cue:
    # measured on this project, a 7-effect + narration amix produced the outro
    # whoosh at RMS 95 instead of 2660, while any *pair* of the same branches
    # mixed correctly at ~2650. Summing the effects into one bed first and then
    # mixing that single bed against the narration is both correct and cheaper.
    filters.insert(0, f"[0:a]aformat=channel_layouts=mono,volume=1.0,"
                      f"apad,atrim=0:{total:.3f}[narr]")
    cue_labels = "".join(mix_labels[1:])
    filters.append(f"{cue_labels}amix=inputs={len(mix_labels) - 1}:"
                   f"duration=longest:normalize=0[sfx]")
    filters.append("[narr][sfx]amix=inputs=2:duration=first:normalize=0[aout]")

    dst = BUILD / "gdu_with_sfx.m4a"
    cmd = ["ffmpeg", "-y", "-v", "error", *inputs,
           "-filter_complex", ";".join(filters),
           "-map", "[aout]", "-c:a", "aac", "-b:a", "192k", str(dst)]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        sys.exit(f"ffmpeg failed: {proc.stderr[-800:]}")
    print(f"  mixed audio -> {dst}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
