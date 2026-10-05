"""Command line: python -m sleepgen render styles/warm_drift.yaml --minutes 15 --mp3"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

import numpy as np
import soundfile as sf

from .analyze import analyze
from .song import load_style, render_song


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def to_mp3(wav: Path, bitrate: str = "192k") -> Path | None:
    if not shutil.which("ffmpeg"):
        print("  (ffmpeg not found, skipping MP3)")
        return None
    mp3 = wav.with_suffix(".mp3")
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(wav), "-c:a", "libmp3lame",
                    "-b:a", bitrate, str(mp3)], check=True)
    return mp3


def cmd_render(args: argparse.Namespace) -> None:
    style = load_style(args.style)
    seed = args.seed if args.seed is not None else int(np.random.default_rng().integers(1, 1_000_000))
    audio, sr, info = render_song(style, args.minutes, seed)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    stem = f"{_slug(style['name'])}_{seed}_{args.minutes:g}m"
    wav = out / f"{stem}.wav"
    sf.write(str(wav), audio, sr, subtype="PCM_24")
    info["files"] = {"wav": str(wav)}
    if args.mp3 and (mp3 := to_mp3(wav)):
        info["files"]["mp3"] = str(mp3)
    if args.report:
        info["analysis"] = analyze(wav, png=out / f"{stem}.png")
        info["files"]["report"] = str(out / f"{stem}.png")
    (out / f"{stem}.json").write_text(json.dumps(info, indent=2))
    print(f"done in {info['render_seconds']}s -> {wav}")


def cmd_analyze(args: argparse.Namespace) -> None:
    print(json.dumps(analyze(args.file, png=args.png), indent=2))


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="sleepgen", description="Local generator for long-form sleep / calm music.")
    sub = parser.add_subparsers(dest="command", required=True)

    r = sub.add_parser("render", help="render one song from a style file")
    r.add_argument("style", help="path to a style .yaml file")
    r.add_argument("--minutes", type=float, default=15.0, help="song length (default 15)")
    r.add_argument("--seed", type=int, help="random seed; the same seed always gives the same song")
    r.add_argument("--out", default="output/songs", help="output folder (default output/songs)")
    r.add_argument("--mp3", action="store_true", help="also write an MP3 for easy listening")
    r.add_argument("--report", action="store_true", help="also write a loudness/spectrogram PNG")
    r.set_defaults(func=cmd_render)

    a = sub.add_parser("analyze", help="loudness and spectrogram report for an audio file")
    a.add_argument("file")
    a.add_argument("--png", help="save a spectrogram picture here")
    a.set_defaults(func=cmd_analyze)

    args = parser.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    sys.exit(main())
