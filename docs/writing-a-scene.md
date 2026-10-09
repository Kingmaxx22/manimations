# Writing a scene

This guide is for the part of the work that is genuinely yours: turning a piece
of narration into a diagram that explains it.

## The shape of a scene

```python
class ScenePrefixAndConnectivity(ExplainerScene):
    def construct(self) -> None:
        t = self.theme

        # 1. header: the section title, always in the same place
        self.add_header("Prefix and connectivity", accent=t.green, index="04")

        # 2. build the diagram progressively
        block = network.address_block([...], accent=t.violet)
        block.move_to([0, 1.7, 0])
        self.register_content(block)
        self.play(LaggedStart(*[FadeIn(c) for c in block], lag_ratio=0.08))

        # 3. annotate what the narration is talking about
        ...

        # 4. settle: hold the final frame to the scene's declared duration
        self.settle()
```

Four things make a Manimations scene: a header, a diagram built in steps, an
emphasis on the element being narrated, and a `settle()`.

## Rules that keep the look coherent

1. **Never hard-code a colour or font size.** Take them from `self.theme`
   (`t.cyan`, `t.sizes.body`, `t.spacing.lg`). This is what makes every scene
   look like the same channel.

2. **Register what you draw.** Call `self.register_content(...)` on the
   top-level mobjects so the QA pass can check them for clipping.

3. **Build, don't reveal.** A diagram that appears all at once reads as a
   slide. Reveal it in the order the narration introduces the parts:

   ```python
   self.play(timing.fade_in_stagger([host, router, server], lag=0.18))
   ```

4. **Use semantic accents.** IPv4 is always amber, IPv6 violet, prefixes green,
   legacy constraints rose. Reuse the same idea → same colour everywhere.

5. **Let the narration carry the detail.** On-screen text is a label, not a
   transcript. One short phrase beats a sentence.

6. **End with `self.settle()`.** The pipeline tells each scene its declared
   duration via the `MANIMATIONS_SCENE_SPEC` environment variable, and `settle()`
   pads the scene to exactly that length — so the animation stays in sync with
   the voiceover. If you skip it, the scene will be shorter than its narration.

## Narration sync

The declared `duration` in `project.yaml` is the contract between the animation
and the voice:

- `settle()` holds the last frame until the elapsed time reaches `duration`.
- If your animations already run *longer* than `duration`, the scene is simply
  as long as the animations; adjust the duration in the brief.
- The renderer passes the duration in through the environment, so scene files
  need no import of the project config.

**Avoid long silent tails.** A declared duration is a guess; if it exceeds the
narration, the scene freezes after the voice stops. Run the final render with
`--fit-narration` and the pipeline measures the real speech, sets each scene's
duration to it (plus `--tail`, default 0.6s), and writes the result back to the
brief:

```bash
uv run manimations final myslug --voiceover --fit-narration
```

## Orientation

Scenes are orientation-agnostic: both landscape (1920×1080) and vertical
(1080×1920) keep the frame height at 8 scene units, so vertical is just a
narrower frame. Use the layout helpers rather than fixed x-coordinates and your
scene works in both:

```python
layout.safe_width()                     # adapts to the orientation
layout.columns(3, total_width=layout.safe_width(), gap=0.3)
layout.fit_width(block, layout.safe_width() - 0.5)
```

Set the orientation in the brief (`orientation: vertical`) or per render with
`--orientation vertical`. Vertical gives you less horizontal room, so prefer
stacked layouts (`rows`) over side-by-side ones (`columns`) when you want a
scene to look good in both.

## Emphasis techniques

| Goal | Component |
| --- | --- |
| Stress a word in a sentence | `typography.highlight_phrase(text, "word", color=...)` |
| Spotlight a whole element | `self.play(Indicate(target, color=...))` |
| Point at something | `surfaces.annotation_arrow(target, "note")` |
| Compare two things | `data.comparison("A", [...], "B", [...])` |
| Count up to a figure | `data.counter(...)` + `cnt.tracker.animate.set_value(...)` |
| Show a span of time | `data.timeline([("1998", "standardised"), ...])` |
| Show how full something is | `data.meter(fraction)` |

## Checking your work

```bash
uv run manimations preview myslug          # renders + QA + contact sheets
#   open projects/myslug/build/qa/*_sheet.png
uv run manimations qa --project myslug     # frame-level report only
```

The QA pass measures the bounding box of everything you drew against the safe
area, so a clipped or off-screen element shows up as a warning with the frame
index — before you spend time on a final render.

## Layout helpers

```python
from manimations.helpers import layout

layout.safe_width()            # usable width inside the margins
layout.fit_width(mob, 5.0)     # scale down to fit, never scale up
layout.columns(4, total_width=..., gap=0.3)   # x-centres for N columns
layout.rows(3, total_height=..., gap=0.4)     # y-centres for N rows
```

Position blocks with these rather than magic numbers; it is the difference
between a layout that survives a text change and one that clips.
