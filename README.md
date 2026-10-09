# Sleep Music Studio (`sleepgen`)

Long-form sleep and calm music, composed and rendered locally by code. The plan is to
make 15-minute instrumental songs and string them into 1–3 hour videos.

- **Local and free.** Plain Python on a Mac or Windows PC. No GPU, subscription, credits or limits.
- **Original.** Every note is composed by the engine from a style recipe plus a random
  seed. Nothing is sampled from other people's music.
- **Synced through GitHub.** Code, styles and notes live in this repo, so the Mac and the PC
  share them. Big audio files stay out of git and go to Google Drive instead (see below).
  Any machine can also re-render a song from its style + seed.
- **Repeatable.** Same style + same seed + same engine version gives the same song (same notes,
  chords and mix) on any machine.

## Quick start

**Windows** (the main machine). Run this in PowerShell:

```powershell
winget install Python.Python.3.12 Gyan.FFmpeg Git.Git
git clone https://github.com/Gammaclaw/Work.git; cd Work
py -m venv .venv; .venv\Scripts\Activate.ps1   # if blocked: Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
pip install -r requirements.txt
python -m sleepgen render styles/ocean_night.yaml --minutes 3 --mp3
```

**Mac** (install [Homebrew](https://brew.sh) first):

```bash
brew install python ffmpeg git
git clone https://github.com/Gammaclaw/Work.git && cd Work
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python -m sleepgen render styles/ocean_night.yaml --minutes 3 --mp3
```

Each render writes three files to `output/songs/`, or to Google Drive once that's set up (below):

- a 24-bit WAV (master quality)
- an MP3 for listening
- a JSON with the key, chords and seed

## Save renders to Google Drive

Renders are big (about 260 MB per 15-minute WAV), so they live in Google Drive rather than git.
The folder `My Drive/Sleep Music Studio` already exists.

1. Install [Google Drive for Desktop](https://www.google.com/drive/download/) on each machine and sign in.
2. Point sleepgen at the folder once per machine, then open a new terminal:
   - **Windows:** `setx SLEEPGEN_OUTPUT "G:\My Drive\Sleep Music Studio"` (use your Drive's letter if it isn't G:)
   - **Mac:** `echo 'export SLEEPGEN_OUTPUT="$HOME/Library/CloudStorage/GoogleDrive-<your Google email>/My Drive/Sleep Music Studio"' >> ~/.zshrc`

From then on every render lands in `Sleep Music Studio/songs/` and shows up on both machines and
on your phone. Pass `--out` to send a single render somewhere else.

## Commands

```text
python -m sleepgen render STYLE.yaml [--minutes 15] [--seed N] [--mp3] [--report]
                                     [--set KEY=VALUE ...] [--tag LABEL] [--out DIR]
python -m sleepgen analyze FILE.wav [--png picture.png]
```

- `--seed`: the same seed always gives the same song. Leave it out to get a new song; the seed
  it used is printed and saved in the JSON.
- `--report`: saves a spectrogram and loudness picture. This is how Claude checks a render, since it can't hear audio.
- `--set` / `--tag`: try a change without editing the style file, for A/B comparisons. For example,
  `--set drone.gain_db=-20 --tag hum-faint` renders the same song with a quieter hum and adds
  `_hum-faint` to the file name.

## Styles

A style is a small YAML recipe in `styles/`. Each song picks a key from the style's list,
then composes fresh chords and melodies from its seed.

| Style | Feel |
|---|---|
| `warm_drift` | Floating major-key pads, a low drone, a distant felt piano, faint brown noise |
| `ocean_night` | Muted minor pads, a faint low hum, rare glass notes, rolling waves (the lead style) |
| `ocean_night_piano` | Take: Ocean Night with soft felt-piano phrases instead of the glass notes |
| `ocean_night_drift` | Take: Ocean Night slower and darker, with the waves moved forward |
| `ocean_night_whales` | Take: Ocean Night plus distant whale calls that glide between notes of the key |
| `rain_cabin` | Felt piano (slow left-hand arpeggios and a simple melody), quiet pads, steady rain |

**Takes.** A take starts with `extends: <style>` and lists only what it changes. Every part of a
song (chords, pads, melody, waves, whales ...) has its own random stream, so a take rendered
with the same seed as its base keeps everything it doesn't change identical. That makes A/B
listening clean: the only difference you hear is the change.

The main settings:

| Setting | What it does |
|---|---|
| `mode` | `lydian` dreamy, `ionian` plain major, `dorian` / `aeolian` darker |
| `chords.seconds` | How slowly the harmony moves |
| `tempo` | Locks chords, arpeggio and melody to one beat |
| `pad.brightness` | How bright the pads sound |
| `melody.density` | How often melodic phrases appear |
| `texture.type` | `brown`, `ocean`, `rain` or `none` |
| `whales` | Adds distant whale calls (`gain_db`, `range`, `gap_seconds`) |
| `reverb.seconds` | How big the room sounds |
| `master.lufs` | Final loudness |

## How it works

```text
style + seed
  -> composer: key, chords in AABA cycles, recurring melodic motifs, an energy arc
  -> instruments: shimmering additive pads, drone, felt piano / glass, arpeggios, noise beds,
     whale calls
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
