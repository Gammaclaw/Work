# Listening log

Feedback on renders, newest first. Each entry records:

- the date
- the render (style, seed, length)
- what worked and what didn't
- what changed afterwards

Any render can be recreated with
`python -m sleepgen render styles/<style>.yaml --seed <seed> --minutes <length> --mp3`.

## 2026-10-09: hum chosen, round 2 takes (engine v0.2.0)

- **Hum:** the owner picked `hum-faint`, so Ocean Night's drone is now -20 dB by default.
- **Engine v0.2.0:** every part has its own random stream. v0.1 renders (seed 11 and the
  15-minute Warm Drift) now need the v0.1 commit (`f05aadb`) to reproduce exactly.
- **Round 2: three takes on Ocean Night**, all seed 21 and 3 minutes, in C aeolian
  (Cm7, Ebmaj7, Bbadd9, Fm, Cm7):
  - `ocean_night`: the base, with the faint hum and 7 glass notes.
  - `ocean_night_piano` (Moonlit Piano): 20 soft felt-piano notes replace the glass. Same chords
    and waves as the base.
  - `ocean_night_drift` (Deep Drift): chords hold 42–64 s (4 chords), darker pads, waves
    +3 dB, 11 s reverb, 1 dB quieter overall.
  - `ocean_night_whales` (Whale Song): the base plus whale calls, about 8 dB under the mix while
    calling. Same chords, glass notes and waves as the base.
- **Fixed before sending:** Deep Drift's pads were first moved lower, which made a low voice
  throb about 1.5 times a second. They went back to the base register with a narrower detune.
- Feedback: *pending*.

## 2026-10-05: first feedback

- **Favourite: Ocean Night**, especially the waves. This is the lead direction for the channel.
- **The hum (low drone) was too strong** in Warm Drift and Ocean Night.
  - Warm Drift's drone went from -6 to -12 dB.
  - Ocean Night's drone went from -8 to -14 dB.
- **A/B sent, same seed 11, 3 minutes.** The hum's share of the total sound energy:
  - the original: 26%
  - `hum-soft` (-14, the new default): 10%
  - `hum-faint` (`--set drone.gain_db=-20`): 5%
- Choice between soft and faint: **faint** (decided 2026-10-09).

## 2026-10-05: first sketches (engine v0.1.0)

Renders (3-minute previews, seed 11):

- `warm_drift`: D lydian, Dmaj7, Aadd9, Eadd9, Bm7, D, Amaj7, Dadd9
- `ocean_night`: A aeolian, Asus2, Fadd9, Cadd9, Fmaj7, Amadd9
- `rain_cabin`: C ionian, Cmaj7, Gadd9, Dmadd9, Gadd9 ... C

Full length: `warm_drift`, seed 2026, 15 minutes.

Feedback: *pending. Which direction is closest, and what should change (darker or brighter,
more or less piano, nature sounds or not, slower)?*
