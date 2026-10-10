# The WSL Trick That Feels Illegal (usbipd)

Episode 2 of the *Developer & Power-User Black Magic* series — a vertical 9:16
Short for YouTube Shorts / TikTok / Instagram Reels.

Pass a physical USB device (microcontroller, flash drive, controller) straight
through to WSL 2 with [usbipd-win](https://github.com/dorssel/usbipd-win), so
Linux can see hardware Windows normally holds.

## Commands shown (verified, not copied from the draft script)

Checked against usbipd-win **5.3.0** installed on this machine (`usbipd --help`,
`usbipd list`, `usbipd bind --help`, `usbipd attach --help`) and Microsoft's
[Connect USB devices](https://learn.microsoft.com/en-us/windows/wsl/connect-usb)
doc:

```powershell
usbipd list                          # find the bus ID (no elevation needed)
usbipd bind --busid 4-4              # share it  — REQUIRES Administrator
usbipd attach --wsl --busid 4-4      # pipe it into WSL — no elevation
```

```bash
lsusb                                # it now appears inside Linux
```

**Two corrections to the source script**, both verified rather than stylistic:

- The draft used `usbipd wsl list` / `usbipd wsl attach`. That spelling was
  removed in usbipd-win **4.0.0** and errors out on 5.x —
  `usbipd: error: The 'wsl' subcommand has been removed.` The video shows the
  current syntax.
- The draft's "instead of dual-booting" is dropped. usbipd-win redirects a
  device to WSL 2; it is not a dual-boot replacement.

## Narration

Engine: **voxcpm-gguf** (quantized VoxCPM2 via llama.cpp-omni, 8 GPU layers —
the 4 GB card default).

Acronyms are spelled out as separate letters in `project.yaml` (`W S L`,
`U S B`, `U S B I P D`, `L S U S B`). That is deliberate: synthesised both ways
and transcribed with faster-whisper, voxcpm-gguf reads `usbipd` written as one
word as **"SBIPT"** and `lsusb` garbled, while the spaced forms come back as
"USB IPD" and "LSUSB" correctly.

## Build

```bash
uv run manimations validate usbipd
uv run manimations preview  usbipd
uv run manimations final    usbipd --voiceover --engine voxcpm-gguf \
                                   --fit-narration --subtitles
uv run python projects/usbipd/mix_sfx.py     # narration + placed SFX
```

`mix_sfx.py` writes `build/usbipd_with_sfx.m4a`; mux it over the render:

```bash
ffmpeg -y -i projects/usbipd/build/usbipd_final.mp4 \
          -i projects/usbipd/build/usbipd_with_sfx.m4a \
       -map 0:v -map 1:a -map 0:s? -c:v copy -c:a copy -c:s mov_text \
       -movflags +faststart projects/usbipd/build/usbipd_reel.mp4
```

`build/usbipd_reel.mp4` is the deliverable: video + narration + SFX + soft subs.

## Sound effects

Four CC0 Freesound clips in `assets/sfx/` (credited in `credits.txt`): a whoosh
on three scene changes and key clacks where the commands are typed. Cue times
come from the **rendered** clip durations, so they survive narration re-fitting.

The effects are summed as a **balanced tree of pairwise `amix`** nodes, not one
`amix` over all seven streams. A single multi-input `amix` silently drops the
last input: measured here, the outro whoosh came out at -91 dBFS (digital
silence) while every other cue measured -20 to -36 dBFS.
