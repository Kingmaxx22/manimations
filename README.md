# Manimations

An automated **2D educational motion-graphics system** built on
[Manim Community Edition](https://www.manim.community/). Give it a topic and a
structured scene brief, and it produces a complete, narrated 1920×1080 explainer
video — rendering, repair, assembly, voiceover and subtitles included.

It ships with a reusable visual component library, a design system, a
multi-stage rendering pipeline with error recovery, and a finished example
project: **“What Is IPv6, and Why Is Adoption So Slow?”**

Everything is free and local: Manim + FFmpeg + [pocket-tts](https://github.com/kyutai-labs/pocket-tts)
(a CPU-only text-to-speech model). No cloud services, no API keys, no subscriptions.

---

## Contents

- [Quick start](#quick-start)
- [What it produces](#what-it-produces)
- [Project layout](#project-layout)
- [The design system](#the-design-system)
- [The component library](#the-component-library)
- [Scene briefs](#scene-briefs)
- [The production pipeline](#the-production-pipeline)
- [Command reference](#command-reference)
- [Making a new explainer](#making-a-new-explainer)
- [The IPv6 example](#the-ipv6-example)
- [Quality assurance](#quality-assurance)
- [Testing](#testing)
- [Troubleshooting](#troubleshooting)

See also [`docs/writing-a-scene.md`](docs/writing-a-scene.md) for a practical
guide to turning narration into a diagram, and [`examples/dns_brief.yaml`](examples/dns_brief.yaml)
for a ready-to-scaffold second explainer.

---

## Quick start

Requires Python ≥ 3.10 and FFmpeg on your `PATH`.

```bash
# 1. install (uv is recommended; pip works too)
uv sync --extra tts          # or: pip install -e ".[tts]"

# 2. check the environment and the example project
uv run manimations validate ipv6

# 3. fast preview render of every scene (480p) + contact sheets + frame QA
uv run manimations preview ipv6

# 4. full-quality render (1920x1080 @ 30fps), narration, subtitles, assembly
uv run manimations final ipv6 --voiceover --subtitles
```

The finished video lands at `projects/ipv6/build/ipv6_final.mp4`.

> `uv run` is only needed if you installed with `uv`. With `pip install -e .`
> the `manimations` console script is on your `PATH` directly.

The `tts` extra is optional — omit it and everything works except `--voiceover`
(narration is skipped with a clear message rather than failing).

---

## What it produces

- **1920 × 1080 landscape MP4 at 30 fps**, H.264 + AAC, `+faststart`.
- One MP4 per scene, preserved for debugging, plus the concatenated final cut.
- Contact sheets (PNG) of evenly spaced frames per scene for fast review.
- A JSON QA report per video: resolution, fps, duration, blank-frame and
  edge-clipping analysis of the *actual rendered pixels*.
- Optional narration (per-scene WAV + a single aligned track), an SRT subtitle
  file, and an optional looped music bed mixed low under the voice.

---

## Project layout

```
manimations/
├── pyproject.toml                # deps + the `manimations` console script
├── src/manimations/              # ← the reusable framework
│   ├── theme.py                  # design tokens → Manim config (palette, type, motion)
│   ├── config.py                 # project.yaml → typed dataclasses + validation
│   ├── brief.py                  # scene-brief schema + project scaffolding
│   ├── scene.py                  # ExplainerScene base class (chrome, QA hooks)
│   ├── demo.py                   # component-library demo scene
│   ├── cli.py                    # the command-line interface
│   ├── components/               # ← the visual component library
│   │   ├── typography.py         #   titles, headings, emphasis, labels
│   │   ├── surfaces.py           #   cards, panels, connectors, callouts
│   │   ├── network.py            #   nodes, routers, links, packets, address blocks
│   │   ├── data.py               #   counters, timelines, comparisons, meters
│   │   └── transitions.py        #   dissolves, slides, morphs
│   ├── helpers/
│   │   ├── timing.py             #   easing curves + staggered reveals
│   │   └── layout.py             #   safe areas, grids, clipping/collision checks
│   └── pipeline/
│       ├── validator.py          #   pre-flight checks (deps, fonts, classes, brief)
│       ├── renderer.py           #   preview → repair → final, contact sheets
│       ├── errors.py             #   failure classification + repair log
│       ├── cache.py              #   content-hash cache (skip unchanged scenes)
│       ├── qa.py                 #   real pixel analysis of rendered frames
│       ├── probe.py              #   ffprobe/ffmpeg wrappers
│       ├── assembler.py          #   concat + mux (ffmpeg)
│       └── audio.py              #   pocket-tts narration, music, SRT subtitles
├── projects/
│   ├── ipv6/                     # ← the finished example project
│   │   ├── project.yaml          #   the scene brief
│   │   └── scenes.py             #   7 real, rendered scenes
│   └── _template/                # ← copy this to start a new topic
└── tests/                        # unit + end-to-end (real render) tests
```

Topic content lives entirely under `projects/<slug>/`. The framework never
imports a project; projects import the framework. Adding a topic never means
editing animation code.

---

## The design system

Defined once in `src/manimations/theme.py` and applied automatically by
`ExplainerScene`:

| Token | Value |
| --- | --- |
| Canvas | 1920 × 1080, 30 fps, 16:9 |
| Background | `#0B1220` (dark navy) |
| Surfaces | `#141E33` / `#1B2740` / `#22304C` |
| Text | `#F2F6FC` primary, `#A9B8D4` secondary, `#6C7E9E` muted |
| Accents | cyan `#22D3EE`, violet `#8B7BFF`, amber `#FBBF24`, green `#34D399`, rose `#FB7185`, blue `#60A5FA` |
| Type | Segoe UI / Inter / DejaVu Sans fallback chain; JetBrains Mono / Consolas for addresses and data |
| Motion | 0.35 s quick → 1.3 s slow, ease-out-cubic reveals |

Accent colours are **semantic and stable across scenes**: IPv4 is always amber,
IPv6 always violet, network prefixes green, legacy constraints rose. That
consistency is what makes a series feel like one channel.

---

## The component library

`from manimations.components import typography, surfaces, network, data, transitions`

| Family | Highlights |
| --- | --- |
| `typography` | `headline`, `body`, `mono`, `title_card`, `scene_header`, `keyword`, `highlight_phrase`, `bullet_list` |
| `surfaces` | `panel`, `card`, `badge`, `connector`, `elbow_connector`, `callout`, `annotation_arrow`, `pointer`, `divider`, `progress_track` |
| `network` | `address_block` (IPv4/IPv6, grouped hextets), `bit_grid`, `node`, `router`, `device`, programmatic `icon_monitor/cloud/server/shield`, `link`, `packet`, `packet_path`, `stack` |
| `data` | `counter` (animated), `timeline`, `comparison`, `comparison_column`, `meter`, `stat_block` |
| `transitions` | `dissolve_in/out`, `slide_in`, `morph`, `swap` |

All graphics are drawn from Manim's native vector primitives — there are **no
external image assets**, so every explainer renders anywhere Manim runs.

Preview the whole library:

```bash
uv run manimations demo            # renders src/manimations/demo.py
```

---

## Scene briefs

A brief is a YAML file: a title plus a list of scenes, each with narration, an
approximate duration, accent, intended visuals and authoring notes.

```yaml
title: "How DNS Resolution Works"
slug: dns
narration_voice: alba
scenes:
  - id: 01_problem
    class: SceneProblem          # must exist in scenes.py
    accent: amber
    duration: 16
    narration: "You type a name, but the network only understands addresses."
    visuals: [address-block, query-arrow]
    notes: "Show the name resolving into an address."
```

Validation enforces the shape (`NN_name` ids, valid accents, class present in
`scenes.py`) and checks that narration pace is reasonable — **105–185 words per
minute** of the declared duration, with a suggested duration when it is not.

---

## The production pipeline

```
project.yaml ──validate──▶ render preview (480p)
                              │  on failure: classify → retry (≤3) → log
                              ▼
                         contact sheets + pixel QA
                              │
                              ▼
                         render final (1080p30)   [cache-aware]
                              │
                              ▼
   narration (pocket-tts) ─▶ FFmpeg concat ─▶ mux audio/subs ─▶ final MP4
                              │
                              ▼
                    ffprobe validation + frame QA
```

Key guarantees, all enforced in code:

- **Success is never assumed.** A scene is only marked done when its output file
  exists, is non-empty and probes cleanly. The final video is only reported when
  `ffprobe` confirms resolution, fps and duration.
- **Repair, don't crash.** Failures are classified (syntax, import, attribute,
  type, missing class, timeout). Recoverable ones retry up to **3 times** with
  backoff; fatal ones stop immediately. Every failure is written to
  `build/qa/render_errors.txt` with the real stderr.
- **No clobbering.** Scenes and the final cut render to a staging path and are
  promoted only after validation, so a previously good render survives a bad
  rebuild.
- **Caching.** A scene's cache key hashes its narration, class, quality, the
  whole framework source and the brief. Unchanged scenes are reused; touching the
  design system invalidates everything automatically.
- **Narration stays in sync.** Each scene is padded by `settle()` to its declared
  duration, the narration track is padded/trimmed to the same timeline, and the
  assembler refuses to promote an export whose duration is shorter than its
  scenes. So a 143 s brief yields a 143 s video with the voice lining up.

---

## Command reference

```
manimations new NAME [--topic T] [--brief file.yaml] [--dir D] [--force]
manimations list
manimations validate PROJECT
manimations preview  PROJECT [--scene ID]... [--no-cache] [--attempts N]
manimations final    PROJECT [--scene ID]... [--voiceover] [--voice NAME]
                              [--language LANG] [--music FILE] [--subtitles]
                              [--burn-subtitles] [--no-qa] [--no-cache]
manimations assemble PROJECT [--voiceover] [--music FILE] [--subtitles]
manimations voiceover PROJECT [--voice NAME] [--language LANG] [--scene ID]
manimations subtitles PROJECT
manimations qa VIDEO [--expect W,H,FPS] | qa --project SLUG [--final]
manimations contact-sheet VIDEO [--cols N] [--rows N] [--output PNG]
manimations demo [--quality l|m|h]
```

`PROJECT` accepts a slug (`ipv6`), a directory (`projects/ipv6`) or a path to a
`project.yaml`.

---

## Making a new explainer

There are two ways to bring a new video idea in, both starting from the same
brief format.

### Option A — you have a topic, the tool writes the brief

```bash
uv run manimations new dns --topic "How DNS Resolution Works"
```

This creates `projects/dns/project.yaml` with a sensible 3-scene skeleton
(intro / concept / conclusion) and a `scenes.py` full of runnable stubs. Edit
the narration and durations in the YAML, then replace the stub bodies.

### Option B — you have written the brief yourself

Write a YAML file (copy `examples/dns_brief.yaml` as a starting point) and
scaffold from it:

```bash
uv run manimations new dns --brief examples/dns_brief.yaml --dir projects/dns
```

This is the one to use when you already know the scene list — it turns each
brief entry into a named, renderable scene class.

### The brief format

```yaml
title: "How DNS Turns Names Into Addresses"
slug: dns
description: "A short explainer on the Domain Name System"
narration_voice: alba          # any pocket-tts voice name, or a path to a wav
subtitle_lang: en
# music: assets/music_bed.mp3  # optional bed, looped and mixed low

scenes:
  - id: 01_problem               # must be NN_name (two digits, lowercase)
    class: SceneProblem          # the class name in scenes.py
    accent: amber                # cyan|violet|amber|green|rose|blue|slate
    duration: 15                 # approximate seconds (matches the narration)
    narration: "You type a name ... the network only understands addresses."
    visuals: [name-badge, address-badge, arrow]   # notes to yourself
    notes: "Show a human name resolving into an IP address."
```

Rules that validation enforces:

- `id` matches `NN_name`; scenes must be in numeric order; ids unique
- `class` must exist in `scenes.py` (checked by parsing the file)
- `accent` must be one of the seven palette names
- narration pace must land in **105–185 wpm** for the declared duration — if it
  doesn't, validation tells you the suggested duration

### Then iterate

```bash
uv run manimations validate dns                 # check the brief + environment
uv run manimations preview  dns                 # 480p render + QA + contact sheets
#   review projects/dns/build/qa/*_sheet.png
uv run manimations final    dns --voiceover --subtitles
```

`new` generates a **working** project: every scene stub is a real,
renderable `ExplainerScene` subclass with the narration and intended visuals
embedded as class attributes, so `preview` succeeds immediately and you replace
the placeholder body with the real diagram. The `_template` project
(`projects/_template/`) is a ready-made copy of that output if you'd rather
start by copying a directory than by running the command.

To hand the brief to the tool without keeping the YAML around, note that
`--brief` reads and scaffolds in one step; the generated `project.yaml` is then
the source of truth.

---

## The IPv6 example

`projects/ipv6/` — seven scenes, ~138 s of narration, all rendered and assembled:

| # | Scene | Idea, shown visually |
| --- | --- | --- |
| 00 | `SceneColdOpen` | Title card; the two address families resolve side by side |
| 01 | `SceneScarcity` | Counter climbs to 4.29 billion; the allocation pool fills and is stamped *all allocated* |
| 02 | `SceneAddressMeaning` | A packet hops device → router → destination; the device relocates and its address changes |
| 03 | `SceneBitWidth` | 32-bit dotted quad vs 128-bit hextets, each over its own bit grid |
| 04 | `ScenePrefixAndConnectivity` | One address split at bit 64 into network prefix and interface identifier; a /64 stat |
| 05 | `SceneSlowAdoption` | Four factor cards (legacy, compatibility, cost, operations) over a timeline from 1998 to today |
| 06 | `SceneDualStack` | One device, two addresses, two routes — IPv6 preferred, IPv4 fallback |
| 07 | `SceneConclusion` | Three takeaways, then settle |

Technical accuracy notes: the explainer states that IPv6 is **not** inherently
faster or more secure, and that its purpose is to solve address exhaustion. No
invented statistics are used; the only figures shown (2³² ≈ 4.29 billion, 2⁶⁴)
are exact properties of the address widths.

---

## Quality assurance

`manimations preview` runs QA automatically, and `manimations qa` runs it on
demand. It genuinely analyses rendered frames — it does not just claim to:

- samples frames with FFmpeg and locates the bounding box of non-background
  pixels, checking it against the safe area (**text clipping / off-screen**)
- detects content touching the frame border
- detects blank or near-empty frames (a scene that failed to draw)
- validates **resolution, fps and duration** from the file on disk
- writes a per-video JSON report and per-scene contact sheets

```bash
uv run manimations qa --project ipv6            # all preview renders
uv run manimations qa --project ipv6 --final    # all final renders
uv run manimations qa build/ipv6_final.mp4 --expect 1920,1080,30
```

Scenes also self-check at render time: `ExplainerScene.qa_report()` flags
content outside the safe area and bounding-box collisions via
`manimations.helpers.layout`.

---

## Testing

```bash
uv run pytest -m "not slow"     # unit tests: config, theme, components, pipeline
uv run pytest                   # adds end-to-end tests that really render
```

The end-to-end tests render a two-scene project with Manim, assemble it with
FFmpeg, and assert on the real output — including that the render cache reuses
unchanged scenes and that no sampled frame is blank.

---

## Troubleshooting

| Symptom | Fix |
| --- | --- |
| `ffmpeg not found` | Install FFmpeg and put it on `PATH` (`winget install Gyan.FFmpeg`, `brew install ffmpeg`, `apt install ffmpeg`). |
| `cannot import manim` | Run inside the project environment: `uv run manimations …` or activate `.venv`. |
| `pocket-tts not importable` | Install the extra: `uv sync --extra tts`. Everything else still works. |
| A scene fails to render | Read `projects/<slug>/build/qa/render_errors.txt` — it has the real stderr and the failure class. |
| Fonts look wrong | `manimations validate` reports the resolved heading/body/mono families; install one of the fallbacks. |
| Rendering is slow | Use `preview` while iterating; the cache skips scenes whose inputs did not change. |

---

## Credits

- [Manim Community Edition](https://www.manim.community/) — vector animation engine
- [FFmpeg](https://ffmpeg.org/) — encoding, assembly and frame analysis
- [pocket-tts](https://github.com/kyutai-labs/pocket-tts) by Kyutai — local CPU text-to-speech
- [uv](https://docs.astral.sh/uv/) — environment and dependency management

Licensed for educational use; respect the licences of the individual tools and
the pocket-tts voice samples you choose.
