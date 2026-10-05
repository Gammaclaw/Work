"""Objective checks on a render: loudness, peaks, and a spectrogram picture.

Claude can't hear audio, so this is how it "looks" at a render: harsh highs,
boomy lows, sudden jumps in level or dead silent gaps all show up here.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import soundfile as sf
from scipy import signal

from .effects import loudness


def analyze(path: str | Path, png: str | Path | None = None) -> dict:
    x, sr = sf.read(str(path), dtype="float32", always_2d=True)
    mono = x.mean(axis=1)
    win = 5 * sr
    blocks = max(1, len(mono) // win)
    block_db = 20 * np.log10(np.sqrt(np.mean(mono[: blocks * win].reshape(blocks, -1) ** 2, axis=1)) + 1e-9)
    body = block_db[(block_db > block_db.max() - 40)]
    report = {
        "file": str(path),
        "minutes": round(len(x) / sr / 60, 2),
        "lufs": round(loudness(x, sr), 1),
        "peak_dbfs": round(float(20 * np.log10(np.max(np.abs(x)) + 1e-9)), 1),
        "level_swing_db": round(float(np.percentile(body, 95) - np.percentile(body, 10)), 1),
        "stereo_correlation": round(float(np.corrcoef(x[:, 0], x[:, 1])[0, 1]), 2),
    }
    if png:
        _plot(mono, sr, block_db, report, png)
    return report


def _plot(mono: np.ndarray, sr: int, block_db: np.ndarray, report: dict, png: str | Path) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    f, t, spec = signal.spectrogram(mono, fs=sr, nperseg=8192, noverlap=0)
    spec_db = 10 * np.log10(spec + 1e-12)
    rows = np.geomspace(30, min(14000, sr / 2 - 1), 240)  # log-frequency view
    spec_db = spec_db[np.searchsorted(f, rows)]
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 6.5), height_ratios=[3, 1], sharex=True)
    top = np.percentile(spec_db, 99.5)
    ax1.imshow(spec_db, aspect="auto", origin="lower", cmap="magma", vmin=top - 70, vmax=top,
               extent=[0, t[-1] / 60, 0, len(rows)])
    ticks = [50, 100, 200, 500, 1000, 2000, 5000, 10000]
    ax1.set_yticks([np.searchsorted(rows, v) for v in ticks if v < rows[-1]])
    ax1.set_yticklabels([f"{v // 1000}k" if v >= 1000 else str(v) for v in ticks if v < rows[-1]])
    ax1.set_ylabel("Hz")
    ax1.set_title(f"{Path(report['file']).name}   {report['lufs']} LUFS   peak {report['peak_dbfs']} dBFS")
    ax2.plot((np.arange(len(block_db)) + 0.5) * 5 / 60, block_db, color="#c65")
    ax2.set_ylabel("level dB")
    ax2.set_xlabel("minutes")
    ax2.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(png, dpi=90)
    plt.close(fig)
