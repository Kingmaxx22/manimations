"""Narration, music and subtitle processing.

Narration is generated with **pocket-tts** (Kyutai) — a CPU-only, ~100M-parameter
TTS that runs entirely locally, so no cloud service or API key is involved.  The
module degrades gracefully: if pocket-tts or its model weights are unavailable,
``synthesise_narration`` reports the failure instead of pretending to have made
audio.

Everything downstream (padding, concatenation, music bed, subtitles, muxing) is
plain ffmpeg.
"""

from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

from ..config import ProjectConfig, SceneSpec
from . import probe


# --------------------------------------------------------------------------
# narration text hygiene
# --------------------------------------------------------------------------
#: Expand the few symbols a TTS reads poorly so the voice sounds natural.
_READ_ALOUD = {
    "IPv4": "I P version four",
    "IPv6": "I P version six",
    "IP": "I P",
    "IETF": "I E T F",
    "IANA": "I A N A",
    "NAT": "N A T",
    "CIDR": "C I D R",
    "ISP": "I S P",
    "DNS": "D N S",
    "TCP": "T C P",
    "UDP": "U D P",
    "DHCP": "D H C P",
    "TTL": "T T L",
    "LAN": "L A N",
    "WAN": "W A N",
    "&": "and",
    "%": "percent",
    "→": " to ",
}


def normalise_for_tts(text: str) -> str:
    """Make narration friendlier for a speech model without changing meaning."""
    out = text
    for src, dst in _READ_ALOUD.items():
        out = re.sub(rf"(?<![\w]){re.escape(src)}(?![\w])", dst, out)
    out = re.sub(r"\s+", " ", out).strip()
    return out


@dataclass
class NarrationClip:
    scene_id: str
    path: Path | None
    duration: float
    text: str
    ok: bool
    error: str = ""


# --------------------------------------------------------------------------
# pocket-tts
# --------------------------------------------------------------------------
class PocketTTS:
    """Lazy wrapper around pocket-tts' Python API.

    The model (~100M params) and voice state are loaded once and kept in memory
    because ``load_model`` and ``get_state_for_audio_prompt`` are slow.
    """

    def __init__(self, voice: str = "alba", language: str = "english",
                 config_url: str | None = None):
        self.voice = voice
        self.language = language
        self.config_url = config_url
        self._model = None
        self._state = None
        self._sample_rate = 24000

    def available(self) -> tuple[bool, str]:
        try:
            import pocket_tts  # noqa: F401

            return True, "pocket_tts importable"
        except Exception as exc:
            return False, f"pocket-tts not importable: {exc}"

    def _load(self) -> None:
        if self._model is not None:
            return
        from pocket_tts import TTSModel

        kwargs = {}
        if self.config_url:
            kwargs["config"] = self.config_url
        elif self.language and self.language != "english":
            kwargs["language"] = self.language
        self._model = TTSModel.load_model(**kwargs)
        self._sample_rate = getattr(self._model, "sample_rate", 24000)
        self._state = self._model.get_state_for_audio_prompt(self.voice)

    def synthesise(self, text: str, out_wav: Path) -> float:
        """Generate speech for ``text`` into ``out_wav``; returns duration."""
        self._load()
        import numpy as np
        import scipy.io.wavfile

        out_wav.parent.mkdir(parents=True, exist_ok=True)
        audio = self._model.generate_audio(self._state, text)
        arr = audio.detach().cpu().numpy() if hasattr(audio, "detach") else np.asarray(audio)
        arr = np.asarray(arr)
        if arr.dtype != np.int16:
            peak = float(np.max(np.abs(arr))) or 1.0
            arr = (arr / peak * 32767.0 * 0.95).astype(np.int16)
        scipy.io.wavfile.write(str(out_wav), self._sample_rate, arr)
        return probe.probe_audio_duration(out_wav)


# --------------------------------------------------------------------------
# project-level narration
# --------------------------------------------------------------------------
def synthesise_narration(
    project: ProjectConfig,
    *,
    voice: str | None = None,
    language: str = "english",
    config_url: str | None = None,
    only: list[str] | None = None,
    engine: PocketTTS | None = None,
) -> list[NarrationClip]:
    """Generate one WAV per scene.  Missing scenes are reported, not faked."""
    voice = voice or project.narration_voice
    engine = engine or PocketTTS(voice=voice, language=language, config_url=config_url)
    ok, detail = engine.available()
    clips: list[NarrationClip] = []

    for spec in project.scenes:
        if only and spec.id not in only:
            continue
        if not spec.narration.strip():
            clips.append(NarrationClip(spec.id, None, 0.0, "", False, "no narration text"))
            continue
        if not ok:
            clips.append(NarrationClip(spec.id, None, 0.0, spec.narration, False, detail))
            continue
        out = project.audio_dir / f"{spec.id}.wav"
        try:
            text = normalise_for_tts(spec.narration)
            dur = engine.synthesise(text, out)
            clips.append(NarrationClip(spec.id, out, dur, text, dur > 0))
        except Exception as exc:  # pragma: no cover - depends on model
            clips.append(NarrationClip(spec.id, None, 0.0, spec.narration, False, str(exc)))
    return clips


# --------------------------------------------------------------------------
# subtitles (SRT)
# --------------------------------------------------------------------------
def _ts(seconds: float) -> str:
    if seconds < 0:
        seconds = 0
    ms = int(round(seconds * 1000))
    h, ms = divmod(ms, 3_600_000)
    m, ms = divmod(ms, 60_000)
    s, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def _wrap(text: str, width: int = 42) -> str:
    words, lines, cur = text.split(), [], ""
    for w in words:
        if len(cur) + len(w) + 1 > width and cur:
            lines.append(cur)
            cur = w
        else:
            cur = f"{cur} {w}".strip()
    if cur:
        lines.append(cur)
    return "\n".join(lines)


def build_srt(project: ProjectConfig, clips: list[NarrationClip] | None = None,
              *, out_path: Path | None = None) -> Path:
    """Write an SRT aligned to the *assembled video* timeline.

    Cue times come from each scene's declared ``duration`` in the brief, because
    that is exactly how long the rendered scene is (``ExplainerScene.settle()``
    pads every scene to its declared duration).  Using the raw narration length
    instead would drift, since speech is usually shorter than the scene.
    """
    out_path = Path(out_path or project.build_dir / "subtitles.srt")
    out_path.parent.mkdir(parents=True, exist_ok=True)

    entries: list[str] = []
    t = 0.0
    idx = 1
    for spec in project.scenes:
        dur = max(spec.duration, 0.5)
        start, end = t, t + dur
        text = spec.narration.strip()
        if text:
            entries.append(f"{idx}\n{_ts(start)} --> {_ts(end)}\n{_wrap(text)}\n")
            idx += 1
        t = end
    out_path.write_text("\n".join(entries), encoding="utf-8")
    return out_path


# --------------------------------------------------------------------------
# ffmpeg audio helpers
# --------------------------------------------------------------------------
def pad_audio(src: Path, dst: Path, target_duration: float, *, fade: float = 0.25) -> Path | None:
    """Pad or trim ``src`` to exactly ``target_duration`` with tiny fades."""
    if not src.exists():
        return None
    dst.parent.mkdir(parents=True, exist_ok=True)
    filt = (
        f"apad,atrim=0:{target_duration:.3f},"
        f"afade=t=in:st=0:d={fade},"
        f"afade=t=out:st={max(0.0, target_duration - fade):.3f}:d={fade}"
    )
    cmd = [
        "ffmpeg", "-y", "-v", "error", "-i", str(src),
        "-af", filt, "-ar", "44100", "-ac", "1", str(dst),
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    return dst if proc.returncode == 0 and dst.exists() else None


def concat_audio(parts: list[Path], dst: Path) -> Path | None:
    """Concatenate WAV parts in order using the ffmpeg concat demuxer."""
    if not parts:
        return None
    dst.parent.mkdir(parents=True, exist_ok=True)
    listing = dst.with_suffix(".txt")
    listing.write_text(
        "\n".join(f"file '{p.resolve().as_posix()}'" for p in parts),
        encoding="utf-8",
    )
    cmd = [
        "ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0",
        "-i", str(listing), "-c", "copy", str(dst),
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    return dst if proc.returncode == 0 and dst.exists() else None


def build_narration_track(project: ProjectConfig, clips: list[NarrationClip],
                          dst: Path | None = None) -> Path | None:
    """Build a single narration track aligned to the scene timeline.

    Each clip is padded/trimmed to its scene's declared duration so the track
    lines up with the assembled video even when speech is shorter or longer.
    """
    dst = Path(dst or project.audio_dir / "narration.wav")
    parts: list[Path] = []
    for spec in project.scenes:
        clip = next((c for c in clips if c.scene_id == spec.id), None)
        # Always pad/trim to the scene's declared duration, whether or not it has
        # narration, so the track length matches the assembled video exactly.
        target = max(spec.duration, 0.5)
        if clip is None or not clip.ok or clip.path is None:
            # silence placeholder of the right length keeps alignment
            silence = project.audio_dir / f"{spec.id}_silence.wav"
            subprocess.run(
                ["ffmpeg", "-y", "-v", "error", "-f", "lavfi",
                 "-i", "anullsrc=r=44100:cl=mono", "-t",
                 f"{target:.3f}", str(silence)],
                capture_output=True, text=True,
            )
            if silence.exists():
                parts.append(silence)
            continue
        padded = project.audio_dir / f"{spec.id}_pad.wav"
        out = pad_audio(clip.path, padded, target)
        parts.append(out or clip.path)
    return concat_audio(parts, dst)
