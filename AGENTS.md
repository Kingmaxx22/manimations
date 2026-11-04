# AGENTS.md

Guidance for AI agents and contributors working in this repository.

**Manimations** turns a topic and a structured scene brief into a finished, narrated explainer video (render, error repair, assembly, voiceover, subtitles) using Manim Community Edition. It ships a component library, a design system, a render/repair/assemble pipeline, and a catalogue of vertical Shorts (`projects/episode-<N>-<slug>`). Everything runs locally with free tools; no paid APIs.

---

## 0. Standing constraints (read first)

Each rule exists because breaking it once cost real time or disk.

### 0.1 Keep everything on `D:`
The repo, venv, model weights, renders and scratch all live on `D:`. `C:` is the small shared system drive.

- Scratch goes in `build/scratch/`, never `$TMPDIR`, `%TEMP%` or `~/.cache`.
- Multi-GB artefacts (weights, GGUFs, llama.cpp builds) go under `build/` (git-ignored).
- Point tool caches (`pip`, `npm`, `uv`, `HF_HOME`, `UV_CACHE_DIR`, `XDG_CACHE_HOME`, …) at `D:` *before* they populate the default. Don't relocate a cache a tool already filled.
- Exceptions (state them in your report): tools that only exist on `C:` (`winget`, npm global shims, Ollama) or read-only lookups of system paths.

### 0.2 Don't run things unless asked
Renders, tests, installs, TTS and network calls cost time, power, disk and GPU.

- Default to reading: `read_file`, `search_files`, the graphify graph.
- Never execute the subject of a video (a CLI, tunnel, server, scheduler). Claims come from vendor docs; commands appear on screen as text. Never run destructive commands against real data. Use a throwaway fixture.
- Ask before long or expensive runs (full render, model download, long TTS, dependency install) and batch so one run answers every open question.
- When the user asks ("render it", "run the tests"), run it and report real numbers.

### 0.3 Verify against vendor docs, using `playwright-cli`
Never answer factual questions about an external tool from memory or third-party summaries. Vendor docs and product pages are the authority.

```bash
playwright-cli open "https://docs.ollama.com/windows"
playwright-cli goto "https://ollama.com/library/llama3.1"
playwright-cli find "4.9GB"                # search page, with context
playwright-cli eval "() => document.body.innerText.slice(0, 2000)"
playwright-cli snapshot                    # a11y tree with refs, for click/fill
playwright-cli close
```

- Prefer `find` and small `innerText` slices over raw markup.
- Cite what you read: URL, date, and the vendor's wording where a claim depends on it.
- A 403 means try the vendor's docs domain or another route, not a secondary source.

**Lessons (each from a real wrong claim):**

- **A summary line isn't the spec.** navi's README says "à la Ctrl-R"; the real binding is Ctrl+G (`docs/widgets/README.md`). When a claim hinges on a flag, key or command, read the page that specifies it. jless: `c` is shallow collapse, `C` deep, both act on the node and its siblings.
- **A roadmap item isn't support.** ctop "planned" other runtimes; the source has only `docker.go` and `runc.go`, and zero "podman" matches. Check the directory that implements a named integration.
- **A screenshot isn't the spec.** dive's demo GIF renders `FgRed` as pink. Only `file_node.go` settles colours (Added green, Removed red, Modified yellow).
- **Don't announce a verdict before reading the source.** btop's GPU claim looked false but was wrong the other way: GPU support depends on how btop is built. "Not verified yet" is a complete answer.
- **Conflicting vendor pages: fetch the thing they disagree about.** watchexec's README advertised an apt repo that its own `doc/packages.md` marks defunct (the host is dead).
- **A valid install command can still fail.** For `gh`, read both the install page and the releases page (signing-key rotations, repo migrations, deprecations). Check whether the distro archive carries the same version (Ubuntu 2.46.0 vs official 2.102.1).
- **A rename kills the install command.** `mprocs` became `dekit`; `brew install mprocs` 404s (`formula_renames.json` only migrates existing installs). Check the package still answers to the name used.
- **Surface omissions on screen.** Check every episode for a project-status note (maintenance mode, archived, deprecated). navi's outro now says "maintenance mode".

### 0.4 Use the graphify graph for codebase questions
`graphify-out/` is a knowledge graph of the repo (1013 nodes, 2000 edges, 70 communities, 40 named). Query it before grepping.

```bash
graphify query "how does a scene pad to its declared duration" --budget 600
graphify explain "ProjectConfig"
graphify path "ExplainerScene" "Renderer"
graphify god-nodes --top 12
```

- Read `graphify-out/GRAPH_REPORT.md` before broad refactors. Grep only to confirm details.
- God nodes: `ProjectConfig` (87 edges) and `ExplainerScene` (51) are the only bridges. No import cycles.
- Refresh after code changes: `graphify update .` (no API key).
- **It goes stale.** The copy was built at `fc3f47d` (3 commits behind HEAD): it has pre-rename paths (`projects/gdu`, `projects/usbipd`) and knows nothing of episodes 3+ (git-ignored). Run `graphify update .` before trusting project-side answers.

---

## 1. Where to read more

- **`manim-video` skill → `references/manim-ce-0.22-pipeline-lessons.md`**: hard-won Manim CE 0.22 pitfalls. Read before touching rendering, layout or the pipeline.
- **`README.md`**: user manual. **`docs/writing-a-scene.md`**: turning narration into a diagram.
- **Never edit `projects/*/build/`** (generated, git-ignored).

## 2. The one architectural rule

```
src/manimations/   ← reusable framework
projects/<slug>/   ← topic content (brief + scenes)
```

**The framework never imports a project.** A new topic must never require editing framework code. Add a component or helper instead of special-casing a topic in `src/`.

## 3. Layout

```
src/manimations/
├── theme.py        design tokens → Manim config; Orientation
├── config.py       project.yaml → dataclasses; validation
├── brief.py        brief schema, scaffolding, YAML emission
├── scene.py        ExplainerScene base: theme, chrome, QA hooks, duration sync
├── cli.py          `manimations` command
├── components/     typography, surfaces, network, data, transitions
├── helpers/        timing (easing, stagger), layout (safe areas, spread/stacked/pair, collision)
└── pipeline/       validator, renderer, errors, cache, qa, probe, assembler, audio, assets
projects/           _template/, episode-*/, old_ignore/ (archived ipv6, dns; git-ignored)
pngtuber/           avatar sprite pack (Count Sudo): poses, keyed sprites, prep script (11.2)
tests/  docs/  examples/  graphify-out/  build/
```

- `projects/ipv6` and `projects/dns` are archived in `projects/old_ignore/`. Examples using `ipv6` need a live slug substituted.
- **Tracked vs ignored is uneven:** the `projects/` ignore rule landed after the first episodes, so only `_template/`, `episode-1-gdu` (minus README) and `episode-2-usbipd` are tracked. Episodes 3+ are local and invisible to `git status`; `git add projects/…` silently does nothing for them. Use `git add -f projects/<slug>` deliberately.

## 4. Environment and commands

Python ≥ 3.10, `uv`, FFmpeg on `PATH`. **Always `uv run …` from the repo root** (bare `python` can't see Manim).

```bash
uv sync --extra tts                  # install (omit extra to skip narration)
uv sync --extra voxcpm               # optional PyTorch VoxCPM (~8 GB VRAM; use voxcpm-gguf on 4 GB)

uv run manimations validate <slug>   # pre-flight
uv run manimations preview  <slug>   # 480p + pixel QA + contact sheets
uv run manimations final    <slug> --voiceover --fit-narration --subtitles
uv run manimations qa --project <slug>
uv run manimations new myslug --topic "My Topic"

uv run pytest -m "not slow"          # 197 unit tests
uv run pytest                        # + 7 real-render e2e tests
```

`<slug>` is a live folder under `projects/`, identical to its `slug:`, e.g. `episode-48-gh`.

### 4.1 What each command does

| Command | Purpose | Cost |
| --- | --- | --- |
| `validate <slug>` | Pre-flight: brief schema, dependencies, fonts, scene classes, narration wpm. Renders nothing. | Seconds |
| `preview <slug>` | 480p render of every scene, pixel QA per scene, contact sheets in `projects/<slug>/build/qa/*_sheet.png`. No audio. | Minutes |
| `final <slug> …` | Full-resolution render, narration, subtitles, assembly into one video. | Longest |
| `qa --project <slug>` | Frame-level report on already-rendered scenes. Re-reads files; renders nothing. | Seconds |
| `new <slug> --topic "…"` | Scaffolds a working 3-scene project. | Instant |

### 4.2 Final render, step by step

**Before you start**

1. `validate <slug>` must pass. It flags pace (105–185 wpm) but **not** line length, so also check that no narration line exceeds ~150 characters (§13).
2. `preview <slug>` must be clean: no `!` lines, and the contact sheets read with `vision_analyze` (§7).
3. Per §0.2, a final render is a long, expensive run. If the user asked for the whole brief (§14), run it without asking; otherwise confirm first.

**The command**

```bash
uv run manimations final <slug> --voiceover --engine voxcpm-gguf --gpu-layers 4 \
    --fit-narration --subtitles
```

| Flag | Effect |
| --- | --- |
| `--voiceover` | Synthesises narration for each scene and lays it on the timeline. Without it the video is silent. |
| `--engine voxcpm-gguf` | The TTS engine every delivered episode (2+) uses. Other engines: `voxcpm` (PyTorch, ~8 GB VRAM, untested on real model), and pocket-tts (CPU; used only by episode 1, needs network once for weights). |
| `--gpu-layers 4` | Caps GPU layers for `voxcpm2-cli`. Use 4 for any episode 17 or later, or any line over ~150 characters; 6 is the maximum for older, shorter-line episodes. The code default of 8 is unsafe on this machine. |
| `--fit-narration` | Measures the real speech, then sets each scene's `duration = narration + 0.6 s` and removes silent tails. **It overwrites declared durations**, even larger ones, and persists them into `project.yaml`. |
| `--subtitles` | Builds an SRT from actual rendered scene durations. Subtitle text comes from `subtitle_text` if set. |
| `--orientation vertical\|landscape` | Overrides the brief. Shorts are vertical (1080×1920 @ 30 fps). |
| `--music` | Optional music bed. Implemented and tested, but delivered Shorts don't use it. |

**What happens internally**

1. Each scene renders to a **staging path** and is promoted only after it exists, is non-empty and probes cleanly. Unchanged scenes are skipped via the content-hash cache (any framework edit invalidates everything).
2. Failures are classified; recoverable ones retry up to 3× with backoff. Fatal ones stop and write stderr to `build/qa/render_errors.txt`.
3. Narration is synthesised, then durations are fitted, then scenes re-render at their fitted durations.
4. Narration and subtitles are placed on the *actual* rendered scene durations. The assembler concatenates, muxes, and promotes the final only after ffprobe confirms resolution, fps and duration.

**After it finishes: read the output, don't assume**

- **Silent scenes:** if the narration step names a scene as silent, the TTS failed and was padded with silence. The video still probes clean and reports `audio=True`. **Re-run it; never ship it.**
- **Overruns:** if `final` names a scene that rendered longer than declared, its animation outlasted `narration + 0.6 s`. Audio stays aligned, but you get a frozen frame. Lengthen the line (§13), don't just re-render.
- **Pace:** measure per-scene wpm from the rendered clips. Fix any rushing or dwelling line, and reset its declared `duration` in `project.yaml` before re-running (`--fit-narration` would otherwise keep the bad value).
- **Sync check:** `ffmpeg -i <final>.mp4 -af silencedetect -f null -` and confirm each voice line starts just after its scene boundary and ends inside it.

**Then finish the episode**

1. Run the episode's own `mix_sfx.py` (places SFX at scene boundaries), then `verify_sfx.py` (not present in episodes 1–4). Check the script's header for its exact arguments.
2. Mux to the reel, then `uv run manimations qa --project <slug>`. Expect `ok: true` and zero problems; report the real numbers (resolution, fps, duration).
3. Write the audit: `README.md` (claims table, measured pace, re-render command) and `assets/sfx/credits.json` / `credits.txt`.

**Re-rendering**

- Changing only narration or a single scene re-renders just what changed (cache). Changing anything under `src/manimations/` re-renders everything.
- Never edit `projects/<slug>/build/`; delete and re-run instead.
- If a GPU run OOMs or aborts (`failed to reserve AudioVAE decode graph memory`, or `rc=3221226505`), drop `--gpu-layers` (4, then 0 for CPU) or shorten the offending line.

## 5. Authoring a scene

Subclass `ExplainerScene`: header, diagram built in steps, emphasis, done.

```python
class SceneExample(ExplainerScene):
    def construct(self) -> None:
        t = self.theme
        self.add_header("Section title", accent=t.violet, index="03")
        block = network.address_block(["2001", "db8", "1", "1"], dot=False, accent=t.violet)
        layout.fit_width(block, layout.safe_width())
        block.move_to([0, 1.5, 0])
        self.register_content(block)
        self.play(timing.fade_in_stagger(list(block), lag=0.1))
        self.settle()
```

**Rules:**

1. Never hard-code colours, font sizes or positions. Use `self.theme` (`t.cyan`, `t.sizes.body`, `t.spacing.lg`).
2. `self.register_content(...)` every top-level mobject (QA only checks registered content).
3. Use layout helpers (`safe_width`, `spread`, `stacked`, `pair`, `fit_width`), never fixed x-coordinates.
4. Build progressively, in the order the narration introduces parts.
5. On-screen text is a label, not a transcript.
6. No `wait()` padding. The base class pads to the declared duration; `settle()` is for an extra beat.

**Components:**

| Need | Use |
| --- | --- |
| Titles / headings / body | `typography.headline`, `.body`, `.label`, `.title_card`, `.scene_header` |
| Emphasise a word | `typography.highlight_phrase(text, "word", color=…)` |
| Cards, notes | `surfaces.card`, `.panel`, `.callout`, `.badge` |
| Arrows, rules | `surfaces.connector`, `.elbow_connector`, `.annotation_arrow`, `.divider` |
| Addresses, bits | `network.address_block(...)`, `network.bit_grid(rows, cols)` |
| Devices, links | `network.device`, `.router`, `.node`, `.link`, `.packet` |
| Icons | `network.icon_monitor`, `.icon_cloud`, `.icon_server`, `.icon_shield` |
| Counters, timelines | `data.counter(...)` → `cnt.tracker.animate.set_value(x)`; `data.timeline`, `.comparison`, `.meter`, `.stat_block` |

**Manim/framework gotchas (all hit in real episodes):**

- **Add a panel before its content.** Panels are opaque; fading one in after its text paints the text out. Order: `FadeIn(panel)` → `Write(text)` → rows.
- **`surfaces.panel(fill=None)` is opaque** (it falls back to `THEME.surface`). Use `fill_opacity=0.0` for a border-only box. Also: if border, tint and label share one accent, the label vanishes.
- **`fill_color` alone draws nothing.** Manim shapes default to `fill_opacity=0`; set `fill_opacity=1.0`. Verify by counting accent-coloured pixels in a frame.
- **`headline/body/label/mono` take no `align`.** They return a centred `Text`; position with `move_to`.
- **`Line` takes only start and end.** For polylines use `VMobject.set_points_as_corners`.
- **`arrange(aligned_edge=…)` re-aligns.** Arrange first, then `shift` to indent. Verify with `row.get_left()[0]`.
- **`fit_width` guarantees fit, not legibility.** Shorten content rather than shrink type, then check at native resolution.

## 6. Orientation

Set `orientation: landscape|vertical` in the brief or `--orientation` per render. Landscape is 1920×1080, vertical 1080×1920; both keep frame height at 8 units.

- Safe-area margins are 7% of the frame; don't reintroduce fixed margins.
- `layout.is_vertical()` is for layouts that genuinely must differ.
- Prefer `spread/stacked/pair` over `VGroup.arrange`.

## 7. Pipeline guarantees (don't weaken)

- **Success is never assumed.** Output must exist, be non-empty and probe cleanly; the final is reported only after ffprobe confirms resolution, fps and duration.
- **Repair, don't crash.** Failures are classified (syntax, import, attribute, type, missing class, timeout). Recoverable ones retry up to 3×; fatal ones stop and log stderr to `build/qa/render_errors.txt`.
- **Never clobber a good render.** Render to staging, promote after validation.
- **Content-hashed cache** (narration, class, quality, framework source, brief). Touching the design system invalidates everything.
- **Narration stays in sync.** Narration and subtitles use actual rendered durations (`probe.scene_durations`), not the brief. `final` names scenes that rendered longer than declared; the assembler refuses exports shorter than their scenes.
- **QA is real, but not semantic.** `qa.py` checks pixels (bounds, edge contact, blank frames) and file resolution/fps/duration. It can't see unreadable text, clashing colours or a diagram that contradicts the narration. After a preview, read `projects/*/build/qa/*_sheet.png` with `vision_analyze`. Both checks are required.
  - Contact sheets are 480 px wide: good for type legibility, bad for judging graphics. A 10-segment gauge read as "8 identical segments" on a sheet. **Extract a native-resolution frame before "fixing" anything:** `ffmpeg -sseof -0.4 -i scene.mp4 -frames:v 1 out.png`.
  - Judge the last frame of a scene; earlier frames are legitimately half-built.

## 8. Testing

When you fix a bug, add a test that fails without the fix. When you change layout, render in **both** orientations (`preview myslug --orientation vertical|landscape`). Any `!` line in preview output is a real layout problem with a frame index.

## 9. Conventions

- Python 3.10+, `from __future__ import annotations`, type hints on public functions, dataclasses for structured data.
- Docstrings explain *why*; comments only for non-obvious constraints.
- Topic content stays out of `src/`; framework logic stays out of `projects/`.
- Conventional Commits (`feat:`, `fix:`, `docs:`); say what changed and how it was verified.
- If `write_file` refuses as a "partial view" after a full read, it's a false positive: use `patch` or Python via `execute_code`.

## 10. Adding a topic

```bash
uv run manimations new myslug --topic "My Topic"
uv run manimations new myslug --brief my_brief.yaml --dir projects/myslug
```

Edit `project.yaml` (narration, durations, accents, orientation) and `scenes.py`, then iterate with `preview`. `new` yields a working project (every stub renders).

Validation enforces: `id` is `NN_name` in numeric order; `class` exists in `scenes.py`; `accent` is one of seven palette names; narration is 105–185 wpm for its duration.

---

## 11. Current state

- Framework ~6.4k lines. 197 unit + 7 e2e tests (204 collected; 7 are `-m slow`); last unit run green.
- Vertical 9:16 Shorts, 1080×1920 @ 30 fps, narration plus placed SFX, no music. `episode-1-gdu` uses pocket-tts; all others use voxcpm-gguf. Every final is promoted. Durations run ~25–50 s (episodes 31–42 and 46–51 cluster at 25–29 s; 43–45 at 33–36 s).
- Each episode has `README.md` (engine, verified facts, re-render command), `assets/sfx/*.mp3` (four Freesound CC0 files + `credits.json`/`.txt`), `mix_sfx.py` and `verify_sfx.py`.
  - **Exceptions:** `episode-1-gdu`, `episode-14-httpie` and `episode-28-procs` have no README (the claims audit is a `project.yaml` header comment); episodes 1–4 have no `verify_sfx.py`.
- `dns` (archived) is still generated stubs.
- **Known published defect:** `episode-14-httpie` QA is `ok: false` (frame 26 touches the left edge). Every other final is `ok: true`. Fix only on re-render.
- **A silent scene is a failure.** `episode-17-gentoo`'s first render shipped 10.4 s of silence (TTS aborted on a 167-char line) while reporting `audio=True, problems=0`. If narration names a silent scene, re-render it.

### 11.1 Episode numbering (source of truth: don't re-derive from drafts)

Folders are `episode-<N>-<slug>`; the folder name is the `slug:`. Episode N's CTA says "Follow for Episode N+1". Spoken CTA spells the number ("Follow for Episode fifteen."); the on-screen CTA uses the numeral ("Follow for Episode 15"). A bare numeral after a proper noun is unsafe for TTS.

| N | slug | N | slug | N | slug |
| --- | --- | --- | --- | --- | --- |
| 1 | gdu | 20 | fd | 39 | watchexec |
| 2 | usbipd | 21 | btop | 40 | k9s |
| 3 | sortdl | 22 | delta | 41 | navi |
| 4 | cloudflared | 23 | yazi | 42 | age |
| 5 | ollama | 24 | starship | 43 | helix |
| 6 | f3 | 25 | hyperfine | 44 | jless |
| 7 | mise | 26 | glow | 45 | dekit |
| 8 | wifi | 27 | atuin | 46 | rclone |
| 9 | bat | 28 | procs | 47 | choose |
| 10 | zoxide | 29 | sd | 48 | gh |
| 11 | lazygit | 30 | zellij | 49 | dive |
| 12 | tldr | 31 | fastfetch | 50 | ctop |
| 13 | fzf | 32 | lazydocker | 51 | stern |
| 14 | httpie | 33 | duf | 52 | trivy |
| 15 | cache | 34 | gum | 53 | restic |
| 16 | sequoia | 35 | doggo | 54 | croc |
| 17 | gentoo | 36 | gping | 55 | nnn |
| 18 | eza | 37 | bandwhich | 56 | broot |
| 19 | ripgrep | 38 | just | 57 | tealdeer |
| | | | | 58 | tokei-scc |
| | | | | 59 | mlr |
| | | | | 60 | dasel |
| 61 | gron | 62 | entr | 63 | progress |
| 64 | httpstat | 65 | hurl | 66 | glances |
| 67 | hyfetch | 68 | micro | | |

Episode 1's CTA is unnumbered ("Follow for more / terminal black magic"). The next new episode is N+1 of the current head; check the repo for the actual head before numbering.

**Colliding briefs:** if two briefs claim the same episode number, the earlier (already built) one wins and the later moves up. Never renumber a published episode to match a draft (`ctop` and `stern` both said "Episode 51").

**Known inconsistencies (fix only on re-render):** `episode-1-gdu` never numbered itself; series name is "Developer & Power-User Black Magic" in 49 of 51 briefs, "Power-User & Developer Shortcuts" in `sortdl` and `cloudflared`, and absent from `gdu`. Pick one when next branded.

### 11.2 Styling and the avatar rig — NEW VIDEOS ONLY

Two styles, selected per project with `theme:` in `project.yaml` (injected as `MANIMATIONS_THEME`):

| Style | What | Who |
| --- | --- | --- |
| `classic` (default) | the original navy design system — unchanged, byte-identical behaviour | every delivered episode (1–82) |
| `neumorphic` | modern soft-UI dark: lifted slate palette (`theme.NEUMORPHIC_PALETTE`), soft dual shadows via `surfaces.soft_shadow`, rounder corners, same accents | `manimations new` scaffolds it; new episodes from 83 on |

- **Never re-render an episode to re-skin it.** Old projects carry no `theme:` key → classic; their finals stay as shipped, even though any framework edit invalidates the render cache. A `theme:` typo deliberately falls back to classic — a typo must never re-skin a delivered episode.
- **Avatar pack: `pngtuber/`** (repo level, neither framework nor project). Source poses are `vtuber_pose_*.png`; `prep_avatar.py` keys the gray backgrounds by edge-connected flood fill (the bold outlines protect the character; a global colour key would eat the pale skin) into `avatar_{idle,talking,blink,gesture,pointing,excited}.png`. `pngtuber/README.md` has the pose mapping and regeneration steps.
- Projects opt in with an `avatar:` block (`states:` name→path, `default:`) plus per-scene `avatar_state:`; `manimations new` emits both. The framework hardcodes no paths: the renderer resolves them and passes the scene a `MANIMATIONS_AVATAR` JSON payload; `components/avatar.py` builds the bottom-right rig — flips `talking↔idle` mouth cadence while narrating, blinks every few seconds, bobs gently, and is re-brought to the front each tick so it reads as an overlay. Missing sprites warn and disable the rig; they never fail a render.
- Verify both styles with a scratch project (`manimations new …` + `preview`), never by re-rendering a shipped episode.

---

## 12. Known gaps

- **Unattributed whoosh SFX.** Two whoosh files used by episodes 31–51 appear in no `credits.json` (only the two key clicks are credited). A 2026-10-22 trace (episode 49) found no spectral match (best cosine 0.63; the exact-duration Freesound candidate `853649` scored −0.15). Still open: trace before re-rendering any of them.
- **Music bed (`--music`)** is tested against real audio (including music-only) but never used in delivered Shorts. Freesound/Jamendo paths are tested with injected transports; not exercised through the pipeline even though `.env` has credentials. SFX came in via the asset client.
- **PyTorch VoxCPM (`--engine voxcpm`)** is tested only against a stub: it needs PyTorch + CUDA and Python < 3.13, absent here, and can't be quantized (~8 GB VRAM).
- **voxcpm-gguf** is exercised against the real 2B model and used by every delivered episode. Caveats: llama.cpp-omni dependency; `--gpu-layers` must be capped (episodes ≤16 use 6; 17+ use 4; the default of 8 is unsafe here); and name mangling ("Ollama" → "a llama", "HTTPie" → "HTTP", bare "sd" costs 1.6 s vs "ess-dee").
- **Spelling a name for the ear is per name, not a rule.** Probe each. On zellij, bare "Tmux" was best (177 wpm); "T mux" (241) and "Tee-mux" (199) rushed. Keep the real name in `subtitle_text` and on screen.
- pocket-tts needs network once to fetch weights; offline runs report narration unavailable.
- llama.cpp-omni is Linux-first. The Windows build (from source) is verified here; Linux/macOS may differ.

---

## 13. The quantized VoxCPM2 backend (`voxcpm-gguf`)

`--engine voxcpm-gguf` narrates through llama.cpp-omni's `voxcpm2-cli`, which loads **GGUF** weights. That is the only way to quantize VoxCPM2, since the Python package offers no dtype or bitsandbytes hook. It needs no PyTorch at all, which is why it runs on a 4 GB GPU where the PyTorch backend (~8 GB VRAM) cannot.

### 13.1 Build (Windows, verified)

Do this once. Everything lands under `build/` (git-ignored, on `D:` per §0.1). Check §0.2 first: the clone, compile and weight download are a long, disk-heavy run, so confirm with the user unless the brief requires it.

```bash
# one-time toolchain: VS 2022 Build Tools (C++ workload), Ninja, Vulkan SDK
git clone --depth 1 https://github.com/tc-mb/llama.cpp-omni.git build/llama.cpp-omni
cmd /c build/llama.cpp-omni/build_vulkan.bat      # sets VULKAN_SDK, builds voxcpm2-cli
hf download DennisHuang648/VoxCPM2-GGUF VoxCPM2-BaseLM-Q8_0.gguf VoxCPM2-Acoustic-F16.gguf \
    --local-dir build/voxcpm-gguf
```

Step by step:

1. **Toolchain.** Install VS 2022 Build Tools with the C++ workload, Ninja and the Vulkan SDK. These are the "necessary exceptions" in §0.1: package-manager or installer binaries may live on `C:`, but nothing else should.
2. **Clone** llama.cpp-omni into `build/llama.cpp-omni` (shallow, `--depth 1`).
3. **Build** with `build_vulkan.bat`. It sets `VULKAN_SDK` and produces `voxcpm2-cli`. Run it through `cmd /c` from the repo root.
4. **Download weights** with `hf download` into `build/voxcpm-gguf`. Set `HF_HOME` to a `D:` path *before* running, or the Hugging Face cache will fill `C:` (§0.1). The repo needs both files:
   - `VoxCPM2-BaseLM-Q8_0.gguf` (BaseLM, 8-bit quantized)
   - `VoxCPM2-Acoustic-F16.gguf` (Acoustic, 16-bit)
5. **Confirm paths.** The pipeline looks for the binary and weights inside the repo's `build/`. For installs elsewhere, set `MANIMATIONS_VOXCPM_BIN`, `MANIMATIONS_VOXCPM_BASE_LM` and `MANIMATIONS_VOXCPM_ACOUSTIC` (see the knobs at the end of this section).

The CLI takes **two** GGUFs (BaseLM + Acoustic); a combined single-file GGUF from another runtime will not load.

**Platform caveat:** llama.cpp-omni is Linux-first. Its Windows story is build-from-source (the only prebuilt binaries are the Comni GUI, which has no headless CLI). The Windows build above is verified on this machine; a Linux or macOS build may behave differently.

### 13.2 GPU layers

Measured on a 4 GB GTX 1650 (Turing, sm_75). About 3.6 GB of weights are resident, so the layer count must be capped or generation OOMs when the AudioVAE decode graph grows. Raising the layer count buys speed and costs headroom; the code's default of 8 is wrong for this box either way.

| `--gpu-layers` | Result |
| --- | --- |
| 0 (CPU) | works, RTF ~10.7 |
| 4 | **safe for long lines** (verified at 167 chars) |
| 6 | safe up to 166 chars; aborts at 167 |
| 8 (code default) | fine at scene length; OOMs on ~700 chars in one call |
| 10 | short text only |
| 12 | OOM on project-length narration |
| 16 / all | OOM immediately |

Two distinct failures:

- **Total audio per call:** `failed to reserve AudioVAE decode graph memory` (clean OOM).
- **Single-line length:** hard abort, `rc=3221226505` (`0xC0000409`, stack buffer overrun). Tight boundary: 166 chars OK at 6 layers, 167 not; 4 layers OK.

**Rule: keep every narration line ≤ ~150 characters, or use `--gpu-layers 4`.** (Every episode up to 16 had a longest line of ≤152, which is why 6 looked universally safe.) Validation flags pace, not length, so check both. Silent failures: the pipeline pads failed scenes with silence so the video still probes clean and reports `audio=True`. The CLI names silent scenes; if one is named, re-run it. Don't ship it.

### Pace: probing and fixing

- **The engine isn't byte-reproducible** (four runs of one line gave four SHA-256s; one line varied 3.84–4.48 s). **But duration is reproducible per text** (3.68 s ×3 in-process and again in a second process). A difference between two *wordings* is signal if it exceeds ~0.6 s; below that, treat as noise and re-measure. Wording is the only controllable lever.
- **Probe in one process with several variants** rather than re-rendering. Probe vs pipeline context can differ (4.64 s vs 5.44 s).
- **Rushing** (275–300 wpm vs siblings at 170–200). Triggers: "X, not Y, so Z" contrast; mid-line colon; three comma-separated clauses (dive: 277 wpm → 176 by shortening the middle clause).
- **Dwelling** (slow phrase, long scene). Triggers: spoken flag names ("dash E": name the capability instead); repeated words (one "different", not three); pause-inviting punctuation (mid-line colon); a **word junction** (watchexec's "from brew. Apache licensed." dwelled at 85 wpm; probe the phrase, not the vocabulary).
- **Judge by wpm, not s/word.** s/word is confounded by word length (lazydocker's long words ran 0.44–0.47 s/word at an ordinary 125–137 wpm). Use s/word only to compare variants of the *same* line.
- **wpm can't see dropped words.** On `sd`, "…with dash p, and identical behavior…" read a normal 170 wpm, but adding those three words cost only 0.16 s (expected ~1.0 s): the flag was never spoken. **Compare the duration delta of a minimal pair.**
- **Trends aren't causes.** Three outros ending in spoken numbers looked like a dose-response; the real cause was "Install … with brew" vs "Get … from brew". Probe the line. A 4-digit year mid-sentence is fine ("in 2024" ≈ "twenty twenty-four").
- **A probe can't hear phonemes.** For `age` (hard g per its README), duration says nothing about the consonant. The narration uses the author's transliteration ("aghe"), the screen keeps `age`, and the README says the pronunciation is unverified.
- **Faster isn't better: it shrinks the animation budget.** `--fit-narration` sets `duration = narration + 0.6 s`. On `k9s`, bare "k9s" dwelled (6.08 s, 98.8 wpm, under the 105 floor) while "kay-nines" ran 4.64 s (126 wpm) with only 0.74 s of margin. Fix by *adding* words ("…dashboard that watches your whole cluster": 5.60 s, 150 wpm, 1.70 s margin).
- **Episode length is a brief decision.** 32 s+ needs ~17–20-word lines and staggered multi-step builds; the usual 25–29 s band needs ~11–15-word lines and three plays per scene. Check the brief before writing lines.

### Duration must beat the animation, not just the narration

`--fit-narration` sets `duration = narration + 0.6 s` and **overwrites** the declared value even when larger (its docstring claims otherwise; the code doesn't). If the target falls below the scene's animation time, `_pad_to_target` applies the 1.1 s minimum hold *instead of* padding, so the scene overruns and every later voice plays early (`lazydocker`: 3.6 s target vs 3.77 s animation → scene 01 rendered 4.90 s).

- The pipeline now builds narration and subtitles from real durations, so audio stays aligned, but an overrun still costs a frozen frame. Keep `narration + 0.6 ≥ animation + margin`.
- Measure animation time by forcing every duration to 1.0 s and reading the render back (rendered − 1.1 s).
- Verify exports with `ffmpeg -af silencedetect`: each line must start just after its scene boundary and end inside it.
- **`--fit-narration` persists bad pace into the brief** (a dwelling scene becomes `duration: 16.8`). Reset the declared duration when you fix the line.

**Knobs:** `--gpu-layers N`; env `MANIMATIONS_VOXCPM_BIN`, `_BASE_LM`, `_ACOUSTIC`, `_GPU_LAYERS`.

---

## 14. Working a brief end to end

When the user pastes a **Video Blueprint**, the deliverable is the finished Short, not a plan. Run the whole pipeline without check-ins:

1. **Verify the draft first (§0.3).** The Blueprint is a draft: timestamps are usually fiction and claims often fail vendor verification. Read vendor pages, fix or drop unsupported claims, and report corrections *before* writing code.
2. **Scaffold** (`manimations new <slug> --topic … --dir projects/<slug>`), write `project.yaml` (brief + claims audit) and `scenes.py`, then `validate`.
3. **Probe pace (§13)** and fix rushing/dwelling lines and lines >150 chars *before* the first render.
4. **Preview** (480p) and read contact sheets with the vision model; check suspicious frames at native resolution.
5. **Final:** `manimations final <slug> --voiceover --engine voxcpm-gguf --gpu-layers 4 --fit-narration --subtitles`, then `mix_sfx.py`, `verify_sfx.py`, then mux to the reel. Follow §4.2 for flags, post-render checks and failure handling.
6. **Write the audit:** `README.md` (claims table, measured pace, re-render command) and `assets/sfx/credits.json`/`.txt`.
7. **QA the reel** (`manimations qa`) and report real numbers.

**Working rules:**

- Once the brief is accepted, don't stop to ask "is it done?". §0.2's "ask before expensive runs" governs work *outside* the brief, not the pipeline the brief requires.
- Renders run in the background for minutes: poll (or `notify=True`) and write credits, README and AGENTS.md updates *while* it runs.
- **Episode numbering:** the Blueprint's CTA names the *next* episode (CTA "N+1" → this is Episode N). Check §11.1 before writing any CTA.
