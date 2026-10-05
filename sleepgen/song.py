"""Turn a style file plus a seed into one finished, mastered song.

Same style + same seed + same engine version = the same song (notes, chords, mix) on any machine.
"""
from __future__ import annotations

import time
from pathlib import Path

import numpy as np
import yaml

from . import __version__
from .compose import chord_timeline, compose_arpeggio, compose_melody, intensity_arc
from .effects import echo, loudness, master, reverb, reverb_ir
from .synth import HOP, midi_to_hz, mallet_note, pad_note, swell
from .textures import TEXTURES
from .theory import Chord, parse_key, parse_mode, voice_chord

LAYER_REFERENCE_LUFS = -26.0  # where a layer with gain_db 0 sits before reverb and mastering


def load_style(path: str | Path) -> dict:
    with open(path, encoding="utf-8") as f:
        style = yaml.safe_load(f) or {}
    style.setdefault("name", Path(path).stem)
    style["_file"] = str(path)
    return style


def _pick(value, rng: np.random.Generator):
    """Style values may be a list of options; pick one per song."""
    return str(rng.choice(value)) if isinstance(value, list) else value


def _ctrl_slice(arc: np.ndarray, start: int, points: int) -> np.ndarray:
    part = arc[start:start + points]
    return np.concatenate([part, np.full(points - len(part), arc[-1])]) if len(part) < points else part


def _sustained_notes(chords: list[Chord], voicings: list[list[int]]) -> list[tuple[int, float, float]]:
    """Per pad voice, merge a pitch held across chord changes into one long note."""
    notes = []
    for v in range(len(voicings[0])):
        current, since = None, 0.0
        for chord, voicing in zip(chords, voicings):
            if voicing[v] != current:
                if current is not None:
                    notes.append((current, since, chord.start))
                current, since = voicing[v], chord.start
        notes.append((current, since, chords[-1].end))
    return notes


def render_pad(chords, arc, sr, n, rng, cfg) -> np.ndarray:
    low, high = cfg.get("range", [52, 79])
    voices = int(cfg.get("voices", 4))
    attack, release = float(cfg.get("attack", 7.0)), float(cfg.get("release", 9.0))
    brightness = float(cfg.get("brightness", 0.45))
    voicings, prev = [], None
    for chord in chords:
        prev = voice_chord(chord, prev, low, high, voices, rng)
        voicings.append(prev)
    bus = np.zeros((n, 2), dtype=np.float32)
    for midi, start, end in _sustained_notes(chords, voicings):
        s0 = int(start * sr)
        length = min(int((end - start + release) * sr), n - s0)
        if length <= 0:
            continue
        points = length // HOP + 2
        bright = np.clip(brightness * (0.55 + 0.9 * _ctrl_slice(arc, s0 // HOP, points)), 0.0, 1.0)
        bus[s0:s0 + length] += pad_note(
            midi_to_hz(midi), length, sr, rng,
            env=swell(points, sr, attack, end - start, release), bright=bright,
            partials=int(cfg.get("partials", 10)), unison=int(cfg.get("unison", 3)),
            detune_cents=float(cfg.get("detune_cents", 7.0)), shimmer=float(cfg.get("shimmer", 0.35)),
            width=float(cfg.get("width", 0.8)),
        )
    return bus


def render_drone(chords, tonic, sr, n, rng, cfg) -> np.ndarray:
    base = 12 * (int(cfg.get("octave", 2)) + 1)
    attack, release = float(cfg.get("attack", 10.0)), float(cfg.get("release", 10.0))
    if cfg.get("follow", "root") == "tonic":
        events = [(tonic, 0.0, chords[-1].end)]
    else:
        events = []
        for chord in chords:
            if events and events[-1][0] == chord.root:
                events[-1] = (chord.root, events[-1][1], chord.end)
            else:
                events.append((chord.root, chord.start, chord.end))
    bus = np.zeros((n, 2), dtype=np.float32)
    for pc, start, end in events:
        midi = base + pc - (12 if pc > 6 else 0)  # keep the drone in one low register
        s0 = int(start * sr)
        length = min(int((end - start + release) * sr), n - s0)
        if length <= 0:
            continue
        points = length // HOP + 2
        bus[s0:s0 + length] += pad_note(
            midi_to_hz(midi), length, sr, rng,
            env=swell(points, sr, attack, end - start, release), bright=np.full(points, 0.5),
            # A single voice: detuned pairs this low beat audibly ("wub... wub...").
            partials=4, rolloff=1.8, darkening=0.8, unison=1, drift_cents=1.5,
            shimmer=0.15, max_hz=1000.0,
        )
    return bus


def render_notes(notes, sr, n, rng, cfg) -> np.ndarray:
    """Play struck notes (melody or arpeggio) on one instrument, then add its echo."""
    instrument = cfg.get("instrument", "felt_piano")
    bus = np.zeros((n, 2), dtype=np.float32)
    for note in notes:
        s0 = int(note.time * sr)
        if s0 >= n:
            continue
        pan = float(np.clip((note.midi - 64) / 24 * 0.6 + rng.uniform(-0.1, 0.1), -0.8, 0.8))
        sig = mallet_note(midi_to_hz(note.midi), note.velocity, sr, rng, instrument, pan)
        length = min(len(sig), n - s0)
        bus[s0:s0 + length] += sig[:length]
    if cfg.get("echo"):
        e = cfg["echo"]
        bus = echo(bus, sr, float(e.get("seconds", 0.8)), float(e.get("feedback", 0.35)),
                   float(e.get("mix", 0.25)), float(e.get("damp_hz", 3000)))
    return bus


def render_song(style: dict, minutes: float, seed: int, log=print) -> tuple[np.ndarray, int, dict]:
    started = time.time()
    rng = np.random.default_rng(seed)
    sr = int(style.get("sample_rate", 48000))
    duration = float(minutes) * 60.0
    n = int(duration * sr)
    points = n // HOP + 2

    key = _pick(style.get("key", "C"), rng)
    mode = parse_mode(_pick(style.get("mode", "ionian"), rng))
    tonic = parse_key(key)
    arc = intensity_arc(duration, points, rng, style.get("arc", "arch"))

    def arc_at(t: float) -> float:
        return float(arc[min(int(t * sr / HOP), points - 1)])

    # A shared tempo locks chords, arpeggio and melody to one beat grid.
    chord_cfg, melody_cfg, arp_cfg = (dict(style.get(k) or {}) for k in ("chords", "melody", "arpeggio"))
    if style.get("tempo"):
        beat = 60.0 / float(style["tempo"])
        chord_cfg.setdefault("bar_seconds", 4 * beat)
        for cfg in (c for c in (melody_cfg, arp_cfg) if c):
            cfg.setdefault("tempo", style["tempo"])
            cfg.setdefault("quantize", True)
    chords = chord_timeline(tonic, mode, duration, rng, chord_cfg)
    log(f"{style['name']} | {key} {mode} | {minutes:g} min | seed {seed} | {len(chords)} chords")

    dry = np.zeros((n, 2), dtype=np.float32)
    send = np.zeros((n, 2), dtype=np.float32)

    def mix_in(name: str, bus: np.ndarray, cfg: dict, default_send: float) -> None:
        level = loudness(bus, sr)
        if not np.isfinite(level):
            return
        bus *= 10 ** ((LAYER_REFERENCE_LUFS + float(cfg.get("gain_db", 0.0)) - level) / 20)
        np.add(dry, bus * float(cfg.get("dry", 1.0)), out=dry)
        np.add(send, bus * float(cfg.get("reverb_send", default_send)), out=send)
        log(f"  {name:<8} rendered ({time.time() - started:5.1f}s)")

    if style.get("pad"):
        mix_in("pad", render_pad(chords, arc, sr, n, rng, style["pad"]), style["pad"], 0.5)
    if style.get("drone"):
        mix_in("drone", render_drone(chords, tonic, sr, n, rng, style["drone"]), style["drone"], 0.1)
    counts = {}
    if arp_cfg:
        notes = compose_arpeggio(chords, duration, arc_at, rng, arp_cfg)
        mix_in("arpeggio", render_notes(notes, sr, n, rng, arp_cfg), arp_cfg, 0.5)
        counts["arpeggio"] = len(notes)
    if melody_cfg:
        notes = compose_melody(chords, tonic, mode, duration, arc_at, rng, melody_cfg)
        mix_in("melody", render_notes(notes, sr, n, rng, melody_cfg), melody_cfg, 0.8)
        counts["melody"] = len(notes)
    texture = style.get("texture") or {}
    if texture.get("type", "none") != "none":
        mix_in("texture", TEXTURES[texture["type"]](n, sr, rng, texture), texture, 0.0)

    rv = style.get("reverb", {})
    ir = reverb_ir(sr, float(rv.get("seconds", 6.0)), float(rv.get("damping", 0.5)), rng,
                   float(rv.get("predelay", 0.025)))
    dry += reverb(send, ir) * 10 ** (float(rv.get("wet_db", -3.0)) / 20)
    del send
    log(f"  reverb   done     ({time.time() - started:5.1f}s)")
    audio = master(dry, sr, style.get("master", {}), log=log)

    info = {
        "style": style["name"],
        "style_file": style.get("_file"),
        "seed": seed,
        "minutes": minutes,
        "sample_rate": sr,
        "key": key,
        "mode": mode,
        "chords": [{"name": c.name, "roman": c.roman, "start": round(c.start, 1), "end": round(c.end, 1)}
                   for c in chords],
        "note_counts": counts,
        "engine_version": __version__,
        "render_seconds": round(time.time() - started, 1),
    }
    return audio, sr, info
