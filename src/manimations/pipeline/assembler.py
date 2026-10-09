"""Video assembly with FFmpeg.

Joins the per-scene renders in the order declared by the brief, optionally muxes
a narration track, mixes a music bed, and burns or attaches subtitles.  Every
step verifies the produced file with ffprobe before reporting success.
"""

from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

from ..config import ProjectConfig
from . import probe


@dataclass
class AssemblyResult:
    ok: bool
    path: Path | None
    width: int = 0
    height: int = 0
    fps: float = 0.0
    duration: float = 0.0
    has_audio: bool = False
    message: str = ""
    parts: list[Path] | None = None


def _run(cmd: list[str], timeout: int = 1800) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)


def concat_scenes(
    project: ProjectConfig,
    scene_files: list[Path],
    dst: Path,
    *,
    reencode: bool = True,
) -> AssemblyResult:
    """Concatenate scene MP4s in order.

    Re-encodes by default so clips rendered at different times/encoders join
    cleanly; ``reencode=False`` uses the fast stream-copy path when all inputs
    share identical parameters.
    """
    scene_files = [Path(p) for p in scene_files]
    missing = [p for p in scene_files if not p.exists()]
    if missing:
        return AssemblyResult(False, None, message=f"missing scene files: {missing}")
    if not scene_files:
        return AssemblyResult(False, None, message="no scene files to assemble")

    dst.parent.mkdir(parents=True, exist_ok=True)
    listing = dst.with_suffix(".concat.txt")
    listing.write_text(
        "\n".join(f"file '{p.resolve().as_posix()}'" for p in scene_files),
        encoding="utf-8",
    )

    if reencode:
        cmd = [
            "ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0",
            "-i", str(listing),
            "-c:v", "libx264", "-preset", "medium", "-crf", "18",
            "-pix_fmt", "yuv420p", "-r", str(project.orient.fps), "-an",
            str(dst),
        ]
    else:
        cmd = [
            "ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0",
            "-i", str(listing), "-c", "copy", str(dst),
        ]
    proc = _run(cmd)
    if proc.returncode != 0 or not dst.exists() or dst.stat().st_size == 0:
        return AssemblyResult(False, None, message=f"ffmpeg concat failed: {proc.stderr[-500:]}")

    info = probe.probe_video(dst)
    if info is None:
        return AssemblyResult(False, None, message="assembled file could not be probed")
    return AssemblyResult(
        True, dst, info.width, info.height, info.fps, info.duration,
        info.has_audio, parts=scene_files,
    )


def mux_audio(
    video: Path,
    narration: Path | None,
    dst: Path,
    *,
    music: Path | None = None,
    music_gain_db: float = -22.0,
    subtitles: Path | None = None,
    burn_subtitles: bool = False,
) -> AssemblyResult:
    """Add narration/music/subtitles to an assembled (silent) video.

    * narration is the primary track
    * music, if given, is looped and mixed underneath at ``music_gain_db``
    * subtitles are embedded as a soft ``mov_text`` track by default, or burned
      in when ``burn_subtitles`` is set (keeps everything in one MP4 either way)
    """
    video = Path(video)
    if not video.exists():
        return AssemblyResult(False, None, message=f"no input video {video}")

    dst.parent.mkdir(parents=True, exist_ok=True)
    cmd = ["ffmpeg", "-y", "-v", "error", "-i", str(video)]
    inputs = 1
    filters: list[str] = []

    has_audio = False
    if narration and Path(narration).exists():
        cmd += ["-i", str(narration)]
        has_audio = True
    if music and Path(music).exists():
        cmd += ["-stream_loop", "-1", "-i", str(music)]

    audio_inputs = []
    if narration and Path(narration).exists():
        audio_inputs.append((1, "narration"))
    if music and Path(music).exists():
        audio_inputs.append((2 if audio_inputs else 1, "music"))

    if has_audio:
        narr_idx = audio_inputs[0][0]
        if len(audio_inputs) > 1:
            music_idx = audio_inputs[1][0]
            filters.append(
                f"[{narr_idx}:a]volume=1.0[narr];"
                f"[{music_idx}:a]volume={music_gain_db}dB[mus];"
                f"[narr][mus]amix=inputs=2:duration=first:dropout_transition=2[aout]"
            )
        else:
            filters.append(f"[{narr_idx}:a]volume=1.0[aout]")

    sub_idx = None
    if subtitles and Path(subtitles).exists() and not burn_subtitles:
        cmd += ["-i", str(subtitles)]
        sub_idx = cmd.count("-i") - 1  # index of the subtitles input

    if burn_subtitles and subtitles and Path(subtitles).exists():
        escaped = str(Path(subtitles).resolve()).replace("\\", "/").replace(":", r"\:")
        filters.append(f"[0:v]subtitles='{escaped}'[vout]")

    if filters:
        cmd += ["-filter_complex", ";".join(filters)]

    if burn_subtitles and subtitles and Path(subtitles).exists():
        cmd += ["-map", "[vout]"]
    else:
        cmd += ["-map", "0:v"]
    if has_audio:
        cmd += ["-map", "[aout]"]
    if sub_idx is not None:
        cmd += ["-map", f"{sub_idx}:s", "-c:s", "mov_text", "-metadata:s:s:0", "language=eng"]

    cmd += ["-c:v", "libx264", "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p"]
    if has_audio:
        # No -shortest here: the narration track is padded to the exact scene
        # total, and a short subtitle stream must not truncate the video.
        cmd += ["-c:a", "aac", "-b:a", "192k"]
    cmd += ["-movflags", "+faststart", str(dst)]

    proc = _run(cmd)
    if proc.returncode != 0 or not dst.exists() or dst.stat().st_size == 0:
        return AssemblyResult(False, None, message=f"ffmpeg mux failed: {proc.stderr[-600:]}")

    info = probe.probe_video(dst)
    if info is None:
        return AssemblyResult(False, None, message="muxed file could not be probed")
    return AssemblyResult(
        True, dst, info.width, info.height, info.fps, info.duration, info.has_audio,
    )


def assemble_project(
    project: ProjectConfig,
    scene_files: list[Path],
    *,
    narration: Path | None = None,
    music: Path | None = None,
    subtitles: Path | None = None,
    burn_subtitles: bool = False,
    output: Path | None = None,
) -> AssemblyResult:
    """Full assembly: concat scenes then optionally mux audio/subtitles.

    Writes to a staging file first and only promotes it to the final name after
    the file probes cleanly, so a previously good export is never clobbered.
    """
    output = Path(output or project.build_dir / project.output_name)
    output.parent.mkdir(parents=True, exist_ok=True)
    staging_video = project.build_dir / f".{project.slug}.scenes.mp4"
    staging_final = project.build_dir / f".{project.slug}.staging.mp4"

    concat = concat_scenes(project, scene_files, staging_video)
    if not concat.ok:
        return concat

    if narration or music or subtitles:
        result = mux_audio(
            staging_video, narration, staging_final, music=music,
            subtitles=subtitles, burn_subtitles=burn_subtitles,
        )
        if not result.ok:
            return result
        source = staging_final
    else:
        source = staging_video

    # Validate before promoting: the muxed file must not have lost frames
    # (e.g. a short subtitle stream truncating the video).
    info = probe.probe_video(source)
    if info is None:
        return AssemblyResult(False, None, message="assembled file could not be probed")
    expected = concat.duration
    if expected > 0 and info.duration < expected - 0.5:
        return AssemblyResult(
            False, None,
            message=(
                f"assembled duration {info.duration:.2f}s is shorter than the "
                f"concatenated scenes ({expected:.2f}s) — refusing to overwrite"
            ),
        )

    shutil.move(str(source), str(output))
    info = probe.probe_video(output)
    if info is None:
        return AssemblyResult(False, None, message="final file could not be probed")
    return AssemblyResult(
        True, output, info.width, info.height, info.fps, info.duration,
        info.has_audio, message="assembled", parts=scene_files,
    )
