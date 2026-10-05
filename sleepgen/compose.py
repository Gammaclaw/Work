"""The composer: a song's energy arc, its chord timeline and its melodic phrases."""
from __future__ import annotations

import bisect
from dataclasses import dataclass

import numpy as np

from .theory import CHORD_SHAPES, CHORD_WEIGHTS, MELODY_DEGREES, MODES, Chord, make_chord

# Energy over the song (0 = barely there, 1 = fullest), as six evenly spaced points.
ARCS = {
    "arch": [0.15, 0.45, 0.7, 0.65, 0.4, 0.1],  # rise, bloom, settle
    "descend": [0.5, 0.55, 0.45, 0.35, 0.2, 0.05],  # keeps sinking: good for deep sleep
    "flat": [0.4, 0.45, 0.45, 0.45, 0.4, 0.3],
}


def intensity_arc(duration: float, points: int, rng: np.random.Generator, shape: str = "arch") -> np.ndarray:
    """Slowly varying 0..1 energy curve with `points` samples spread over `duration` seconds."""
    if shape not in ARCS:
        raise ValueError(f"unknown arc {shape!r}; use one of {sorted(ARCS)}")
    knots = np.array(ARCS[shape]) + rng.uniform(-0.07, 0.07, len(ARCS[shape]))
    x = np.linspace(0.0, 1.0, points) * (len(knots) - 1)
    seg = np.minimum(x.astype(int), len(knots) - 2)
    w = (1 - np.cos(np.pi * (x - seg))) / 2  # cosine ease between knots
    arc = knots[seg] * (1 - w) + knots[seg + 1] * w
    t = np.linspace(0.0, duration, points)
    arc += 0.05 * np.sin(2 * np.pi * t / rng.uniform(70, 110) + rng.uniform(0, 2 * np.pi))
    return np.clip(arc, 0.0, 1.0)


def _pick_shape(rng: np.random.Generator, colors: dict[str, float]) -> str:
    names = [name for name in colors if name in CHORD_SHAPES]
    weights = np.array([colors[name] for name in names], dtype=float)
    return str(rng.choice(names, p=weights / weights.sum()))


def _make_cycle(mode: str, rng: np.random.Generator, length: int, colors: dict[str, float],
                degrees: list[int] | None = None) -> list[tuple[int, str]]:
    """One repeating chord cycle of (degree, colour) pairs, starting on the home chord."""
    if degrees:
        return [((d - 1) % 7, _pick_shape(rng, colors)) for d in degrees]  # style files count from 1
    weights = CHORD_WEIGHTS[mode]
    degs = [0]
    while len(degs) < length:
        options = [d for d in weights if d != degs[-1]]
        if len(degs) == length - 1:  # the cycle loops back to the home chord next
            options = [d for d in options if d != 0]
        w = np.array([weights[d] for d in options])
        degs.append(int(rng.choice(options, p=w / w.sum())))
    return [(d, _pick_shape(rng, colors)) for d in degs]


def chord_timeline(tonic: int, mode: str, duration: float, rng: np.random.Generator, cfg: dict) -> list[Chord]:
    """Chords for the whole song: two cycles (A and B) in an AABA pattern, ending at home."""
    lo, hi = cfg.get("seconds", [20, 30])
    length = int(cfg.get("cycle_length", 4))
    colors = cfg.get("colors", {"add9": 3, "seventh": 2, "sus2": 1, "triad": 1})
    variation = float(cfg.get("variation", 0.25))
    fixed = cfg.get("degrees")
    bar = cfg.get("bar_seconds")  # set when the style has a shared tempo: chords change on bar lines
    cycles = {"A": _make_cycle(mode, rng, length, colors, fixed)}
    cycles["B"] = cycles["A"] if fixed else _make_cycle(mode, rng, length, colors)

    chords: list[Chord] = []
    t = 0.0
    for i in range(10_000):
        for degree, shape in cycles["AABA"[i % 4]]:
            if rng.random() < variation:  # same root movement, fresh colour
                shape = _pick_shape(rng, colors)
            dur = rng.uniform(lo, hi)
            if bar:
                dur = max(bar, round(dur / bar) * bar)
            if t + dur + lo > duration:
                break
            chord = make_chord(tonic, mode, degree, shape)
            chord.start, chord.end = t, t + dur
            chords.append(chord)
            t += dur
        else:
            continue
        break
    # Resolve home for the ending.
    if chords and chords[-1].degree == 0:
        chords[-1].end = duration
    else:
        last = make_chord(tonic, mode, 0, _pick_shape(rng, colors))
        last.start, last.end = t, duration
        chords.append(last)
    return chords


def chord_at(chords: list[Chord], t: float) -> Chord:
    i = bisect.bisect_right([c.start for c in chords], t) - 1
    return chords[max(0, min(i, len(chords) - 1))]


@dataclass
class Note:
    time: float  # seconds
    midi: int
    velocity: float  # 0..1


def _make_motif(rng: np.random.Generator) -> list[tuple[int, float, float]]:
    """A short idea: (scale-step offset, onset in beats, relative velocity) per note."""
    length = int(rng.integers(3, 6))
    steps = [0] + list(rng.choice([-2, -1, -1, 1, 1, 2, 3], size=length - 1))
    offsets = np.cumsum(steps)
    onsets = np.concatenate([[0.0], np.cumsum(rng.choice([1.0, 1.5, 2.0, 2.0, 3.0], size=length - 1))])
    vels = np.clip(0.9 - 0.08 * np.arange(length) + rng.uniform(-0.08, 0.08, length), 0.4, 1.0)
    return [(int(o), float(t), float(v)) for o, t, v in zip(offsets, onsets, vels)]


def _vary(motif: list[tuple[int, float, float]], rng: np.random.Generator) -> list[tuple[int, float, float]]:
    """Repeat the idea, often with a small change, so phrases feel related but not looped."""
    m = list(motif)
    r = rng.random()
    if r < 0.35:
        pass
    elif r < 0.55 and len(m) > 3:
        m = m[:-1]
    elif r < 0.75:
        i = int(rng.integers(1, len(m)))
        m[i] = (m[i][0] + int(rng.choice([-1, 1])), m[i][1], m[i][2])
    elif r < 0.9:
        m = [(-o, t, v) for o, t, v in m]
    else:
        offsets = [o for o, _, _ in m][::-1]
        m = [(offsets[i] - offsets[0], t, v) for i, (_, t, v) in enumerate(m)]
    return [(o, max(0.0, t + rng.uniform(-0.06, 0.06)) if t else 0.0, v) for o, t, v in m]


def compose_arpeggio(chords: list[Chord], duration: float, arc_at, rng: np.random.Generator,
                     cfg: dict) -> list[Note]:
    """A slow left-hand broken chord (root, fifth, then the colour tones an octave up)."""
    lo, hi = cfg.get("range", [43, 72])
    pattern = cfg.get("pattern", [0, 1, 2, 3, 2, 1])
    step = float(cfg.get("beats_per_note", 2)) * 60.0 / float(cfg.get("tempo", 60))
    base_vel = float(cfg.get("velocity", 0.4))
    tail = float(cfg.get("tail_seconds", 15))
    notes: list[Note] = []
    for chord in chords:
        root = lo + (chord.root - lo) % 12
        tones = [root] + ([root + 7] if 7 in chord.intervals else [])
        tones += sorted(root + 12 + iv % 12 for iv in chord.intervals if iv % 12 not in (0, 7))
        tones = [m for m in tones if m <= hi] or [root]
        t, i = chord.start, 0
        while t < min(chord.end, duration - tail):
            level = arc_at(t)
            if i == 0 or rng.random() > 0.35 * (1.0 - level):  # thin out in the quiet parts
                vel = base_vel * (1.15 if i == 0 else 1.0) * (0.7 + 0.5 * level) * rng.uniform(0.9, 1.05)
                midi = tones[pattern[i % len(pattern)] % len(tones)]
                notes.append(Note(max(0.0, t + rng.uniform(-0.015, 0.015)), midi, vel))
            t += step
            i += 1
    return notes


def compose_melody(chords: list[Chord], tonic: int, mode: str, duration: float, arc_at,
                   rng: np.random.Generator, cfg: dict) -> list[Note]:
    """Sparse phrases built from one recurring motif, with long rests between them."""
    lo, hi = cfg.get("range", [62, 86])
    allowed = {(tonic + MODES[mode][d]) % 12 for d in MELODY_DEGREES[mode]}
    scale = [m for m in range(lo, hi + 1) if m % 12 in allowed]
    beat = 60.0 / float(cfg.get("tempo", 56))
    density = float(cfg.get("density", 0.5))
    rest_lo, rest_hi = cfg.get("rest_seconds", [8, 24])
    base_vel = float(cfg.get("velocity", 0.55))
    tail = float(cfg.get("tail_seconds", 25))
    center = len(scale) // 2

    motif = _make_motif(rng)
    notes: list[Note] = []
    last = center
    t = min(25.0, duration * 0.12)
    while t < duration - tail:
        level = arc_at(t)
        if rng.random() < density * (0.3 + 0.7 * level):
            if cfg.get("quantize"):  # play in time with the arpeggio
                t = float(np.ceil(t / beat) * beat)
            chord = chord_at(chords, t)
            tones = np.array([i for i, m in enumerate(scale) if m % 12 in chord.pcs] or range(len(scale)))
            w = np.exp(-np.abs(tones - last) / 2.5 - np.abs(tones - center) / 6.0)
            start = int(rng.choice(tones, p=w / w.sum()))
            phrase = _vary(motif, rng)
            end = t + phrase[-1][1] * beat
            if end > duration - tail:
                break
            for offset, onset, vel in phrase:
                i = int(np.clip(start + offset, 0, len(scale) - 1))
                notes.append(Note(t + onset * beat, scale[i], base_vel * vel * (0.75 + 0.5 * level)))
            last = int(np.clip(start + phrase[-1][0], 0, len(scale) - 1))
            if rng.random() < 0.3:  # a soft harmony note under the phrase ending
                notes.append(Note(end, scale[max(0, last - 2)], notes[-1].velocity * 0.7))
            if rng.random() < float(cfg.get("new_idea", 0.15)):
                motif = _make_motif(rng)
            t = end + beat * rng.uniform(2, 4)
        t += rng.uniform(rest_lo, rest_hi) * (1.3 - 0.6 * level)
    return notes
