# Sleep Music Studio (`sleepgen`)

Long-form sleep and calm music, composed and rendered locally by code. The plan is to
make 15-minute instrumental songs and string them into 1–3 hour videos.

- **Local and free.** Plain Python on a Mac or Windows PC. No GPU, subscription, credits or limits.
- **Original.** Every note is composed by the engine from a style recipe plus a random
  seed. Nothing is sampled from other people's music.
- **Synced through GitHub.** Code, styles and notes live in this repo, so the Mac and the PC
  share them. Big audio files stay out of git. Any machine can re-render a song exactly
  from its style + seed, or you can sync `output/` with Google Drive, iCloud or OneDrive.
- **Repeatable.** Same style + same seed + same engine version gives identical audio.

## Quick start

**Mac** (install [Homebrew](https://brew.sh) first):

```bash
brew install python ffmpeg git
git clone https://github.com/Gammaclaw/Work.git && cd Work
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python -m sleepgen render styles/warm_drift.yaml --minutes 3 --mp3
```

**Windows** (PowerShell):

```powershell
winget install Python.Python.3.12 Gyan.FFmpeg Git.Git
git clone https://github.com/Gammaclaw/Work.git; cd Work
py -m venv .venv; .venv\Scripts\Activate.ps1   # if blocked: Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
pip install -r requirements.txt
python -m sleepgen render styles/warm_drift.yaml --minutes 3 --mp3
```

Each render writes to `output/songs/`:

- a 24-bit WAV (master quality)
- an MP3 for listening
- a JSON with the key, chords and seed

## Commands

```text
python -m sleepgen render STYLE.yaml [--minutes 15] [--seed N] [--mp3] [--report] [--out DIR]
python -m sleepgen analyze FILE.wav [--png picture.png]
```

- `--seed`: the same seed always gives the same song. Leave it out to get a new song; the seed
  it used is printed and saved in the JSON.
- `--report`: saves a spectrogram and loudness picture. This is how Claude checks a render, since it can't hear audio.

## Styles

A style is a small YAML recipe in `styles/`. Each song picks a key from the style's list,
then composes fresh chords and melodies from its seed.

| Style | Feel |
|---|---|
| `warm_drift` | Floating major-key pads, a low drone, a distant felt piano, faint brown noise |
| `ocean_night` | Dark minor drone, muted pads, rare glass notes, rolling waves |
| `rain_cabin` | Felt piano (slow left-hand arpeggios and a simple melody), quiet pads, steady rain |

The main settings:

| Setting | What it does |
|---|---|
| `mode` | `lydian` dreamy, `ionian` plain major, `dorian` / `aeolian` darker |
| `chords.seconds` | How slowly the harmony moves |
| `tempo` | Locks chords, arpeggio and melody to one beat |
| `pad.brightness` | How bright the pads sound |
| `melody.density` | How often melodic phrases appear |
| `texture.type` | `brown`, `ocean`, `rain` or `none` |
| `reverb.seconds` | How big the room sounds |
| `master.lufs` | Final loudness |

## How it works

```text
style + seed
  -> composer: key, chords in AABA cycles, recurring melodic motifs, an energy arc
  -> instruments: shimmering additive pads, drone, felt piano / glass, arpeggios, noise beds
  -> mix: every layer set to a target loudness, ping-pong echo, synthetic hall reverb
  -> master: low cut, soft high roll-off, fades, final loudness (-18 LUFS by default)
```

The rules are calm by construction:

- no diminished chords, and tense chords are softened
- melodies stay on pentatonic notes
- the level stays steady, with no sudden jumps

## Roadmap

1. **Done:** v0.1 engine with three test styles, 15-minute songs and analysis reports.
2. Dial in the sound together (listen, give feedback, tweak), then lock 3–5 signature styles.
3. Competitor research (VidIQ): which sub-niches, lengths, titles and thumbnails work.
4. Long-form builder: string songs into 1–3 hour mixes with crossfades and chapter timestamps.
5. Video: Higgsfield background art or a slow loop, rendered with ffmpeg into a YouTube-ready MP4.
6. Richer instruments: real sampled piano and strings (free CC0 / CC-BY libraries), and/or
   [ACE-Step 1.5](https://github.com/ace-step/ACE-Step-1.5) (a local AI music model, MIT license, runs on Mac and PC).
7. One command from style to finished video, plus batch and scheduled runs.

## Layout

```text
sleepgen/   the engine: theory, compose, synth, textures, effects, song, analyze, CLI
styles/     style recipes (YAML)
docs/       listening log and notes
tests/      quick smoke test (pip install pytest && pytest)
output/     renders (not in git)
```
