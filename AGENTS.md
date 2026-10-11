# AGENTS.md

Guidance for AI agents and contributors working in this repository.

**Manimations** is an automated 2D educational motion-graphics system built on
Manim Community Edition. You give it a topic and a structured scene brief, and it
produces a finished, narrated explainer video — rendering, error recovery,
assembly, voiceover and subtitles included. It ships with a reusable component
library, a design system, a render/repair/assemble pipeline, and a complete
example project (`projects/ipv6`).

Everything runs locally with free tools. No paid APIs, cloud services or
subscriptions.

---

## 0. Standing constraints for agents (read before anything else)

Four rules that override convenience. They exist because each one was broken
once and cost real time or real disk.

### 0.1 Keep everything on `D:`. Do not touch `C:` unless it is necessary.

This repository, its venv, its model weights, its renders and its scratch files
all live on `D:` (a 928 GB volume). `C:` is the smaller system drive and is
shared with the OS.

- Write scratch/temp files under `build/scratch/` in the repo, **not** under
  `$TMPDIR`, `%TEMP%`, `~/AppData/Local/Temp` or `~/.cache`.
- Model weights, downloaded GGUFs, llama.cpp builds and any multi-GB artefact go
  under `build/` (already git-ignored), never into a home-directory cache.
- When a tool defaults to a `C:` cache (`pip`, `npm`, `uv`, `huggingface_hub`,
  `graphify`), point it at `D:` **before** it populates the default location, or
  set the tool's own env var (`HF_HOME`, `UV_CACHE_DIR`, `XDG_CACHE_HOME`, …).
  Do not silently relocate a cache a tool has already filled — check where it
  writes first.
- **Necessary exceptions** (use them, but say so in the report): the tool itself
  only exists on `C:` (e.g. `winget`, npm global shims, Ollama's own install),
  or a read-only lookup of a system path. Installing a package manager's global
  binary to `C:` is acceptable; parking a 3 GB model cache there is not.

### 0.2 Do not run things on this machine unless the user asked for it.

Rendering, tests, installs, TTS synthesis and network calls all cost time,
electricity, disk and GPU. A `D:`-side read is free; a render is not.

- **Default to reading.** `read_file`, `search_files` and the graphify graph
  answer most questions without executing anything.
- **Do not execute the subject of a video.** A Short explaining a CLI tool,
  a tunnel, a server or a scheduler does not need that tool run to be accurate —
  the claims come from the vendor's docs and the commands go on screen as text.
  Never point a destructive or system-modifying command at the user's real data
  to "verify" it; build a throwaway fixture instead.
- **Ask before a long or expensive run** (a full render, a model download, a
  multi-minute TTS pass, a dependency install), and batch so one run answers
  every open question rather than one question per run.
- When the user *does* ask for it ("render it", "run the tests", "install it"),
  run it and report the real numbers.

### 0.3 Read the proper docs on the web — with `playwright-cli`.

Do not answer a factual question about an external tool from memory, and do not
trust a third-party summary when the vendor publishes the fact itself. **Vendor
docs and vendor product pages are the authority**; blog posts, aggregator sites
and "FAQ" pages on unrelated domains are not.

`playwright-cli` (already installed, npm global) drives a real browser and is the
way to read a page that a plain fetch mangles or blocks:

```bash
playwright-cli open "https://docs.ollama.com/windows"     # open + navigate
playwright-cli goto "https://ollama.com/library/llama3.1" # navigate an open session
playwright-cli find "4.9GB"                               # search the page, with context
playwright-cli eval "() => document.body.innerText.slice(0, 2000)"
playwright-cli snapshot                                   # a11y tree with element refs
playwright-cli close
```

- Prefer `find "<string>"` and a small `eval` that slices `innerText` — they
  return text you can cite, not a wall of markup.
- Use `snapshot` when you need to click or fill something (it gives `ref=eN`).
- **Cite what you read, with the URL and the date.** Record the vendor's own
  wording where a claim depends on it.
- A page that 403s (Cloudflare) is a signal to try the vendor's docs domain or
  a different route — not a licence to fall back on a secondary source.

Worked example, and why this rule exists: the model size for
`ollama run llama3.1:8b` was taken from third-party write-ups as **4.7 GB** and
rendered on screen. Reading `ollama.com/library/llama3.1` live showed the vendor
lists **4.9GB**. The wrong number was in a delivered video; the vendor page
settled it in one command.

### 0.4 Use the graphify graph to understand this codebase.

`graphify-out/` holds a knowledge graph of this repo — 1013 nodes, 2000 edges,
70 **named** communities (`ExplainerScene core`, `Layout and safe areas`,
`Narration, TTS and subtitles`, …). Query it instead of grepping blind:

```bash
graphify query "how does a scene pad to its declared duration" --budget 600
graphify explain "ProjectConfig"       # a node and its neighbours
graphify path "ExplainerScene" "Renderer"   # shortest path between concepts
graphify god-nodes --top 12            # the architectural hubs
```

- **Treat a codebase question as a graphify query first.** It returns the
  structure — who calls whom, which module owns a concern — which is exactly what
  `grep` cannot show you.
- Read `graphify-out/GRAPH_REPORT.md` for god nodes, surprising connections and
  the community map before a broad refactor.
- After changing code, refresh it: `graphify update .` (no API key, no LLM).
- The graph's god nodes are the real architecture: `ProjectConfig` (87 edges) and
  `ExplainerScene` (51) are the only two bridges across the codebase, and there
  are **no import cycles** — the §2 rule holds.

---

## 1. Read this first

- **Ask the graphify graph first** (§0.4). For "how does X work", "what calls Y"
  or "where does Z live", `graphify query` / `explain` / `path` answers from the
  built structure in one command, and `graphify-out/GRAPH_REPORT.md` has the
  architecture map. Grep afterwards, to confirm a detail — not to explore.
- **The hard-won Manim CE 0.22 facts are in the `manim-video` skill**, under
  `references/manim-ce-0.22-pipeline-lessons.md`. Read it before touching
  rendering, layout or the pipeline. It records pitfalls that cost real renders
  to discover (background-colour timing, missing `ElbowArrow`, `VGroup` vs
  `ValueTracker`, `always_redraw` drift, `-shortest` truncation, and more).
- **`README.md`** is the user-facing manual (setup, commands, guarantees).
- **`docs/writing-a-scene.md`** is the guide for the part a human/agent authors:
  turning narration into a diagram.
- **Never edit `projects/*/build/`** — it is generated output (git-ignored).

## 2. The one architectural rule

```
src/manimations/   ← the reusable framework
projects/<slug>/   ← topic content (brief + scenes)
```

**The framework must never import a project. Projects import the framework.**

A new topic must never require editing framework code. If you find yourself
wanting to special-case a topic inside `src/`, add a component or a helper
instead. This boundary is what makes the system reusable, and it is the thing
most worth protecting in review.

## 3. Repository layout

```
src/manimations/
├── theme.py            design tokens → Manim config; Orientation (landscape/vertical)
├── config.py           project.yaml → dataclasses; validation; orient property
├── brief.py            scene-brief schema, project scaffolding, YAML emission
├── scene.py            ExplainerScene base: theme, chrome, QA hooks, duration sync
├── demo.py             component-library demo scene
├── cli.py              the `manimations` command line
├── components/         the visual component library (see §5)
│   ├── typography.py   titles, headings, labels, emphasis, title_card
│   ├── surfaces.py     panels, cards, badges, connectors, callouts, dividers
│   ├── network.py      address blocks, bit grids, nodes, routers, packets, stacks
│   ├── data.py         counters, timelines, comparisons, meters, stat blocks
│   └── transitions.py  dissolves, slides, morphs
├── helpers/
│   ├── timing.py       easing curves, staggered reveals
│   └── layout.py       safe areas, spread/stacked/pair, clipping & collision checks
└── pipeline/
    ├── validator.py    pre-flight checks (deps, fonts, classes, brief)
    ├── renderer.py     preview → repair → final; orientation-aware resolution
    ├── errors.py       failure classification + repair log
    ├── cache.py        content-hash cache (skip unchanged scenes)
    ├── qa.py           real pixel analysis of rendered frames
    ├── probe.py        ffprobe/ffmpeg wrappers
    ├── assembler.py    concat + mux
    └── audio.py        narration engines (pocket-tts/VoxCPM), fitting, SRT subtitles
    └── assets.py       free asset search/download (Freesound SFX, Jamendo music)

projects/
├── ipv6/               the finished example (8 scenes, both orientations)
├── dns/                a second example scaffolded from examples/dns_brief.yaml
└── _template/          copyable starter for a new topic

tests/                  166 unit tests + 7 real-render end-to-end tests
docs/ examples/         the scene-authoring guide and a sample brief
graphify-out/           knowledge graph of this repo (git-ignored; see §0.4)
```

## 4. Environment and commands

Python ≥ 3.10, `uv`, FFmpeg on `PATH`. The project venv holds Manim CE 0.22,
pocket-tts (optional, CPU TTS), VoxCPM (optional, GPU TTS) and pytest.

```bash
uv sync --extra tts                  # install (omit the extra to skip narration)
uv sync --extra voxcpm               # optional: VoxCPM PyTorch backend (needs ~8 GB VRAM)
                                     #   for a 4 GB GPU use the voxcpm-gguf engine instead

uv run manimations validate ipv6     # pre-flight: brief, deps, fonts, classes
uv run manimations preview  ipv6     # 480p render + pixel QA + contact sheets
uv run manimations final    ipv6 --voiceover --fit-narration --subtitles
uv run manimations qa --project ipv6 # frame-level report on rendered scenes
uv run manimations new myslug --topic "My Topic"

uv run pytest -m "not slow"          # unit tests (fast)
uv run pytest                        # adds tests that really render + assemble
```

Always use `uv run …` from the repo root — the bare `python` on this machine is
a different interpreter and cannot see Manim.

Scratch files, probes and downloads go under `build/scratch/` (git-ignored, on
`D:`). Never write them to `$TMPDIR` / `%TEMP%` / `~/.cache` — see §0.1.

## 5. Authoring a scene

Every scene subclasses `ExplainerScene`. The shape is: header, a diagram built
in steps, emphasis on what the narration stresses, done.

```python
from manim import DOWN, FadeIn, VGroup
from manimations import ExplainerScene
from manimations.components import network, surfaces, typography
from manimations.helpers import layout, timing


class SceneExample(ExplainerScene):
    def construct(self) -> None:
        t = self.theme
        self.add_header("Section title", accent=t.violet, index="03")

        block = network.address_block(["2001", "db8", "1", "1"], dot=False,
                                      accent=t.violet)
        layout.fit_width(block, layout.safe_width())
        block.move_to([0, 1.5, 0])
        self.register_content(block)
        self.play(timing.fade_in_stagger(list(block), lag=0.1))
        self.settle()
```

Non-negotiable rules (each exists because breaking it caused a real bug):

1. **Never hard-code a colour, font size or position.** Take them from
   `self.theme` (`t.cyan`, `t.sizes.body`, `t.spacing.lg`). This is what makes a
   library of videos look like one channel.
2. **`self.register_content(...)` every top-level mobject** you draw. The QA pass
   only checks registered content for clipping and off-screen placement.
3. **Use layout helpers, never fixed x-coordinates.** `layout.safe_width()`,
   `spread()`, `stacked()`, `pair()`, `fit_width()` adapt to the orientation.
   A literal like `move_to([-4.6, …])` is a landscape-only bug.
4. **Build progressively.** Reveal a diagram in the order the narration
   introduces its parts; a picture that appears all at once reads as a slide.
5. **On-screen text is a label, not a transcript.** The narration carries detail.
6. **No magic `wait()` for padding.** The base class pads every scene to its
   declared duration automatically; `settle()` is only for an extra beat.

### Component reference (short)

| Need | Use |
| --- | --- |
| Titles / headings / body | `typography.headline`, `.body`, `.label`, `.title_card`, `.scene_header` |
| Emphasise a word in a sentence | `typography.highlight_phrase(text, "word", color=…)` |
| Grouped ideas, notes | `surfaces.card`, `.panel`, `.callout`, `.badge` |
| Arrows, connectors, rules | `surfaces.connector`, `.elbow_connector`, `.annotation_arrow`, `.divider` |
| IPv4/IPv6 addresses | `network.address_block(octets, dot=False, group_size=…)` |
| Bit-count comparison | `network.bit_grid(rows, cols)` |
| Devices, routers, links | `network.device`, `.router`, `.node`, `.link`, `.packet` |
| Programmatic icons | `network.icon_monitor`, `.icon_cloud`, `.icon_server`, `.icon_shield` |
| Counting up to a figure | `data.counter(...)` → `self.play(cnt.tracker.animate.set_value(x))` |
| Time span, comparison, fill | `data.timeline`, `.comparison`, `.meter`, `.stat_block` |

## 6. Orientation (landscape / vertical)

Set `orientation: landscape|vertical` in the brief, or `--orientation vertical`
per render. Landscape is 1920×1080, vertical 1080×1920; both keep the Manim
frame height at **8 scene units**, so vertical is simply a narrower frame and the
vertical spacing tokens stay valid.

- Safe-area margins are a **fraction of the frame** (7%), not fixed units. Do not
  reintroduce fixed margins: 0.85 units is 5% of a landscape frame but 19% of a
  vertical one.
- `layout.is_vertical()` exists for the cases where a layout genuinely must
  differ (e.g. eight address cells cannot fit one 9:16 row — split them).
- Prefer `spread()`/`stacked()`/`pair()` over `VGroup.arrange` in scenes; they
  fit the assembled group, so a row cannot overflow.

## 7. Pipeline guarantees (do not weaken these)

These are enforced in code and covered by tests. A change that breaks one is a
regression:

- **Success is never assumed.** A scene is only "done" when its output file
  exists, is non-empty and probes cleanly. The final video is only reported after
  ffprobe confirms resolution, fps and duration.
- **Repair, don't crash.** Failures are classified (syntax, import, attribute,
  type, missing class, timeout). Recoverable ones retry up to 3 times with
  backoff; fatal ones stop immediately and log the real stderr to
  `build/qa/render_errors.txt`.
- **Never clobber a good render.** Scenes and the final cut render to a staging
  path and are promoted only after validation.
- **Caching is content-hashed.** The key covers narration, class, quality, the
  whole framework source and the brief — so touching the design system
  invalidates everything automatically.
- **Narration stays in sync.** Each scene pads to its declared duration; the
  narration track is padded to the same timeline; the assembler refuses to
  promote an export shorter than its scenes. `--fit-narration` measures the real
  speech and sets the durations, removing silent tails.
- **QA is real.** `pipeline/qa.py` analyses actual rendered pixels (content
  bounds vs the safe area, edge contact, blank frames) and validates resolution,
  fps and duration from the file on disk. Never claim visual inspection beyond
  what this code does.

## 8. Testing

```bash
uv run pytest -m "not slow"    # 166 unit tests: config, theme, components,
                               # layout, orientation, narration fitting, pipeline
uv run pytest                   # + 7 e2e tests that render with Manim, assemble
                               # with FFmpeg, and assert on the real output
```

When you fix a bug, add a test that fails without the fix. When you change scene
layout, verify with a real render in **both** orientations:

```bash
uv run manimations preview myslug --orientation vertical
uv run manimations preview myslug --orientation landscape
```

The preview run prints per-scene QA results; any `!` line is a real layout
problem with a frame index.

## 9. Conventions

- **Python 3.10+ syntax**, `from __future__ import annotations` at the top.
- Type hints on public functions; dataclasses for structured data.
- Docstrings explain *why*, not *what* — the code says what.
- Comments are reserved for non-obvious constraints (e.g. "arrange first, then
  fit — scaling items before arranging lets gaps push the row back over the
  limit").
- Keep topic content out of `src/`. Keep framework logic out of `projects/`.
- Conventional Commits for messages (`feat:`, `fix:`, `docs:`); explain the
  behaviour change and how it was verified.

## 10. Adding a new topic

```bash
uv run manimations new myslug --topic "My Topic"          # 3-scene skeleton
uv run manimations new myslug --brief my_brief.yaml --dir projects/myslug
```

Then edit `projects/myslug/project.yaml` (narration, durations, accents,
orientation) and `projects/myslug/scenes.py` (the visual explanations), and
iterate with `preview`. `new` produces a **working** project — every stub is a
real, renderable scene — so `preview` succeeds immediately.

Brief rules enforced by validation: `id` is `NN_name` and in numeric order,
`class` exists in `scenes.py`, `accent` is one of the seven palette names, and
narration lands in 105–185 wpm for its declared duration.

## 11. Current state

- Framework ~5.8k lines across `src/manimations/`.
- `projects/ipv6`: 8 scenes, verified clean in both orientations; final render
  1080×1920 @ 30fps, 119.4 s, with narration and subtitles.
- Vertical 9:16 Shorts with narration and placed SFX, one folder per episode:
  `episode-1-gdu` (pocket-tts), `episode-2-usbipd`, `episode-3-sortdl`,
  `episode-4-cloudflared`, `episode-5-ollama`, `episode-6-f3`,
  `episode-7-mise`, `episode-8-wifi`, `episode-9-bat`, `episode-10-zoxide`,
  `episode-11-lazygit`, `episode-12-tldr` (all voxcpm-gguf).
  `episode-2-usbipd` is 1080×1920 @ 30fps, 40.5 s; `episode-5-ollama` is
  38.9 s; `episode-7-mise` is 43.5 s; `episode-8-wifi` is 45.3 s;
  `episode-9-bat` is 42.3 s; `episode-10-zoxide` is 38.9 s;
  `episode-11-lazygit` is 39.3 s; `episode-12-tldr` is 42.0 s.
- `projects/ipv6` and `projects/dns` are standalone explainers, **not** part of
  the numbered series. `dns` is still the generated stubs.
- 166 unit tests + 7 end-to-end tests passing.
- `graphify-out/` holds a knowledge graph of the repo (1013 nodes, 70 labelled
  communities) built with `graphify extract . --code-only`. Query it with
  `graphify query "<question>"` or read `graphify-out/GRAPH_REPORT.md` before
  grepping. Rebuild after code changes with `graphify update .` (no API key).

### 11.1 The Shorts series — canonical episode numbering

**This table is the source of truth. Do not re-derive an episode number from the
draft script; drafts routinely guess wrong.** Check it before writing any CTA.

Project folders are named `episode-<N>-<slug>`, and the folder name is also the
`slug:` in that project's `project.yaml` — so `manimations preview episode-6-f3`
works with no extra lookup.

| Ep | folder (= slug) | its CTA says |
| --- | --- | --- |
| 1 | `episode-1-gdu` | *(unnumbered — "Follow for more")* |
| 2 | `episode-2-usbipd` | "Follow for Episode 3" |
| 3 | `episode-3-sortdl` | "Follow for Episode 4" |
| 4 | `episode-4-cloudflared` | "Follow for Episode 5" |
| 5 | `episode-5-ollama` | "Follow for Episode 6" |
| 6 | `episode-6-f3` | "Follow for Episode 7" |
| 7 | `episode-7-mise` | "Follow for Episode 8" |
| 8 | `episode-8-wifi` | "Follow for Episode 9" |
| 9 | `episode-9-bat` | "Follow for Episode 10" |
| 10 | `episode-10-zoxide` | "Follow for Episode 11" |
| 11 | `episode-11-lazygit` | "Follow for Episode 12" |
| 12 | `episode-12-tldr` | "Follow for Episode 13" |

Adding episode N+1: name the folder `episode-<N+1>-<slug>`, set the same value as
its `slug:`, and have its CTA say `N+2`.

Two known inconsistencies, left as-is because the rendered videos are already
published — fix them only when re-rendering the affected episode:

- **`episode-1-gdu` never numbered itself.** Its CTA is "Follow for more /
  terminal black magic". That is why the chain *looks* like it starts at 2.
- **The series has two names in the files:** "Developer & Power-User Black Magic"
  (`gdu`, `usbipd`, `ollama`, `f3`) and "Power-User & Developer Shortcuts"
  (`sortdl`, `cloudflared`). Pick one when the series is next branded.

The CTA is spoken, so it is subject to the TTS pronunciation check (§0.3) —
"Follow for Episode seven" is safe, a bare numeral is not.

## 12. Known gaps

Be honest about these rather than working around them:

- The **vision model was unavailable** during development, so visual review has
  been programmatic (safe-area/edge/blank pixel analysis) plus contact sheets in
  `projects/*/build/qa/`. Automated *semantic* inspection of what a diagram
  means is **not** implemented.
- The **music bed** (`--music`) is implemented and now exercised against real
  audio in the end-to-end tests, including the music-only case (no narration),
  which a bug had been silently dropping. The Freesound/Jamendo download paths
  are covered by injected-transport tests plus a live check of the error paths;
  they have **not** been run against a real API key, since none is configured
  here.
- pocket-tts needs network access **once** to fetch model weights; offline runs
  will report narration as unavailable rather than failing.
- The **PyTorch VoxCPM backend** (`--engine voxcpm`) is covered by tests against a
  stub but has **not** been run against the real model: it needs PyTorch + CUDA
  and Python < 3.13, none of which the dev box has. It also cannot be quantized —
  voxcpm 2.0.3's `from_pretrained` exposes no dtype or bitsandbytes hook, so it
  needs ~8 GB of VRAM for the 2B model.
- The **quantized GGUF backend** (`--engine voxcpm-gguf`) *has* been exercised
  against the real 2B model — see §13 for the measured numbers. Its caveats are
  the llama.cpp-omni dependency and the fixed layer-count default.
- llama.cpp-omni is **Linux-first**: its Windows story is build-from-source (the
  only prebuilt binaries are the Comni GUI, which has no headless CLI). The
  Windows build is verified here, but a Linux/macOS build may behave differently.

---

## 13. The quantized VoxCPM2 backend (voxcpm-gguf)

`--engine voxcpm-gguf` narrates through llama.cpp-omni's `voxcpm2-cli`, which
loads **GGUF** weights — the only way to quantize VoxCPM2, since the Python
package offers none. It needs no PyTorch at all.

**Build (Windows, verified):**

```bash
# one-time toolchain: VS 2022 Build Tools (C++ workload), Ninja, Vulkan SDK
git clone --depth 1 https://github.com/tc-mb/llama.cpp-omni.git build/llama.cpp-omni
cmd /c build/llama.cpp-omni/build_vulkan.bat      # sets VULKAN_SDK, builds voxcpm2-cli
hf download DennisHuang648/VoxCPM2-GGUF VoxCPM2-BaseLM-Q8_0.gguf VoxCPM2-Acoustic-F16.gguf \
    --local-dir build/voxcpm-gguf
```

The CLI takes **two** GGUFs (BaseLM + Acoustic); a combined single-file GGUF from
another runtime will not load.

**Measured on a 4 GB GTX 1650 (Turing, sm_75)** — ~3.6 GB of weights resident, so
the layer count must be capped or generation OOMs when the AudioVAE decode graph
grows:

| `--gpu-layers` | Result |
| --- | --- |
| 0 (CPU) | works, RTF ~10.7 |
| 8 (default) | works, RTF ~2.4–4.8 |
| 10 | works for short text |
| 12 | OOM on project-length narration |
| 16 / all | OOM immediately |

Tuning knobs: `--gpu-layers N`, or the env vars `MANIMATIONS_VOXCPM_BIN`,
`MANIMATIONS_VOXCPM_BASE_LM`, `MANIMATIONS_VOXCPM_ACOUSTIC`,
`MANIMATIONS_VOXCPM_GPU_LAYERS` (for installs outside the repo).
