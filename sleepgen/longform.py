"""Long-form assembly: join songs into one 1-3 hour mix, then put the mix on a looping visual.

Both steps stream through FFmpeg, so a 3-hour mix never has to fit in memory.
"""
from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

VIDEO_EXTS = {".mp4", ".mov", ".mkv", ".webm"}


def _need(tool: str) -> str:
    path = shutil.which(tool)
    if not path:
        raise SystemExit(f"{tool} not found; install FFmpeg (Windows: winget install Gyan.FFmpeg, Mac: brew install ffmpeg)")
    return path


def duration(path: Path) -> float:
    out = subprocess.run([_need("ffprobe"), "-v", "error", "-show_entries", "format=duration",
                          "-of", "default=nw=1:nk=1", str(path)], capture_output=True, text=True, check=True)
    return float(out.stdout.strip())


def track_title(path: Path) -> str:
    """The song's style name from its render JSON, else a tidy version of the file name."""
    meta = path.with_suffix(".json")
    if meta.exists():
        try:
            return json.loads(meta.read_text())["style"]
        except (KeyError, ValueError):
            pass
    return path.stem.split("_")[0].replace("-", " ").title()


def timestamp(seconds: float) -> str:
    s = int(round(seconds))
    return f"{s // 3600}:{s // 60 % 60:02d}:{s % 60:02d}" if s >= 3600 else f"{s // 60}:{s % 60:02d}"


def stitch(songs: list[Path], out: Path, crossfade: float = 15.0, bitrate: str = "256k", log=print) -> list[dict]:
    """Crossfade the songs in order into one AAC file; returns the tracklist with start times."""
    if not songs:
        raise SystemExit("no songs given")
    lengths = [duration(p) for p in songs]
    if any(length <= 2 * crossfade for length in lengths):
        raise SystemExit(f"every song must be longer than {2 * crossfade:g} s for a {crossfade:g} s crossfade")
    tracks, start = [], 0.0
    for path, length in zip(songs, lengths):
        tracks.append({"start": round(start, 2), "title": track_title(path), "file": path.name})
        start += length - crossfade
    total = start + crossfade

    cmd = [_need("ffmpeg"), "-y", "-loglevel", "error", "-stats"]
    for p in songs:
        cmd += ["-i", str(p)]
    if len(songs) == 1:
        graph, last = "[0:a]anull[out]", "[out]"
    else:
        steps, prev = [], "[0:a]"
        for i in range(1, len(songs)):
            label = f"[x{i}]"
            steps.append(f"{prev}[{i}:a]acrossfade=d={crossfade}:c1=qsin:c2=qsin{label}")
            prev = label
        graph, last = ";".join(steps), prev
    out.parent.mkdir(parents=True, exist_ok=True)
    cmd += ["-filter_complex", graph, "-map", last, "-c:a", "aac", "-b:a", bitrate, "-ar", "48000", str(out)]
    log(f"stitching {len(songs)} songs, {timestamp(total)} total, {crossfade:g} s crossfades")
    subprocess.run(cmd, check=True)

    lines = [f"{timestamp(t['start'])} {t['title']}" for t in tracks]
    out.with_suffix(".tracklist.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
    out.with_suffix(".json").write_text(json.dumps(
        {"seconds": round(total, 1), "crossfade": crossfade, "tracks": tracks}, indent=2))
    return tracks


def make_video(audio: Path, visual: Path, out: Path, height: int = 1080, log=print) -> None:
    """Loop a picture or a short clip under the audio for its full length (1080p H.264 + AAC)."""
    scale = f"scale=-2:{height}:flags=lanczos,format=yuv420p"
    cmd = [_need("ffmpeg"), "-y", "-loglevel", "error", "-stats"]
    if visual.suffix.lower() in VIDEO_EXTS:
        # A clip: loop it endlessly; a seamless loop is the clip's job.
        cmd += ["-stream_loop", "-1", "-i", str(visual), "-i", str(audio),
                "-vf", scale, "-r", "30", "-c:v", "libx264", "-preset", "medium", "-crf", "20"]
    else:
        # A still picture: 1 frame per second keeps a 3-hour file small and quick to encode.
        cmd += ["-loop", "1", "-framerate", "1", "-i", str(visual), "-i", str(audio),
                "-vf", scale, "-r", "1", "-c:v", "libx264", "-preset", "medium", "-tune", "stillimage", "-crf", "18"]
    out.parent.mkdir(parents=True, exist_ok=True)
    cmd += ["-map", "0:v", "-map", "1:a", "-c:a", "copy", "-shortest", "-movflags", "+faststart", str(out)]
    log(f"rendering video {out.name} ({timestamp(duration(audio))})")
    subprocess.run(cmd, check=True)
