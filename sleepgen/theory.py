"""Music theory: keys, modes, soft chords and smooth voice leading.

The rules are "calm by construction": diminished chords are never used, tense
dominant sevenths are softened, and close dissonances (minor seconds / ninths)
are kept out of pad voicings. Whatever the random seed, nothing should jolt a
sleeping listener.
"""
from __future__ import annotations

import itertools
from dataclasses import dataclass

import numpy as np

PITCH_CLASSES = {
    "C": 0, "C#": 1, "DB": 1, "D": 2, "D#": 3, "EB": 3, "E": 4, "F": 5, "F#": 6,
    "GB": 6, "G": 7, "G#": 8, "AB": 8, "A": 9, "A#": 10, "BB": 10, "B": 11,
}
NOTE_NAMES = ["C", "Db", "D", "Eb", "E", "F", "F#", "G", "Ab", "A", "Bb", "B"]

MODES = {
    "ionian": [0, 2, 4, 5, 7, 9, 11],
    "dorian": [0, 2, 3, 5, 7, 9, 10],
    "lydian": [0, 2, 4, 6, 7, 9, 11],
    "mixolydian": [0, 2, 4, 5, 7, 9, 10],
    "aeolian": [0, 2, 3, 5, 7, 8, 10],
}
MODE_ALIASES = {"major": "ionian", "minor": "aeolian"}

# Chord roots (0-based scale degrees) that sound soft in each mode, and how often
# to use them. Each mode's diminished triad is left out on purpose.
CHORD_WEIGHTS = {
    "ionian": {0: 3.0, 1: 1.5, 2: 1.0, 3: 2.5, 4: 1.0, 5: 2.5},
    "dorian": {0: 3.0, 1: 1.5, 2: 2.0, 3: 2.5, 4: 1.0, 6: 2.0},
    "lydian": {0: 3.0, 1: 2.5, 2: 1.0, 4: 1.5, 5: 2.0, 6: 1.0},
    "mixolydian": {0: 3.0, 1: 1.0, 3: 2.5, 4: 1.0, 5: 1.5, 6: 2.0},
    "aeolian": {0: 3.0, 2: 2.0, 3: 2.0, 4: 1.0, 5: 2.5, 6: 2.0},
}

# Scale degrees melodies may use: pentatonic-style subsets, so no note rubs hard
# against whatever chord is underneath.
MELODY_DEGREES = {
    "ionian": [0, 1, 2, 4, 5],
    "dorian": [0, 2, 3, 4, 6],
    "lydian": [0, 1, 2, 3, 4, 5],
    "mixolydian": [0, 1, 2, 4, 5],
    "aeolian": [0, 2, 3, 4, 6],
}

# Chord colours, as scale steps stacked on the chord root.
CHORD_SHAPES = {
    "triad": [0, 2, 4],
    "sus2": [0, 1, 4],
    "add9": [0, 2, 4, 8],
    "seventh": [0, 2, 4, 6],
    "ninth": [0, 2, 4, 6, 8],
}

ROMAN = ["I", "II", "III", "IV", "V", "VI", "VII"]


def parse_key(name: str) -> int:
    try:
        return PITCH_CLASSES[str(name).strip().upper()]
    except KeyError:
        raise ValueError(f"unknown key {name!r}") from None


def parse_mode(name: str) -> str:
    mode = MODE_ALIASES.get(str(name).lower(), str(name).lower())
    if mode not in MODES:
        raise ValueError(f"unknown mode {name!r}; use one of {sorted(MODES)}")
    return mode


def scale_step(mode: str, step: int) -> int:
    """Semitones above the tonic for a scale step (steps past 6 go up an octave)."""
    return MODES[mode][step % 7] + 12 * (step // 7)


@dataclass
class Chord:
    degree: int  # 0-based scale degree of the root
    root: int  # pitch class of the root
    intervals: list[int]  # semitones above the root, ascending
    minor: bool  # quality of the plain diatonic triad on this degree
    start: float = 0.0  # seconds
    end: float = 0.0

    @property
    def pcs(self) -> list[int]:
        return [(self.root + i) % 12 for i in self.intervals]

    @property
    def roman(self) -> str:
        numeral = ROMAN[self.degree]
        return numeral.lower() if self.minor else numeral

    @property
    def name(self) -> str:
        s = {i % 12 for i in self.intervals}
        root = NOTE_NAMES[self.root]
        if 4 in s:
            quality = ""
        elif 3 in s:
            quality = "m"
        else:
            return root + "sus2"
        seventh = "maj7" if 11 in s else "7" if 10 in s else ""
        ninth = 2 in s
        if seventh and ninth:
            return root + quality + seventh.replace("7", "9")
        return root + quality + seventh + ("add9" if ninth else "")


def make_chord(tonic: int, mode: str, degree: int, shape: str) -> Chord:
    base = scale_step(mode, degree)
    third = scale_step(mode, degree + 2) - base
    ninth = scale_step(mode, degree + 8) - base
    ivs = {scale_step(mode, degree + s) - base for s in CHORD_SHAPES[shape]}
    if 1 in ivs:  # "sus2" landed on a minor second: use the plain triad instead
        ivs = {0, third, 7}
    ivs.discard(13)  # never a flat nine
    if 4 in ivs and 10 in ivs:  # dominant seventh is too tense: swap it for a ninth
        ivs.discard(10)
        if ninth == 14:
            ivs.add(14)
    return Chord(degree, (tonic + base) % 12, sorted(ivs), minor=third == 3)


def voice_chord(chord: Chord, prev: list[int] | None, low: int, high: int,
                voices: int, rng: np.random.Generator) -> list[int]:
    """Place the chord's notes in [low, high] so they move as little as possible.

    Returns `voices` MIDI notes, ascending. Avoids minor seconds/ninths between
    any two voices and crowded intervals low down, where they get muddy.
    """
    pcs = chord.pcs
    if len(pcs) > voices:  # drop the fifth first, then the root (the drone has it)
        for drop in (7, 0):
            if len(pcs) > voices and drop in chord.intervals:
                pcs = [pc for pc in pcs if pc != (chord.root + drop) % 12]
    while len(pcs) < voices:  # double the root, then the next tones
        pcs = pcs + [pcs[(len(pcs) - len(chord.pcs)) % len(chord.pcs)]]
    options = [[m for m in range(low, high + 1) if m % 12 == pc] for pc in pcs]
    center = (low + high) / 2

    def ok(notes: list[int], strict: bool) -> bool:
        if len(set(notes)) < len(notes) or notes[-1] - notes[0] > 24:
            return False
        if any(b - a < (3 if a < 60 else 2) for a, b in zip(notes, notes[1:])):
            return False
        if strict and any((b - a) % 12 == 1 for a, b in itertools.combinations(notes, 2)):
            return False
        return True

    for strict in (True, False):
        best, best_cost = None, np.inf
        for combo in itertools.product(*options):
            notes = sorted(combo)
            if not ok(notes, strict):
                continue
            cost = 0.4 * abs(float(np.mean(notes)) - center) + rng.uniform(0.0, 0.5)
            if prev:
                cost += sum(abs(a - b) for a, b in zip(notes, prev))
            if cost < best_cost:
                best, best_cost = notes, cost
        if best:
            return best
    # Fallback: stack the chord tones upward from the middle of the range.
    start = int(center) - 6
    return sorted(start + (pc - start) % 12 for pc in pcs[:voices])
