"""Tests for the pluggable narration backends (pocket-tts / VoxCPM)."""

from __future__ import annotations

import pytest

from manimations.config import ProjectConfig
from manimations.pipeline import audio


# --------------------------------------------------------------------------
# registry / name resolution
# --------------------------------------------------------------------------
def test_default_engine_is_pocket_tts():
    assert audio.DEFAULT_ENGINE == "pocket-tts"
    assert audio.resolve_engine_name(None) == "pocket-tts"
    assert audio.resolve_engine_name("") == "pocket-tts"


@pytest.mark.parametrize(
    "alias,expected",
    [
        ("pocket", "pocket-tts"),
        ("pocket_tts", "pocket-tts"),
        ("PocketTTS", "pocket-tts"),
        ("vox", "voxcpm"),
        ("VoxCPM", "voxcpm"),
        ("voxcpm", "voxcpm"),
        ("gguf", "voxcpm-gguf"),
        ("vox-gguf", "voxcpm-gguf"),
        ("voxcpm_gguf", "voxcpm-gguf"),
    ],
)
def test_engine_aliases_resolve(alias, expected):
    assert audio.resolve_engine_name(alias) == expected


def test_get_engine_returns_expected_classes():
    assert isinstance(audio.get_engine("pocket-tts"), audio.PocketTTS)
    assert isinstance(audio.get_engine("voxcpm"), audio.VoxCPM)
    assert isinstance(audio.get_engine("voxcpm-gguf"), audio.VoxCPMGGUF)


def test_get_engine_rejects_unknown_name():
    with pytest.raises(ValueError, match="unknown narration engine"):
        audio.get_engine("espeak")


def test_engines_share_the_interface():
    for name in ("pocket-tts", "voxcpm", "voxcpm-gguf"):
        engine = audio.get_engine(name)
        assert isinstance(engine, audio.TTSEngine)
        assert engine.name in ("pocket-tts", "voxcpm", "voxcpm-gguf")
        assert isinstance(engine.available(), tuple)


def test_engine_classes_cover_config_names():
    """Every engine a brief may name must be constructible."""
    from manimations.config import TTS_ENGINES

    for name in TTS_ENGINES:
        assert isinstance(audio.get_engine(name), audio.TTSEngine)


# --------------------------------------------------------------------------
# VoxCPM: how the brief's narration_voice is interpreted
# --------------------------------------------------------------------------
def test_voxcpm_bare_word_is_not_a_description():
    """The pocket-tts default 'alba' must not become a voice-design prompt."""
    engine = audio.VoxCPM(voice="alba")
    assert engine.voice_description == ""
    assert engine.prompt_text("hello") == "hello"


def test_voxcpm_multiword_voice_is_a_description():
    engine = audio.VoxCPM(voice="A young woman, warm and gentle")
    assert engine.voice_description == "A young woman, warm and gentle"
    assert engine.prompt_text("hello") == "(A young woman, warm and gentle)hello"


def test_voxcpm_missing_audio_path_is_not_a_reference(tmp_path):
    engine = audio.VoxCPM(voice=str(tmp_path / "nope.wav"))
    assert engine.reference_wav is None


def test_voxcpm_existing_audio_path_is_a_reference(tmp_path):
    ref = tmp_path / "voice.wav"
    ref.write_bytes(b"RIFF")
    engine = audio.VoxCPM(voice=str(ref))
    assert engine.reference_wav == ref
    # a reference clip suppresses voice-design prompting
    assert engine.voice_description == ""


def test_voxcpm_available_reports_reason_when_missing(monkeypatch):
    import builtins

    real_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name == "voxcpm":
            raise ModuleNotFoundError("No module named 'voxcpm'")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    ok, detail = audio.VoxCPM().available()
    assert ok is False
    assert "voxcpm not importable" in detail


def test_voxcpm_uses_model_override():
    engine = audio.VoxCPM(model="openbmb/VoxCPM1.5")
    assert engine.model_id == "openbmb/VoxCPM1.5"
    assert audio.VoxCPM().model_id == audio.VoxCPM.DEFAULT_MODEL


# --------------------------------------------------------------------------
# project-level integration
# --------------------------------------------------------------------------
def test_project_defaults_to_pocket_tts(project_dir):
    proj = ProjectConfig.load(project_dir)
    assert proj.narration_engine == "pocket-tts"
    assert proj.narration_model is None


def test_project_loads_engine_fields(project_dir):
    yaml_path = project_dir / "project.yaml"
    text = yaml_path.read_text(encoding="utf-8")
    yaml_path.write_text(
        "narration_engine: voxcpm\nnarration_model: openbmb/VoxCPM2\n" + text,
        encoding="utf-8",
    )
    proj = ProjectConfig.load(project_dir)
    assert proj.narration_engine == "voxcpm"
    assert proj.narration_model == "openbmb/VoxCPM2"


def test_project_rejects_unknown_engine(project_dir):
    yaml_path = project_dir / "project.yaml"
    text = yaml_path.read_text(encoding="utf-8")
    yaml_path.write_text("narration_engine: espeak\n" + text, encoding="utf-8")
    proj = ProjectConfig.load(project_dir)
    assert any("narration_engine" in p for p in proj.validate())


class _FakeEngine(audio.TTSEngine):
    """Records the text it was asked to synthesise."""

    name = "fake"
    label = "Fake"

    def __init__(self, fail: bool = False):
        self.calls: list[str] = []
        self.fail = fail

    def available(self) -> tuple[bool, str]:
        return True, "fake"

    def synthesise(self, text: str, out_wav):
        if self.fail:
            raise RuntimeError("boom")
        self.calls.append(text)
        out_wav.parent.mkdir(parents=True, exist_ok=True)
        out_wav.write_bytes(b"RIFF")
        return 1.5


def test_synthesise_narration_uses_injected_engine(project_dir):
    proj = ProjectConfig.load(project_dir)
    engine = _FakeEngine()
    clips = audio.synthesise_narration(proj, engine=engine)
    assert len(clips) == 2
    assert all(c.ok for c in clips)
    assert len(engine.calls) == 2


def test_synthesise_narration_reports_failed_clip(project_dir):
    proj = ProjectConfig.load(project_dir)
    clips = audio.synthesise_narration(proj, engine=_FakeEngine(fail=True))
    assert all(not c.ok for c in clips)
    assert all("boom" in c.error for c in clips)


def test_synthesise_narration_reports_unavailable_engine(project_dir, monkeypatch):
    proj = ProjectConfig.load(project_dir)

    class _Missing(audio.TTSEngine):
        name = "missing"

        def available(self) -> tuple[bool, str]:
            return False, "model weights not downloaded"

        def synthesise(self, text, out_wav):  # pragma: no cover - never reached
            raise AssertionError("should not synthesise")

    clips = audio.synthesise_narration(proj, engine=_Missing())
    assert all(not c.ok for c in clips)
    assert all("model weights not downloaded" in c.error for c in clips)


# --------------------------------------------------------------------------
# VoxCPM: drive the real engine class against a stubbed `voxcpm` module
# --------------------------------------------------------------------------
class _FakeTTSModel:
    sample_rate = 48000


class _FakeVoxCPM:
    """Stands in for voxcpm.VoxCPM: records the call, returns a float waveform."""

    last_kwargs: dict | None = None
    last_model_id: str | None = None

    def __init__(self):
        self.tts_model = _FakeTTSModel()

    @classmethod
    def from_pretrained(cls, model_id, **kwargs):
        cls.last_model_id = model_id
        cls.load_kwargs = kwargs
        return cls()

    def generate(self, **kwargs):
        import numpy as np

        _FakeVoxCPM.last_kwargs = kwargs
        return np.zeros(48000, dtype=np.float32)  # exactly 1s at 48kHz


@pytest.fixture
def fake_voxcpm(monkeypatch):
    """Install a stub `voxcpm` package so the engine can be exercised offline."""
    import sys
    import types

    module = types.ModuleType("voxcpm")
    module.VoxCPM = _FakeVoxCPM
    monkeypatch.setitem(sys.modules, "voxcpm", module)
    _FakeVoxCPM.last_kwargs = None
    _FakeVoxCPM.last_model_id = None
    return module


def test_voxcpm_available_with_stub(fake_voxcpm):
    ok, detail = audio.VoxCPM().available()
    assert ok is True
    assert "voxcpm importable" in detail


def test_voxcpm_synthesise_writes_wav_and_calls_api(fake_voxcpm, tmp_path):
    """End-to-end through the real engine class: correct kwargs, real WAV out."""
    engine = audio.VoxCPM(voice="A calm narrator", seed=7)
    out = tmp_path / "scene.wav"

    duration = engine.synthesise("hello world", out)

    assert out.exists() and out.stat().st_size > 0
    assert duration > 0
    # the voice description reached the model as VoxCPM's "(desc)text" prefix
    assert _FakeVoxCPM.last_kwargs["text"] == "(A calm narrator)hello world"
    assert _FakeVoxCPM.last_kwargs["seed"] == 7
    assert _FakeVoxCPM.last_kwargs["cfg_value"] == 2.0
    assert _FakeVoxCPM.last_kwargs["inference_timesteps"] == 10
    assert "reference_wav_path" not in _FakeVoxCPM.last_kwargs
    # 1 second of 48kHz audio, written as a real mono WAV
    assert duration == pytest.approx(1.0, abs=0.05)


def test_voxcpm_synthesise_passes_reference_clip(fake_voxcpm, tmp_path):
    ref = tmp_path / "voice.wav"
    ref.write_bytes(b"RIFF")
    engine = audio.VoxCPM(voice=str(ref))
    engine.synthesise("clone me", tmp_path / "out.wav")
    assert _FakeVoxCPM.last_kwargs["reference_wav_path"] == str(ref)
    assert _FakeVoxCPM.last_kwargs["text"] == "clone me"  # no design prefix


def test_voxcpm_model_override_reaches_from_pretrained(fake_voxcpm, tmp_path):
    engine = audio.VoxCPM(model="openbmb/VoxCPM1.5")
    engine.synthesise("hi", tmp_path / "out.wav")
    assert _FakeVoxCPM.last_model_id == "openbmb/VoxCPM1.5"


def test_voxcpm_seed_omitted_when_none(fake_voxcpm, tmp_path):
    engine = audio.VoxCPM(seed=None)
    engine.synthesise("hi", tmp_path / "out.wav")
    assert "seed" not in _FakeVoxCPM.last_kwargs


def test_synthesise_narration_end_to_end_with_voxcpm(fake_voxcpm, project_dir):
    """The project path picks VoxCPM up from the brief and produces clips."""
    yaml_path = project_dir / "project.yaml"
    text = yaml_path.read_text(encoding="utf-8")
    yaml_path.write_text("narration_engine: voxcpm\n" + text, encoding="utf-8")

    proj = ProjectConfig.load(project_dir)
    clips = audio.synthesise_narration(proj, engine_name="voxcpm")

    assert len(clips) == 2
    assert all(c.ok for c in clips)
    assert all(c.duration > 0 for c in clips)
    assert _FakeVoxCPM.last_model_id == audio.VoxCPM.DEFAULT_MODEL


# --------------------------------------------------------------------------
# VoxCPMGGUF: the quantized llama.cpp-omni backend (subprocess wrapper)
# --------------------------------------------------------------------------
@pytest.fixture
def fake_cli(tmp_path):
    """A stand-in voxcpm2-cli that writes a real WAV and records its argv.

    Written as a Python script driven by a .bat shim so the test exercises the
    real subprocess boundary (argv order, cwd, exit code) without needing the
    compiled C++ binary.
    """
    argv_log = tmp_path / "argv.txt"
    script = tmp_path / "fake_cli.py"
    script.write_text(
        "import sys, wave, struct, pathlib\n"
        f"pathlib.Path(r'{argv_log}').write_text('\\n'.join(sys.argv[1:]), encoding='utf-8')\n"
        "out = None\n"
        "a = sys.argv[1:]\n"
        "for i, v in enumerate(a):\n"
        "    if v in ('-o', '--output'):\n"
        "        out = a[i+1]\n"
        "if out:\n"
        "    pathlib.Path(out).parent.mkdir(parents=True, exist_ok=True)\n"
        "    with wave.open(out, 'wb') as w:\n"
        "        w.setnchannels(1); w.setsampwidth(2); w.setframerate(48000)\n"
        "        w.writeframes(struct.pack('<%dh' % 48000, *([0]*48000)))\n"
        "sys.exit(0)\n",
        encoding="utf-8",
    )
    bat = tmp_path / "voxcpm2-cli.bat"
    bat.write_text(
        f'@echo off\r\n"{__import__("sys").executable}" "{script}" %*\r\n',
        encoding="utf-8",
    )
    base = tmp_path / "VoxCPM2-BaseLM-Q8_0.gguf"
    acoustic = tmp_path / "VoxCPM2-Acoustic-F16.gguf"
    base.write_bytes(b"GGUF")
    acoustic.write_bytes(b"GGUF")
    return {"bat": bat, "base": base, "acoustic": acoustic, "argv": argv_log}


def test_gguf_available_requires_binary_and_weights(tmp_path):
    engine = audio.VoxCPMGGUF(
        binary=str(tmp_path / "nope.exe"),
        base_lm=str(tmp_path / "nope.gguf"),
    )
    ok, detail = engine.available()
    assert ok is False
    assert "voxcpm2-cli not found" in detail


def test_gguf_available_requires_baselm(fake_cli):
    engine = audio.VoxCPMGGUF(
        binary=str(fake_cli["bat"]),
        base_lm=str(fake_cli["bat"].parent / "missing.gguf"),
    )
    ok, detail = engine.available()
    assert ok is False
    assert "BaseLM GGUF not found" in detail


def test_gguf_available_when_files_exist(fake_cli):
    engine = audio.VoxCPMGGUF(
        binary=str(fake_cli["bat"]),
        base_lm=str(fake_cli["base"]),
        acoustic=str(fake_cli["acoustic"]),
    )
    ok, detail = engine.available()
    assert ok is True
    assert "voxcpm2-cli" in detail


def test_gguf_synthesise_builds_correct_argv(fake_cli, tmp_path):
    """The CLI receives the documented flags and both positional GGUF files."""
    engine = audio.VoxCPMGGUF(
        voice="A calm narrator",
        binary=str(fake_cli["bat"]),
        base_lm=str(fake_cli["base"]),
        acoustic=str(fake_cli["acoustic"]),
        seed=7, cfg_value=2.0, timesteps=10,
    )
    out = tmp_path / "scene.wav"
    duration = engine.synthesise("hello world", out)

    assert out.exists() and out.stat().st_size > 0
    assert duration == pytest.approx(1.0, abs=0.05)

    argv = fake_cli["argv"].read_text(encoding="utf-8").splitlines()
    assert "-t" in argv
    assert argv[argv.index("-t") + 1] == "(A calm narrator)hello world"
    assert argv[argv.index("--seed") + 1] == "7"
    assert argv[argv.index("--cfg") + 1] == "2.0"
    assert argv[argv.index("--timesteps") + 1] == "10"
    # both positional GGUFs, BaseLM first
    positions = [a for a in argv if a.endswith(".gguf")]
    assert positions == [str(fake_cli["base"]), str(fake_cli["acoustic"])]
    # the 4 GB-safe default is applied explicitly
    assert argv[argv.index("--n-gpu-layers") + 1] == str(audio.VoxCPMGGUF.DEFAULT_GPU_LAYERS)


def test_gguf_gpu_layers_zero_forces_cpu(fake_cli, tmp_path):
    engine = audio.VoxCPMGGUF(
        binary=str(fake_cli["bat"]), base_lm=str(fake_cli["base"]),
        acoustic=str(fake_cli["acoustic"]), n_gpu_layers=0,
    )
    engine.synthesise("hi", tmp_path / "out.wav")
    argv = fake_cli["argv"].read_text(encoding="utf-8").splitlines()
    assert argv[argv.index("--n-gpu-layers") + 1] == "0"


def test_gguf_synthesise_passes_reference_clip(fake_cli, tmp_path):
    ref = tmp_path / "voice.wav"
    ref.write_bytes(b"RIFF")
    engine = audio.VoxCPMGGUF(
        voice=str(ref), binary=str(fake_cli["bat"]),
        base_lm=str(fake_cli["base"]), acoustic=str(fake_cli["acoustic"]),
    )
    engine.synthesise("clone me", tmp_path / "out.wav")
    argv = fake_cli["argv"].read_text(encoding="utf-8").splitlines()
    assert argv[argv.index("-r") + 1] == str(ref)
    assert argv[argv.index("-t") + 1] == "clone me"  # no design prefix


def test_gguf_synthesise_raises_on_failure(fake_cli, tmp_path):
    """A non-zero exit must surface as a clear error, not silent success."""
    bad = tmp_path / "bad.bat"
    bad.write_text("@echo off\r\nexit /b 3\r\n", encoding="utf-8")
    engine = audio.VoxCPMGGUF(
        binary=str(bad), base_lm=str(fake_cli["base"]),
        acoustic=str(fake_cli["acoustic"]),
    )
    with pytest.raises(RuntimeError, match="voxcpm2-cli failed"):
        engine.synthesise("hi", tmp_path / "out.wav")


def test_gguf_env_var_overrides(monkeypatch, fake_cli):
    monkeypatch.setenv("MANIMATIONS_VOXCPM_BIN", str(fake_cli["bat"]))
    monkeypatch.setenv("MANIMATIONS_VOXCPM_BASE_LM", str(fake_cli["base"]))
    engine = audio.VoxCPMGGUF()
    assert engine.binary == fake_cli["bat"]
    assert engine.base_lm == fake_cli["base"]


def test_synthesise_narration_with_gguf_engine(fake_cli, project_dir):
    """The project path drives the quantized backend end to end."""
    proj = ProjectConfig.load(project_dir)
    engine = audio.VoxCPMGGUF(
        binary=str(fake_cli["bat"]), base_lm=str(fake_cli["base"]),
        acoustic=str(fake_cli["acoustic"]),
    )
    clips = audio.synthesise_narration(proj, engine=engine)
    assert len(clips) == 2
    assert all(c.ok for c in clips)
