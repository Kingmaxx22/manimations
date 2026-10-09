"""Command-line interface for Manimations.

Commands
--------
``new``          scaffold a project from a topic / brief file
``list``         list available projects
``validate``     pre-flight check of a project (no rendering)
``preview``      fast low-quality render of every scene + contact sheets
``final``        full-quality render, optional voiceover/music/subtitles, assemble
``assemble``     re-assemble existing final renders without re-rendering
``voiceover``    generate narration audio only (pocket-tts)
``subtitles``    build an SRT from the brief / generated narration
``demo``         render the component-library demo scene
``qa``           analyse a rendered video (resolution, fps, blank/edge frames)
``contact-sheet`` build a contact sheet of frames from a video

Projects are addressed by slug (resolved under ``./projects/<slug>``), by
directory path, or by a ``project.yaml`` path.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .config import ConfigError, ProjectConfig
from .pipeline import assembler, audio, probe, qa, renderer, validator

PROJECTS_DIR = Path("projects")

# --------------------------------------------------------------------------
# terminal formatting (no hard dependency on rich/colour)
# --------------------------------------------------------------------------
_USE_COLOR = sys.stdout.isatty()


def _c(text: str, code: str) -> str:
    return f"\033[{code}m{text}\033[0m" if _USE_COLOR else text


def ok(text: str) -> str:
    return _c("✔", "32") + " " + text


def bad(text: str) -> str:
    return _c("✘", "31") + " " + text


def warn(text: str) -> str:
    return _c("!", "33") + " " + text


def hdr(text: str) -> str:
    return _c(text, "1;36")


# --------------------------------------------------------------------------
# project resolution
# --------------------------------------------------------------------------
def resolve_project(ref: str) -> ProjectConfig:
    """Turn a CLI reference into a loaded :class:`ProjectConfig`."""
    p = Path(ref)
    candidates: list[Path] = []
    if p.exists():
        candidates.append(p if p.is_dir() else p.parent)
    candidates.append(PROJECTS_DIR / ref)
    # bare slug search under projects/
    if PROJECTS_DIR.exists():
        for child in PROJECTS_DIR.iterdir():
            if child.is_dir() and child.name == ref:
                candidates.append(child)

    for c in candidates:
        if (c / "project.yaml").exists():
            return ProjectConfig.load(c)
    raise ConfigError(
        f"could not find a project for {ref!r}. Looked in: "
        + ", ".join(str(c) for c in candidates)
        + f". Try 'manimations list'."
    )


# --------------------------------------------------------------------------
# commands
# --------------------------------------------------------------------------
def cmd_new(args: argparse.Namespace) -> int:
    from .brief import Brief, DEFAULT_BRIEF, scaffold_project, slugify

    if args.brief:
        brief = Brief.load(args.brief)
    else:
        topic = args.topic or args.name
        slug = slugify(args.name)
        brief = Brief.from_dict(
            {"title": topic, "slug": slug, "scenes": DEFAULT_BRIEF}
        )
        # retitle the default scenes to the topic slug
        brief.slug = slug
        brief.title = topic

    root = Path(args.dir) if args.dir else PROJECTS_DIR / brief.slug
    if root.exists() and not args.force:
        print(bad(f"{root} already exists (use --force to overwrite)"))
        return 1
    scaffold_project(root, brief, overwrite=args.force)
    print(ok(f"created project at {root}"))
    print(f"  {root / 'project.yaml'}")
    print(f"  {root / 'scenes.py'}")
    print(hdr("\nnext:"))
    print(f"  manimations validate {brief.slug}")
    print(f"  manimations preview  {brief.slug}")
    return 0


def cmd_list(args: argparse.Namespace) -> int:
    if not PROJECTS_DIR.exists():
        print(warn("no projects/ directory yet"))
        return 0
    found = 0
    for child in sorted(PROJECTS_DIR.iterdir()):
        if (child / "project.yaml").exists():
            try:
                proj = ProjectConfig.load(child)
                print(f"  {proj.slug:<20} {proj.title}  ({len(proj.scenes)} scenes, "
                      f"{proj.total_duration:.0f}s)")
                found += 1
            except ConfigError as exc:
                print(warn(f"  {child.name}: {exc}"))
    if not found:
        print(warn("no projects found"))
    return 0


def cmd_validate(args: argparse.Namespace) -> int:
    proj = resolve_project(args.project)
    print(hdr(f"Validating {proj.title} [{proj.slug}]"))
    checks = validator.check_project(proj)
    for chk in checks:
        if chk.ok:
            print("  " + ok(f"{chk.name}: {chk.detail}"))
        elif chk.severity == "warning":
            print("  " + warn(f"{chk.name}: {chk.detail}"))
        else:
            print("  " + bad(f"{chk.name}: {chk.detail}"))
    errs = validator.errors(checks)
    warns = validator.warnings(checks)
    print()
    if errs:
        print(bad(f"{len(errs)} error(s), {len(warns)} warning(s)"))
        return 1
    print(ok(f"valid ({len(warns)} warning(s))"))
    return 0


def _progress_printer(quality: str):
    def _p(scene_id: str, result: renderer.RenderResult) -> None:
        if result.cached:
            print("  " + ok(f"{scene_id}: cached ({result.path.name})"))
        elif result.ok:
            print("  " + ok(f"{scene_id}: {quality} {result.duration:.2f}s "
                           f"({result.attempts} attempt(s))"))
        else:
            assert result.error is not None
            print("  " + bad(result.error.summary()))
    return _p


def cmd_preview(args: argparse.Namespace) -> int:
    proj = resolve_project(args.project)
    print(hdr(f"Preview render — {proj.title}"))
    only = args.scene or None
    report = renderer.render_project(
        proj, quality="l", only=only, use_cache=not args.no_cache,
        max_attempts=args.attempts, progress=_progress_printer("preview"),
    )
    # contact sheets + real frame analysis for quick visual review
    print(hdr("\nContact sheets & frame QA"))
    qa_problems = 0
    for res in report.results:
        if res.ok and res.path:
            sheet = proj.qa_dir / f"{res.scene_id}_sheet.png"
            out = renderer.contact_sheet(res.path, sheet)
            if out:
                print(f"  sheet: {out}")
            analysis = qa.analyse_video(res.path)
            if analysis is not None:
                if analysis.problems:
                    qa_problems += 1
                    for p in analysis.problems:
                        print("  " + warn(f"{res.scene_id}: {p}"))
                else:
                    print("  " + ok(f"{res.scene_id}: {analysis.n_frames_sampled} "
                                   f"frames analysed, layout clean"))
    print()
    print(f"  {len(report.results)} scene(s) in {report.total_seconds:.1f}s")
    if not report.ok:
        print(bad(f"{len(report.failures)} scene(s) failed — see "
                  f"{proj.qa_dir / 'render_errors.txt'}"))
        return 1
    if qa_problems:
        print(warn(f"{qa_problems} scene(s) reported layout warnings (previews still usable)"))
    print(ok("all preview scenes rendered"))
    return 0


def _final_scene_files(proj: ProjectConfig, only: list[str] | None = None) -> list[Path]:
    """Final-quality scene files in brief order."""
    specs = [s for s in proj.scenes if not only or s.id in only]
    files = [proj.final_dir / f"{s.id}.mp4" for s in specs]
    return files


def cmd_final(args: argparse.Namespace) -> int:
    proj = resolve_project(args.project)
    print(hdr(f"Final render — {proj.title}"))
    only = args.scene or None
    report = renderer.render_project(
        proj, quality="h", only=only, use_cache=not args.no_cache,
        max_attempts=args.attempts, progress=_progress_printer("final"),
    )
    if not report.ok:
        print(bad(f"{len(report.failures)} scene(s) failed — see "
                  f"{proj.qa_dir / 'render_errors.txt'}"))
        return 1
    print(ok(f"{len(report.results)} scene(s) rendered in {report.total_seconds:.1f}s"))

    # --- optional narration ------------------------------------------------
    narration_path = None
    clips = []
    if args.voiceover:
        print(hdr("\nNarration (pocket-tts)"))
        clips = audio.synthesise_narration(
            proj, voice=args.voice, language=args.language,
        )
        good = [c for c in clips if c.ok]
        for c in clips:
            if c.ok:
                print("  " + ok(f"{c.scene_id}: {c.duration:.1f}s"))
            else:
                print("  " + warn(f"{c.scene_id}: {c.error}"))
        if good:
            narration_path = audio.build_narration_track(proj, clips)
            if narration_path:
                print(ok(f"narration track: {narration_path}"))
        else:
            print(warn("no narration produced; assembling without voiceover"))

    # --- subtitles ---------------------------------------------------------
    subs = None
    if args.subtitles or args.voiceover:
        subs = audio.build_srt(proj, clips)
        print(ok(f"subtitles: {subs}"))

    # --- music -------------------------------------------------------------
    music = Path(args.music) if args.music else (
        Path(proj.music) if proj.music and Path(proj.music).exists() else None
    )
    if args.music and not music.exists():
        print(warn(f"music file not found: {music}"))
        music = None

    # --- assemble ----------------------------------------------------------
    print(hdr("\nAssembling"))
    result = assembler.assemble_project(
        proj, _final_scene_files(proj, only),
        narration=narration_path, music=music, subtitles=subs,
        burn_subtitles=args.burn_subtitles,
    )
    if not result.ok:
        print(bad(f"assembly failed: {result.message}"))
        return 1
    print(ok(f"final video: {result.path}"))
    print(f"  {result.width}x{result.height} @ {result.fps:g}fps, "
          f"{result.duration:.2f}s, audio={result.has_audio}")

    if not args.no_qa:
        _run_qa(result.path, expect=(1920, 1080, 30))
    return 0


def cmd_assemble(args: argparse.Namespace) -> int:
    proj = resolve_project(args.project)
    print(hdr(f"Assembling — {proj.title}"))
    narration = None
    clips = []
    if args.voiceover:
        clips = audio.synthesise_narration(proj, voice=args.voice, language=args.language)
        narration = audio.build_narration_track(proj, clips)
    subs = audio.build_srt(proj, clips) if (args.subtitles or args.voiceover) else None
    music = Path(args.music) if args.music else None
    result = assembler.assemble_project(
        proj, _final_scene_files(proj), narration=narration, music=music,
        subtitles=subs, burn_subtitles=args.burn_subtitles,
    )
    if not result.ok:
        print(bad(f"assembly failed: {result.message}"))
        return 1
    print(ok(f"final video: {result.path}"))
    print(f"  {result.width}x{result.height} @ {result.fps:g}fps, "
          f"{result.duration:.2f}s, audio={result.has_audio}")
    return 0


def cmd_voiceover(args: argparse.Namespace) -> int:
    proj = resolve_project(args.project)
    print(hdr(f"Narration — {proj.title} (voice={args.voice})"))
    clips = audio.synthesise_narration(
        proj, voice=args.voice, language=args.language, only=args.scene or None,
    )
    okc = 0
    for c in clips:
        if c.ok:
            print("  " + ok(f"{c.scene_id}: {c.duration:.2f}s -> {c.path}"))
            okc += 1
        else:
            print("  " + bad(f"{c.scene_id}: {c.error}"))
    if okc:
        track = audio.build_narration_track(proj, clips)
        if track:
            print(ok(f"narration track: {track}"))
        srt = audio.build_srt(proj, clips)
        print(ok(f"subtitles: {srt}"))
    return 0 if okc else 1


def cmd_subtitles(args: argparse.Namespace) -> int:
    proj = resolve_project(args.project)
    # reuse existing narration if present
    clips = []
    for spec in proj.scenes:
        wav = proj.audio_dir / f"{spec.id}.wav"
        if wav.exists():
            clips.append(audio.NarrationClip(
                spec.id, wav, probe.probe_audio_duration(wav), spec.narration, True))
    srt = audio.build_srt(proj, clips)
    print(ok(f"subtitles: {srt}"))
    return 0


def cmd_demo(args: argparse.Namespace) -> int:
    from . import demo  # noqa: F401  (registers the scene)
    import subprocess

    demo_file = Path(__file__).parent / "demo.py"
    cmd = [
        sys.executable, "-m", "manim", "render", "-q", args.quality,
        "--disable_caching", "--media_dir", str(Path(args.media_dir)),
        str(demo_file), "ComponentDemo",
    ]
    print(hdr("Rendering component demo"))
    proc = subprocess.run(cmd, text=True)
    if proc.returncode != 0:
        print(bad("demo render failed"))
        return proc.returncode
    print(ok("demo rendered"))
    return 0


def _run_qa(video: Path, expect: tuple[int, int, float] | None = None) -> int:
    result = qa.analyse_video(video, expect=expect)
    if result is None:
        print(bad(f"could not analyse {video}"))
        return 1
    print(hdr("\nQuality assurance"))
    print("  " + result.summary())
    report = qa.write_report(result, video.parent / f"{video.stem}_qa.json")
    print(f"  report: {report}")
    if result.problems:
        for p in result.problems:
            print("  " + warn(p))
        return 1
    print("  " + ok("no layout problems detected in sampled frames"))
    return 0


def cmd_qa(args: argparse.Namespace) -> int:
    if args.project:
        return cmd_qa_project(args)
    if not args.video:
        print(bad("provide a video path or --project <slug>"))
        return 2
    expect = None
    if args.expect:
        w, h, fps = args.expect.split(",")
        expect = (int(w), int(h), float(fps))
    return _run_qa(Path(args.video), expect)


def cmd_qa_project(args: argparse.Namespace) -> int:
    """Analyse every rendered scene (preview or final) of a project."""
    proj = resolve_project(args.project)
    base = proj.final_dir if args.final else proj.preview_dir
    files = sorted(base.glob("*.mp4"))
    files = [f for f in files if not f.name.startswith(".")]
    if not files:
        print(bad(f"no renders found in {base} — run 'preview' or 'final' first"))
        return 1
    print(hdr(f"QA — {proj.title} ({'final' if args.final else 'preview'} renders)"))
    total_problems = 0
    for f in files:
        result = qa.analyse_video(f)
        if result is None:
            print("  " + bad(f"{f.name}: could not analyse"))
            total_problems += 1
            continue
        if result.problems:
            total_problems += len(result.problems)
            print("  " + warn(f"{f.name}: {result.summary()}"))
            for p in result.problems:
                print(f"      - {p}")
        else:
            print("  " + ok(f"{f.name}: {result.summary()}"))
    print()
    if total_problems:
        print(warn(f"{total_problems} issue(s) across {len(files)} file(s)"))
        return 1
    print(ok(f"{len(files)} file(s) clean"))
    return 0


def cmd_contact_sheet(args: argparse.Namespace) -> int:
    out = Path(args.output) if args.output else Path(args.video).with_suffix(".sheet.png")
    sheet = renderer.contact_sheet(Path(args.video), out, cols=args.cols, rows=args.rows)
    if sheet is None:
        print(bad("could not build contact sheet"))
        return 1
    print(ok(f"contact sheet: {sheet}"))
    return 0


# --------------------------------------------------------------------------
# parser
# --------------------------------------------------------------------------
def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="manimations",
        description="Automated 2D educational motion-graphics system (Manim CE).",
    )
    sub = p.add_subparsers(dest="command", required=True)

    n = sub.add_parser("new", help="scaffold a new project")
    n.add_argument("name", help="project slug (e.g. ipv6)")
    n.add_argument("--topic", help="human-readable title")
    n.add_argument("--brief", help="YAML brief to use instead of the default")
    n.add_argument("--dir", help="target directory (default projects/<slug>)")
    n.add_argument("--force", action="store_true", help="overwrite an existing project")
    n.set_defaults(func=cmd_new)

    ls = sub.add_parser("list", help="list projects")
    ls.set_defaults(func=cmd_list)

    v = sub.add_parser("validate", help="validate a project without rendering")
    v.add_argument("project")
    v.set_defaults(func=cmd_validate)

    pr = sub.add_parser("preview", help="fast low-quality render of all scenes")
    pr.add_argument("project")
    pr.add_argument("--scene", action="append", help="only this scene id (repeatable)")
    pr.add_argument("--no-cache", action="store_true")
    pr.add_argument("--attempts", type=int, default=renderer.MAX_REPAIR_ATTEMPTS)
    pr.set_defaults(func=cmd_preview)

    fi = sub.add_parser("final", help="full render + assemble")
    fi.add_argument("project")
    fi.add_argument("--scene", action="append")
    fi.add_argument("--no-cache", action="store_true")
    fi.add_argument("--attempts", type=int, default=renderer.MAX_REPAIR_ATTEMPTS)
    fi.add_argument("--voiceover", action="store_true", help="generate narration (pocket-tts)")
    fi.add_argument("--voice", default=None, help="pocket-tts voice name or wav path")
    fi.add_argument("--language", default="english", help="pocket-tts language")
    fi.add_argument("--music", help="background music file (looped, mixed low)")
    fi.add_argument("--subtitles", action="store_true", help="embed subtitles")
    fi.add_argument("--burn-subtitles", action="store_true", help="burn subtitles into video")
    fi.add_argument("--no-qa", action="store_true")
    fi.set_defaults(func=cmd_final)

    asm = sub.add_parser("assemble", help="assemble existing final renders")
    asm.add_argument("project")
    asm.add_argument("--voiceover", action="store_true")
    asm.add_argument("--voice", default=None)
    asm.add_argument("--language", default="english")
    asm.add_argument("--music")
    asm.add_argument("--subtitles", action="store_true")
    asm.add_argument("--burn-subtitles", action="store_true")
    asm.set_defaults(func=cmd_assemble)

    vo = sub.add_parser("voiceover", help="generate narration audio only")
    vo.add_argument("project")
    vo.add_argument("--voice", default=None)
    vo.add_argument("--language", default="english")
    vo.add_argument("--scene", action="append")
    vo.set_defaults(func=cmd_voiceover)

    st = sub.add_parser("subtitles", help="build subtitles from the brief")
    st.add_argument("project")
    st.set_defaults(func=cmd_subtitles)

    dm = sub.add_parser("demo", help="render the component-library demo")
    dm.add_argument("--quality", default="l")
    dm.add_argument("--media-dir", default="build/media")
    dm.set_defaults(func=cmd_demo)

    q = sub.add_parser("qa", help="analyse a rendered video")
    q.add_argument("video", nargs="?")
    q.add_argument("--project", dest="project", help="analyse every scene of a project")
    q.add_argument("--final", action="store_true", help="analyse final renders, not previews")
    q.add_argument("--expect", help="expected W,H,FPS e.g. 1920,1080,30")
    q.set_defaults(func=cmd_qa)

    cs = sub.add_parser("contact-sheet", help="build a contact sheet from a video")
    cs.add_argument("video")
    cs.add_argument("--output")
    cs.add_argument("--cols", type=int, default=3)
    cs.add_argument("--rows", type=int, default=2)
    cs.set_defaults(func=cmd_contact_sheet)

    return p


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except ConfigError as exc:
        print(bad(str(exc)))
        return 2
    except KeyboardInterrupt:
        print(warn("interrupted"))
        return 130


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
