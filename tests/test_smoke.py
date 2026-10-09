"""Quick end-to-end check: every style renders clean, at the right loudness, repeatably."""
from pathlib import Path

import numpy as np
import pytest

from sleepgen.effects import loudness
from sleepgen.song import load_style, render_song

STYLES = sorted(Path(__file__).resolve().parent.parent.joinpath("styles").glob("*.yaml"))


@pytest.mark.parametrize("path", STYLES, ids=lambda p: p.stem)
def test_style_renders_clean(path):
    style = load_style(path)
    audio, sr, info = render_song(style, minutes=0.75, seed=7, log=lambda *_: None)
    assert audio.shape == (int(0.75 * 60 * sr), 2)
    assert np.isfinite(audio).all()
    assert np.max(np.abs(audio)) < 1.0
    assert abs(loudness(audio, sr) - style.get("master", {}).get("lufs", -18)) < 1.5
    assert info["chords"] and info["chords"][-1]["roman"].upper() == "I"  # ends at home


def test_same_seed_same_song():
    style = load_style(STYLES[0])
    a, _, _ = render_song(style, minutes=0.5, seed=3, log=lambda *_: None)
    b, _, _ = render_song(style, minutes=0.5, seed=3, log=lambda *_: None)
    assert np.array_equal(a, b)


def test_set_overrides_nested_values():
    from sleepgen.__main__ import apply_overrides

    style = {"drone": {"gain_db": -8}}
    apply_overrides(style, ["drone.gain_db=-20", "texture.type=none", "key=[A, C]"])
    assert style == {"drone": {"gain_db": -20}, "texture": {"type": "none"}, "key": ["A", "C"]}


STYLE_DIR = Path(__file__).resolve().parent.parent / "styles"


def test_take_inherits_its_base_style():
    take = load_style(STYLE_DIR / "ocean_night_whales.yaml")
    base = load_style(STYLE_DIR / "ocean_night.yaml")
    assert take["name"] != base["name"]
    assert take["texture"] == base["texture"] and take["drone"] == base["drone"]
    assert "whales" in take and "whales" not in base


def test_adding_a_part_leaves_the_rest_untouched():
    # Every part has its own random stream: a near-silent extra part must not change anything else.
    base = load_style(STYLE_DIR / "ocean_night.yaml")
    take = load_style(STYLE_DIR / "ocean_night_whales.yaml")
    take["whales"]["gain_db"] = -120
    a, _, info_a = render_song(base, minutes=0.5, seed=3, log=lambda *_: None)
    b, _, info_b = render_song(take, minutes=0.5, seed=3, log=lambda *_: None)
    assert info_a["chords"] == info_b["chords"]
    assert np.max(np.abs(a - b)) < 1e-4
