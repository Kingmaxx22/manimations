# Manimations

An automated **2D educational motion-graphics system** built on
[Manim Community Edition](https://www.manim.community/). Give it a topic and a
structured scene brief, and it produces a complete, narrated 1920×1080 explainer
video — rendering, repair, assembly, voiceover and subtitles included.

It ships with a reusable visual component library, a design system, a
multi-stage rendering pipeline with error recovery, and a finished example
project: **“What Is IPv6, and Why Is Adoption So Slow?”**

Everything is free and local: Manim + FFmpeg + a local text-to-speech backend —
[pocket-tts](https://github.com/kyutai-labs/pocket-tts) (CPU-only, the default) or
[VoxCPM](https://github.com/OpenBMB/VoxCPM) (OpenBMB; more expressive, GPU-class).
No cloud services, no API keys, no subscriptions.

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

### Narration engines (pocket-tts or VoxCPM)

Two local backends are supported; the brief picks one with `narration_engine`,
or `--engine` overrides it per run:

| Engine | Install | Notes |
| --- | --- | --- |
| `pocket-tts` (default) | `uv sync --extra tts` | CPU-only, ~100M params. Named voice catalogue (`alba`, `cosette`, …) or a wav path for voice cloning. |
| `voxcpm` | `uv sync --extra voxcpm` | [OpenBMB VoxCPM](https://github.com/OpenBMB/VoxCPM) — a 2B-param diffusion TTS, 30 languages, voice design and zero-shot cloning. Needs PyTorch + CUDA and Python < 3.13, and **cannot be quantized** (needs ~8 GB VRAM). |
| `voxcpm-gguf` | build [llama.cpp-omni](https://github.com/tc-mb/llama.cpp-omni) (see below) | The same VoxCPM2 2B model via **quantized GGUF** — fits a 4 GB GPU and needs no PyTorch. See [Quantized VoxCPM2 on a small GPU](#quantized-voxcpm2-on-a-small-gpu). |

```bash
# use VoxCPM for one render, with a voice-design prompt instead of a voice name
uv run manimations final ipv6 --voiceover --engine voxcpm \
    --voice "A calm, clear male narrator"

# or clone a reference clip
uv run manimations voiceover ipv6 --engine voxcpm --voice path/to/reference.wav

# pin a specific checkpoint
uv run manimations final ipv6 --voiceover --engine voxcpm --tts-model openbmb/VoxCPM1.5
```

For VoxCPM the `narration_voice` value in the brief is interpreted as follows: a
**path to an audio file** means clone that voice; a **multi-word phrase** is a
voice-design prompt; anything else (e.g. the pocket-tts default `alba`) is
ignored and the model's own default voice is used.

### Quantized VoxCPM2 on a small GPU

VoxCPM2 is a 2B model that wants ~8 GB of VRAM in PyTorch — and the Python
package **cannot be quantized** (its `from_pretrained` has no dtype or
bitsandbytes hook). The `voxcpm-gguf` engine sidesteps both problems by running
the same weights through [llama.cpp-omni](https://github.com/tc-mb/llama.cpp-omni)
as a quantized GGUF, with no PyTorch at all. It is verified on a **4 GB GTX 1650**.

```bash
# 1. toolchain (Windows): VS 2022 Build Tools (C++ workload), Ninja, Vulkan SDK
# 2. build the CLI
git clone --depth 1 https://github.com/tc-mb/llama.cpp-omni.git build/llama.cpp-omni
cmd /c build/llama.cpp-omni/build_vulkan.bat

# 3. quantized weights: BaseLM (Q8_0, ~1.6 GB) + Acoustic (~1.7 GB)
hf download DennisHuang648/VoxCPM2-GGUF VoxCPM2-BaseLM-Q8_0.gguf VoxCPM2-Acoustic-F16.gguf \
    --local-dir build/voxcpm-gguf

# 4. narrate
uv run manimations voiceover ipv6 --engine voxcpm-gguf
```

Tune the GPU/CPU split with `--gpu-layers N` (default **8**, the safe value on a
4 GB card; `0` forces CPU). Override the binary/weight locations with
`MANIMATIONS_VOXCPM_BIN`, `MANIMATIONS_VOXCPM_BASE_LM`,
`MANIMATIONS_VOXCPM_ACOUSTIC` and `MANIMATIONS_VOXCPM_GPU_LAYERS`.

### Vertical (9:16) for Shorts / Reels / TikTok

Set `orientation: vertical` in the brief (or pass `--orientation vertical`):

```bash
uv run manimations final ipv6 --orientation vertical --voiceover --fit-narration
# -> 1080x1920 @ 30fps
```

Landscape is `1920×1080`; vertical is `1080×1920`. Both keep the Manim frame
height at 8 scene units, so vertical is simply a narrower frame — your vertical
spacing and the component library work unchanged, and the safe-area helpers
adapt automatically.

### Kill the silent pauses (`--fit-narration`)

Scene durations in a brief are guesses. If a scene is declared 18s but the
narration only runs 12s, the video holds a frozen frame for 6s after the voice
stops. `--fit-narration` generates the speech **first**, sets each scene's
duration to the real audio length plus a short tail, writes those durations back
to `project.yaml`, and then renders:

```bash
uv run manimations final ipv6 --voiceover --fit-narration --subtitles
#   01_scarcity: 18.0s -> 15.3s
#   02_what_address_means: 18.0s -> 12.6s
#   ...
#   fitted 7 scene duration(s) to the narration
# -> 119s instead of 143s, with ~0.6s of air after each scene instead of ~5s
```

Tune the tail with `--tail 0.4`. Scenes with no narration (a silent title card)
keep their declared duration.

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
│       └── audio.py              #   narration engines (pocket-tts/VoxCPM), music, SRT
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
| Canvas | landscape 1920 × 1080 or vertical 1080 × 1920, 30 fps |
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
   narration (local TTS) ─▶ FFmpeg concat ─▶ mux audio/subs ─▶ final MP4
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

## Free assets: sound effects and music

Two free, key-based REST APIs are wrapped so a workflow can pull SFX and a
background bed without hunting for files. Both keys go in the **environment** —
never in the repo:

```bash
export FREESOUND_API_KEY=...   # https://freesound.org/apiv2/apply
export JAMENDO_CLIENT_ID=...   # https://devportal.jamendo.com/
```

```bash
# sound effects — CC0 by default, so no attribution is required
uv run manimations assets sfx search whoosh --count 5
uv run manimations assets sfx get transition --count 3 --max-duration 2

# background music — downloads, credits it, and wires it into a project
uv run manimations assets music get "electronic upbeat" --count 1 --project ipv6
```

`get` writes the files plus a `credits.json` / `credits.txt` recording the
author, licence and source URL of everything it downloaded.

**Two licence facts worth knowing**, because they are not the same on both sides:

- **Freesound** results are filtered to `Creative Commons 0` by default, which is
  the point of using it here — no attribution obligation. `--any-license` lifts
  the filter, which also creates an attribution duty.
- **Jamendo has no CC0 catalogue.** Its tracks are Creative Commons (often
  BY-NC), so credit is genuinely required, and the credits file records it.
  Tracks that set `audiodownload_allowed = false` are skipped rather than
  substituted with the streaming URL — the API docs require honouring that.

Key-free caveat: Freesound's key-only path serves **preview MP3s** (transcoded),
not the original upload — retrieving originals needs OAuth2. For UI clicks,
transition whooshes and short ambience that is not a problem.

Then render with the bed mixed low under the narration:

```bash
uv run manimations final ipv6 --voiceover --music projects/ipv6/assets/music_bed/*.mp3
```

---

## Command reference

```
manimations new NAME [--topic T] [--brief file.yaml] [--dir D] [--force]
manimations list
manimations validate PROJECT
manimations preview  PROJECT [--scene ID]... [--no-cache] [--attempts N]
                              [--orientation landscape|vertical]
manimations final    PROJECT [--scene ID]... [--voiceover] [--voice NAME]
                              [--language LANG] [--music FILE] [--subtitles]
                              [--burn-subtitles] [--fit-narration] [--tail S]
                              [--orientation landscape|vertical] [--no-qa] [--no-cache]
manimations assemble PROJECT [--voiceover] [--music FILE] [--subtitles]
manimations voiceover PROJECT [--voice NAME] [--language LANG] [--scene ID]
manimations subtitles PROJECT
manimations qa VIDEO [--expect W,H,FPS] | qa --project SLUG [--final]
manimations contact-sheet VIDEO [--cols N] [--rows N] [--output PNG]
manimations demo [--quality l|m|h]
manimations assets {sfx|music} {search|get} [QUERY] [--count N] [--out DIR]
                              [--format mp31|mp32|ogg|flac] [--max-duration S]
                              [--any-license] [--project SLUG]
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
orientation: landscape         # landscape (1920x1080) or vertical (1080x1920)
narration_voice: alba          # voice name, voice-design prompt or reference wav
narration_engine: pocket-tts   # pocket-tts (CPU, default) or voxcpm (GPU)
# narration_model: openbmb/VoxCPM2   # optional checkpoint override
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
- detects blank or near-empty frames (a scene that failed to draw, or one that
  fades its first mobject in from zero opacity — which would put a black frame
  at a scene boundary, i.e. exactly where the assembled video cuts)
- validates **resolution, fps and duration** from the file on disk
- writes a per-video JSON report and per-scene contact sheets

Sampling is 1 fps, so a short flash at a cut can slip between samples; scene
boundaries are worth checking at full frame rate when a scene changes its
opening animation.

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
| `voxcpm not importable` | Install the extra: `uv sync --extra voxcpm` — it needs PyTorch + CUDA and Python < 3.13. Or use `--engine pocket-tts`. |
| `voxcpm2-cli not found` | Build llama.cpp-omni (see [Quantized VoxCPM2](#quantized-voxcpm2-on-a-small-gpu)), or point `MANIMATIONS_VOXCPM_BIN` at the binary. |
| `voxcpm2-cli failed … ErrorOutOfDeviceMemory` | Too many layers on the GPU. Lower `--gpu-layers` (try 4), or use `--gpu-layers 0` for CPU. |
| `no Freesound API key` | Free key at <https://freesound.org/apiv2/apply>, then `export FREESOUND_API_KEY=…`. |
| `no Jamendo client id` | Free client id at <https://devportal.jamendo.com/>, then `export JAMENDO_CLIENT_ID=…`. |
| `Jamendo rejected the request` | Bad/expired client id, or a parameter the API rejects — the message carries Jamendo's own error. |
| A scene fails to render | Read `projects/<slug>/build/qa/render_errors.txt` — it has the real stderr and the failure class. |
| Fonts look wrong | `manimations validate` reports the resolved heading/body/mono families; install one of the fallbacks. |
| Rendering is slow | Use `preview` while iterating; the cache skips scenes whose inputs did not change. |

---

## Credits

- [Manim Community Edition](https://www.manim.community/) — vector animation engine
- [FFmpeg](https://ffmpeg.org/) — encoding, assembly and frame analysis
- [pocket-tts](https://github.com/kyutai-labs/pocket-tts) by Kyutai — local CPU text-to-speech
- [VoxCPM](https://github.com/OpenBMB/VoxCPM) by OpenBMB — expressive multilingual TTS (alternative narration backend)
- [uv](https://docs.astral.sh/uv/) — environment and dependency management

Licensed for educational use; respect the licences of the individual tools and
the voice samples you choose (pocket-tts voices, or a VoxCPM reference clip).
