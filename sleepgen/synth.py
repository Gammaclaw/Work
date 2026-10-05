"""Instruments: slowly shimmering additive pads and soft mallet / felt-piano notes.

Plain numpy, no plugins or GPU, so the same code (and the same audio for a given
seed) runs on a Mac or a Windows PC.
"""
from __future__ import annotations

import numpy as np

HOP = 256  # audio samples per control-rate point (envelopes, LFOs, brightness)


def midi_to_hz(m: float) -> float:
    return 440.0 * 2.0 ** ((m - 69.0) / 12.0)


def pan_gains(pos: float) -> tuple[float, float]:
    """Equal-power pan; pos runs from -1 (left) to 1 (right)."""
    angle = (float(np.clip(pos, -1.0, 1.0)) + 1.0) * np.pi / 4.0
    return float(np.cos(angle)), float(np.sin(angle))


_RAMP = (np.arange(HOP) / HOP).astype(np.float32)
_TWO_PI = np.float32(2 * np.pi)


def upsample(ctrl: np.ndarray, n: int) -> np.ndarray:
    """Linearly interpolate a control-rate signal (one point per HOP samples) to n float32 samples."""
    need = n // HOP + 2
    ctrl = np.asarray(ctrl, dtype=np.float32)
    if len(ctrl) < need:
        ctrl = np.concatenate([ctrl, np.full(need - len(ctrl), ctrl[-1], dtype=np.float32)])
    a, b = ctrl[: need - 1, None], ctrl[1:need, None]
    return (a + (b - a) * _RAMP).ravel()[:n]


def slow_wander(points: int, rng: np.random.Generator, sr: int, period=(20.0, 60.0)) -> np.ndarray:
    """Smooth random movement in [-1, 1] at control rate (three slow sines summed)."""
    t = np.arange(points) * HOP / sr
    out = np.zeros(points)
    for _ in range(3):
        out += np.sin(2 * np.pi * t / rng.uniform(*period) + rng.uniform(0, 2 * np.pi))
    return out / 3.0


def swell(points: int, sr: int, attack: float, release_at: float, release: float) -> np.ndarray:
    """Control-rate envelope: equal-power rise over `attack`, then fall over `release` from `release_at`."""
    t = np.arange(points) * HOP / sr
    rise = np.sin(0.5 * np.pi * np.clip(t / max(attack, 1e-3), 0.0, 1.0))
    fall = np.cos(0.5 * np.pi * np.clip((t - release_at) / max(release, 1e-3), 0.0, 1.0))
    return np.minimum(rise, fall)


def pad_note(freq: float, n: int, sr: int, rng: np.random.Generator, *, env: np.ndarray,
             bright: np.ndarray, partials: int = 10, rolloff: float = 1.4, darkening: float = 1.6,
             unison: int = 3, detune_cents: float = 7.0, drift_cents: float = 3.0,
             shimmer: float = 0.35, width: float = 0.8, max_hz: float = 6000.0) -> np.ndarray:
    """One sustained pad note as an (n, 2) float32 array.

    `env` and `bright` are control-rate arrays. Brightness (0..1) decides how much
    of the upper harmonics comes through, so the pad opens and closes like a slow
    filter. Every harmonic also swells on its own slow LFO, which is what keeps a
    long held chord from sounding static.
    """
    points = len(env)
    tc = np.arange(points) * HOP / sr
    roll = rolloff + darkening * (1.0 - np.asarray(bright))
    k_max = int(max(1, min(partials, max_hz // freq)))
    spreads = np.linspace(-1.0, 1.0, unison) if unison > 1 else np.zeros(1)
    out = np.zeros((n, 2), dtype=np.float32)
    for spread in spreads:
        cents = spread * detune_cents + drift_cents * slow_wander(points, rng, sr)
        # Phase is tracked in whole cycles at float64 (long notes need the precision);
        # each harmonic then only needs its fractional cycle, which float32 handles fine.
        cycles = np.cumsum(freq / sr * 2.0 ** (upsample(cents, n).astype(np.float64) / 1200.0))
        voice = np.zeros(n, dtype=np.float32)
        for k in range(1, k_max + 1):
            lfo = 1.0 + shimmer * np.sin(2 * np.pi * rng.uniform(0.02, 0.12) * tc + rng.uniform(0, 2 * np.pi))
            frac = cycles * k
            frac -= np.floor(frac)
            wave = np.sin(frac.astype(np.float32) * _TWO_PI + np.float32(rng.uniform(0, 2 * np.pi)))
            wave *= upsample(env * np.power(float(k), -roll) * lfo, n)
            voice += wave
        left, right = pan_gains(spread * width)
        out[:, 0] += left * voice
        out[:, 1] += right * voice
    return out / len(spreads)


TIMBRES = {
    # Soft felt-hammer piano: nearly harmonic partials with a touch of string stiffness,
    # a quick initial drop and a long quiet tail.
    "felt_piano": dict(partials=10, rolloff=1.3, stiffness=0.0004, decay=5.0, decay_tilt=0.7,
                       drop=0.6, attack=0.012, strings=2, detune_cents=1.0, max_hz=5500.0),
    # Glassy celesta / music-box tone with stretched upper partials and a long ring.
    "glass": dict(ratios=[1.0, 2.0, 3.0, 4.16, 5.43, 6.79], amps=[1.0, 0.4, 0.2, 0.1, 0.07, 0.04],
                  decay=7.0, decay_tilt=1.0, drop=0.25, attack=0.004, strings=2, detune_cents=2.5,
                  max_hz=9000.0),
}


def mallet_note(freq: float, velocity: float, sr: int, rng: np.random.Generator,
                timbre: str = "felt_piano", pan: float = 0.0, max_seconds: float = 10.0) -> np.ndarray:
    """One struck note (felt piano, glass, ...) as an (n, 2) float32 array."""
    if timbre not in TIMBRES:
        raise ValueError(f"unknown instrument {timbre!r}; use one of {sorted(TIMBRES)}")
    p = TIMBRES[timbre]
    decay = p["decay"] * (262.0 / freq) ** 0.35  # higher notes ring shorter
    n = int(min(max_seconds, 4.0 * decay) * sr)
    if "ratios" in p:
        ratios, amps = np.array(p["ratios"]), np.array(p["amps"], dtype=float)
    else:
        k = np.arange(1, p["partials"] + 1)
        ratios, amps = k * np.sqrt(1 + p["stiffness"] * k**2), k ** -p["rolloff"]
    amps = amps * np.exp(-(ratios - 1) * (1 - velocity) * 0.5)  # soft touch = fewer overtones
    keep = freq * ratios < p["max_hz"]
    ratios, amps = ratios[keep], amps[keep]

    points = n // HOP + 2
    tc = np.arange(points) * HOP / sr
    t = np.arange(n) / sr
    sig = np.zeros(n)
    for j, (ratio, amp) in enumerate(zip(ratios, amps)):
        tau = decay / (1 + p["decay_tilt"] * j)
        env = upsample(p["drop"] * np.exp(-tc / (0.25 * tau)) + (1 - p["drop"]) * np.exp(-tc / tau), n)
        for s in range(p["strings"]):
            det = 2.0 ** ((s - (p["strings"] - 1) / 2) * p["detune_cents"] / 1200)
            sig += amp * env * np.sin(2 * np.pi * freq * det * ratio * t + rng.uniform(0, 2 * np.pi))
    sig /= amps.sum() * p["strings"]
    na = max(1, int(p["attack"] * sr))
    sig[:na] *= np.sin(0.5 * np.pi * np.arange(na) / na) ** 2
    nr = min(n, int(0.4 * sr))
    sig[-nr:] *= np.cos(0.5 * np.pi * np.arange(nr) / nr) ** 2
    sig *= velocity**1.4
    left, right = pan_gains(pan)
    return np.stack([left * sig, right * sig], axis=1).astype(np.float32)
