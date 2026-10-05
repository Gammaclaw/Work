"""Filters, echo, reverb, fades and loudness."""
from __future__ import annotations

import numpy as np
import pyloudnorm
from scipy import signal


def _filter(x: np.ndarray, kind: str, hz, sr: int, order: int) -> np.ndarray:
    sos = signal.butter(order, hz, kind, fs=sr, output="sos")
    return signal.sosfilt(sos, x, axis=0).astype(np.float32)


def lowpass(x: np.ndarray, hz: float, sr: int, order: int = 2) -> np.ndarray:
    return _filter(x, "lowpass", hz, sr, order)


def highpass(x: np.ndarray, hz: float, sr: int, order: int = 2) -> np.ndarray:
    return _filter(x, "highpass", hz, sr, order)


def bandpass(x: np.ndarray, lo: float, hi: float, sr: int, order: int = 2) -> np.ndarray:
    return _filter(x, "bandpass", [lo, hi], sr, order)


def rms(x: np.ndarray) -> float:
    return float(np.sqrt(np.mean(np.square(x, dtype=np.float64)))) + 1e-12


def loudness(x: np.ndarray, sr: int) -> float:
    """Integrated loudness in LUFS (gated, so silent stretches don't drag it down)."""
    return float(pyloudnorm.Meter(sr).integrated_loudness(x))


def fade(x: np.ndarray, sr: int, fade_in: float, fade_out: float) -> np.ndarray:
    ni, no = min(len(x), int(fade_in * sr)), min(len(x), int(fade_out * sr))
    if ni:
        x[:ni] *= (np.sin(0.5 * np.pi * np.linspace(0, 1, ni)) ** 2)[:, None]
    if no:
        x[-no:] *= (np.cos(0.5 * np.pi * np.linspace(0, 1, no)) ** 2)[:, None]
    return x


def echo(x: np.ndarray, sr: int, seconds: float, feedback: float, mix: float,
         damp_hz: float = 3000.0) -> np.ndarray:
    """Ping-pong echo: repeats alternate left/right and get darker each time."""
    d = max(1, int(seconds * sr))
    n = len(x)
    mono = x.mean(axis=1)
    wet = np.zeros((n, 2))
    b, a = signal.butter(1, damp_hz, fs=sr)
    zi = np.zeros((1, 2))
    for start in range(d, n, d):  # each block only depends on the block before it
        end = min(start + d, n)
        src = np.empty((end - start, 2))
        src[:, 0] = mono[start - d:end - d] + feedback * wet[start - d:end - d, 1]
        src[:, 1] = feedback * wet[start - d:end - d, 0]
        wet[start:end], zi = signal.lfilter(b, a, src, axis=0, zi=zi)
    return (x + mix * wet).astype(np.float32)


def reverb_ir(sr: int, seconds: float, damping: float, rng: np.random.Generator,
              predelay: float = 0.025) -> np.ndarray:
    """A synthetic hall: decaying stereo noise where the highs die away sooner (damping 0..1)."""
    n = int(sr * seconds * 1.2)
    t = np.arange(n) / sr
    noise = rng.standard_normal((n, 2))
    spec = np.fft.rfft(noise, axis=0)
    freqs = np.fft.rfftfreq(n, 1 / sr)
    edges = [0, 400, 1500, 4000, 8000, sr]
    ir = np.zeros((n, 2))
    for i in range(len(edges) - 1):
        band = np.fft.irfft(spec * ((freqs >= edges[i]) & (freqs < edges[i + 1]))[:, None], n=n, axis=0)
        rt60 = max(0.3, seconds * (1.0 - damping * i / (len(edges) - 2)))
        ir += band * np.exp(-6.91 * t / rt60)[:, None]
    onset = int(0.04 * sr)  # soften the very start so nothing "clicks" into the hall
    ir[:onset] *= (np.sin(0.5 * np.pi * np.arange(onset) / onset) ** 2)[:, None]
    ir = np.vstack([np.zeros((int(predelay * sr), 2)), ir])
    ir /= np.sqrt(np.sum(ir**2, axis=0, keepdims=True))
    return ir.astype(np.float32)


def reverb(x: np.ndarray, ir: np.ndarray) -> np.ndarray:
    out = np.empty_like(x)
    for ch in range(2):
        out[:, ch] = signal.oaconvolve(x[:, ch], ir[:, ch])[: len(x)]
    return out


def master(x: np.ndarray, sr: int, cfg: dict, log=print) -> np.ndarray:
    """Clean up the lows, soften the highs, fade, and set the final loudness."""
    x = highpass(x, float(cfg.get("highpass_hz", 30)), sr)
    if cfg.get("lowpass_hz"):
        x = lowpass(x, float(cfg["lowpass_hz"]), sr)
    x = fade(x, sr, float(cfg.get("fade_in", 10)), float(cfg.get("fade_out", 20)))
    target = float(cfg.get("lufs", -18))
    gain = 10 ** ((target - loudness(x, sr)) / 20)
    peak_limit = 10 ** (float(cfg.get("peak_db", -1.0)) / 20)
    peak = float(np.max(np.abs(x))) * gain
    if peak > peak_limit:
        log(f"  note: peaks would hit {20 * np.log10(peak):.1f} dBFS at {target} LUFS; turning down to stay clean")
        gain *= peak_limit / peak
    return (x * gain).astype(np.float32)
