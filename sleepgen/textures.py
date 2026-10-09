"""Background beds that sit under the music: brown noise, ocean waves, soft rain."""
from __future__ import annotations

import numpy as np
from scipy import signal

from .effects import bandpass, highpass, lowpass, rms
from .synth import HOP, midi_to_hz, pan_gains, slow_wander, upsample


def brown(n: int, sr: int, rng: np.random.Generator, cfg: dict) -> np.ndarray:
    """Deep, soft rumble (white noise with the highs rolled off steeply)."""
    white = rng.standard_normal((n, 2), dtype=np.float32)
    x = highpass(signal.lfilter([1.0], [1.0, -0.997], white, axis=0), 30, sr)
    return x / rms(x)


def ocean(n: int, sr: int, rng: np.random.Generator, cfg: dict) -> np.ndarray:
    """Waves that swell in over a few seconds and wash out, each from a slightly different side."""
    points = n // HOP + 2
    rate = sr / HOP
    env = np.zeros((points, 2))
    t = rng.uniform(0.0, 4.0)
    while t < n / sr:
        rise, fall = rng.uniform(2.5, 5.0), rng.uniform(5.0, 9.0)
        shape = np.concatenate([
            np.sin(0.5 * np.pi * np.linspace(0, 1, int(rise * rate))) ** 2,
            np.exp(-3.5 * np.linspace(0, 1, int(fall * rate))),
        ])
        i0 = int(t * rate)
        seg = shape[: max(0, points - i0)]
        env[i0:i0 + len(seg)] += rng.uniform(0.55, 1.0) * np.outer(seg, pan_gains(rng.uniform(-0.6, 0.6)))
        t += rise + fall * rng.uniform(0.45, 0.8)
    env /= env.max()

    white = rng.standard_normal((n, 2), dtype=np.float32)
    red = signal.lfilter([0.05], [1.0, -0.95], white, axis=0)
    dark, bright = lowpass(red, 420, sr), bandpass(red, 500, 3500, sr)
    dark /= rms(dark)
    bright /= rms(bright)
    out = np.empty((n, 2), dtype=np.float32)
    for ch in range(2):
        e = upsample(env[:, ch], n)
        out[:, ch] = (0.12 + e**1.5) * dark[:, ch] + 0.45 * e**2.5 * bright[:, ch]
    return out / rms(out)


def rain(n: int, sr: int, rng: np.random.Generator, cfg: dict) -> np.ndarray:
    """Steady soft rain: a hiss of distant drops plus gentle closer patter."""
    white = rng.standard_normal((n, 2), dtype=np.float32)
    bed = bandpass(white, 700, 5500, sr)
    bed *= upsample(0.8 + 0.2 * slow_wander(n // HOP + 2, rng, sr, period=(15.0, 40.0)), n)[:, None]
    bed /= rms(bed)

    kernels = []
    for _ in range(8):
        kt = np.arange(int(0.03 * sr)) / sr
        k = np.sin(2 * np.pi * rng.uniform(1800, 4500) * kt) * np.exp(-kt / rng.uniform(0.002, 0.006))
        ramp = int(0.0005 * sr)
        k[:ramp] *= np.linspace(0, 1, ramp)
        kernels.append(k.astype(np.float32))
    drops = np.zeros((n, 2), dtype=np.float32)
    count = int(rng.poisson(n / sr * (30 + 90 * float(cfg.get("density", 0.5)))))
    positions = rng.integers(0, max(1, n - len(kernels[0])), count)
    for pos, amp, k, pan in zip(positions, rng.exponential(1.0, count), rng.integers(0, 8, count),
                                rng.uniform(-0.8, 0.8, count)):
        kernel = kernels[k]
        left, right = pan_gains(pan)
        drops[pos:pos + len(kernel), 0] += amp * left * kernel
        drops[pos:pos + len(kernel), 1] += amp * right * kernel
    drops = lowpass(drops, 6000, sr)
    return bed + 0.3 * drops / rms(drops)


def whale_call(f_start: float, f_end: float, seconds: float, sr: int, rng: np.random.Generator) -> np.ndarray:
    """One moan: glides from f_start to f_end with a rise-and-fall arch, opening up in the middle."""
    n = int(seconds * sr)
    x = np.linspace(0.0, 1.0, n)
    arch = np.sin(np.pi * x)
    semis = (12 * np.log2(f_end / f_start) * (3 * x**2 - 2 * x**3)  # smooth glide between notes
             + rng.uniform(1.0, 4.0) * arch**2  # the moan bends up and back down
             + 0.15 * arch * np.sin(2 * np.pi * rng.uniform(2.0, 4.0) * x * seconds + rng.uniform(0, 2 * np.pi)))
    phase = 2 * np.pi * np.cumsum(f_start * 2.0 ** (semis / 12)) / sr
    opening = 0.35 + 0.65 * arch**1.5
    sig = np.zeros(n)
    for k in range(1, 7):
        if f_start * k > 3000:
            break
        sig += k**-1.4 * opening ** (k - 1) * np.sin(k * phase + rng.uniform(0, 2 * np.pi))
    sig += 0.06 * opening * lowpass(rng.standard_normal(n), 1200, sr)  # breath
    if rng.random() < 0.3:  # some calls get a soft growl
        sig *= 1.0 - 0.1 * (1 + np.sin(2 * np.pi * rng.uniform(25, 35) * x * seconds))
    na, nr = int(min(0.8, 0.25 * seconds) * sr), int(min(1.5, 0.4 * seconds) * sr)
    sig[:na] *= np.sin(0.5 * np.pi * np.arange(na) / na) ** 2
    sig[-nr:] *= np.cos(0.5 * np.pi * np.arange(nr) / nr) ** 2
    return (sig / np.max(np.abs(sig)) * rng.uniform(0.6, 1.0)).astype(np.float32)


def whale_song(n: int, sr: int, rng: np.random.Generator, cfg: dict, pitches: list[int]) -> np.ndarray:
    """Distant whales: phrases of one to three calls, each starting and ending on a note of the key."""
    duration = n / sr
    gap_lo, gap_hi = cfg.get("gap_seconds", [25, 60])
    out = np.zeros((n, 2), dtype=np.float32)
    t = min(float(cfg.get("first_call", 20.0)), duration * 0.15)
    while t < duration - 12.0:
        pan = rng.uniform(-0.7, 0.7)
        note = int(rng.integers(0, len(pitches)))
        for _ in range(int(rng.integers(1, 4))):
            seconds = rng.uniform(2.5, 5.5)
            if t + seconds > duration - 12.0:
                break
            nxt = int(np.clip(note + rng.choice([-2, -1, 1, 2]), 0, len(pitches) - 1))
            call = whale_call(midi_to_hz(pitches[note]), midi_to_hz(pitches[nxt]), seconds, sr, rng)
            s0 = int(t * sr)
            length = min(len(call), n - s0)
            left, right = pan_gains(pan + rng.uniform(-0.1, 0.1))
            out[s0:s0 + length, 0] += left * call[:length]
            out[s0:s0 + length, 1] += right * call[:length]
            note = nxt
            t += seconds + rng.uniform(0.6, 2.5)
        t += rng.uniform(gap_lo, gap_hi)
    return lowpass(out, float(cfg.get("lowpass_hz", 1800)), sr)  # far away, under water


TEXTURES = {"brown": brown, "ocean": ocean, "rain": rain}
