# Listening log

Feedback on renders, newest first. Each entry records:

- the date
- the render (style, seed, length)
- what worked and what didn't
- what changed afterwards

Any render can be recreated with
`python -m sleepgen render styles/<style>.yaml --seed <seed> --minutes <length> --mp3`.

## 2026-10-05: first feedback

- **Favourite: Ocean Night**, especially the waves. This is the lead direction for the channel.
- **The hum (low drone) was too strong** in Warm Drift and Ocean Night.
  - Warm Drift's drone went from -6 to -12 dB.
  - Ocean Night's drone went from -8 to -14 dB.
- **A/B sent, same seed 11, 3 minutes.** The hum's share of the total sound energy:
  - the original: 26%
  - `hum-soft` (-14, the new default): 10%
  - `hum-faint` (`--set drone.gain_db=-20`): 5%
- Choice between soft and faint: *pending*. More feedback is coming after re-listening.

## 2026-10-05: first sketches (engine v0.1.0)

Renders (3-minute previews, seed 11):

- `warm_drift`: D lydian, Dmaj7, Aadd9, Eadd9, Bm7, D, Amaj7, Dadd9
- `ocean_night`: A aeolian, Asus2, Fadd9, Cadd9, Fmaj7, Amadd9
- `rain_cabin`: C ionian, Cmaj7, Gadd9, Dmadd9, Gadd9 ... C

Full length: `warm_drift`, seed 2026, 15 minutes.

Feedback: *pending. Which direction is closest, and what should change (darker or brighter,
more or less piano, nature sounds or not, slower)?*
