# CLAUDE.md

Long-form sleep and calm music (instrumental), made locally by code. The goal is 15-minute
songs strung into 1–3 hour videos. The owner works from a Mac and a Windows PC, and this
GitHub repo is the sync point between them. See README.md for setup and the roadmap.

## Owner setup

- **Purpose:** a YouTube channel. Lead direction: night ocean (the `ocean_night` style). See
  `docs/competitor-notes.md`.
- **Main machine:** Windows PC with an RTX 5070 Ti (16 GB VRAM). Do GPU and AI-model work
  there; this engine itself only uses the CPU.
- **Second machine:** MacBook Pro 14" (M1 Pro, 16 GB).
- **Renders:** go to Google Drive, `My Drive/Sleep Music Studio`, via Google Drive for Desktop
  and the `SLEEPGEN_OUTPUT` environment variable. The Drive connector can't upload large audio,
  so don't try.
- **VidIQ credits are limited** (about 150 per month renewable; a search costs 5). Keep research
  focused and say how many credits it used.

## Ground rules

- Keep the engine plain Python (numpy, scipy, soundfile, pyloudnorm, PyYAML), so it runs
  the same on macOS and Windows without a GPU. Heavy extras (AI models, samplers) must be
  optional imports.
- Never commit rendered audio or video; `output/` is gitignored. Songs are reproducible from
  style + seed + engine version. Bump `__version__` in `sleepgen/__init__.py` whenever a
  change alters how existing seeds sound.
- All music is generated and instrumental. Competitors are inspiration only (traits such as
  tempo, instrumentation, length, sub-niche). Never copy their melodies or use their audio.
- Calm by construction: no sudden level jumps, no harsh highs, no tense harmony.

## Working loop

- Render with `python -m sleepgen render styles/<style>.yaml --minutes 3 --seed N --mp3 --report`.
- Claude can't hear audio. Check each render with its `--report` PNG (spectrogram and level
  over time) and its JSON (key, chords, note counts), then ask the owner to listen.
- Log the owner's listening feedback in `docs/listening-log.md`, and read it before tuning a style.
- To try an idea, make a take: a style with `extends: <base>` that lists only the change. Render it
  with the same seed as the base (every part has its own random stream), so the owner hears only
  the change. Use `--set` / `--tag` for quick one-off variants.
- Run `pytest` (the smoke test renders every style briefly) before pushing engine changes.
- Higgsfield MCP cannot generate music (speech only). Use it for visuals: backgrounds, loops,
  thumbnails. Use VidIQ for competitor and keyword research.

## Layout

| Module | Role |
|---|---|
| `sleepgen/theory.py` | Modes, soft chords, voice leading |
| `sleepgen/compose.py` | Energy arc, chord timeline (AABA cycles), motifs, arpeggios |
| `sleepgen/synth.py` | Additive pads, felt piano and glass instruments |
| `sleepgen/textures.py` | Brown noise, ocean, rain, whale calls |
| `sleepgen/effects.py` | Filters, echo, reverb, loudness, mastering |
| `sleepgen/song.py` | Style + seed to a mixed, mastered song |
| `sleepgen/analyze.py` | Loudness and spectrogram report |
| `sleepgen/__main__.py` | CLI |
