"""Real B rules and dynamic loading of A-07, with no enhancement test double."""

from copy import deepcopy
import json

import numpy as np
import pytest

from src.adaptive import adaptive_enhance, enhance_frames, measure_quality, select_params
from src.dip import apply_ops, gamma, gaussian, hist_eq, median, unsharp
from src.io import load_frame, save_frame


@pytest.fixture
def frame():
    return np.random.default_rng(44).integers(20, 150, (31, 43, 3), dtype=np.uint8)


@pytest.mark.parametrize("updates,rule,operation", [
    ({"brightness": 30}, "BR_DARK", lambda f: gamma(f, 0.5)),
    ({"brightness": 70}, "BR_DIM", lambda f: gamma(f, 0.75)),
    ({"brightness": 210}, "BR_BRIGHT", lambda f: gamma(f, 1.3)),
    ({"contrast": 20}, "CT_LOW", hist_eq),
    ({"noise": 10}, "NS_MEDIUM", lambda f: gaussian(f, 3, 1.0)),
    ({"noise": 20}, "NS_HIGH", lambda f: median(f, 5)),
    ({"sharpness": 20}, "SH_LOW", lambda f: unsharp(f, 0.8, 1.0, 5.0)),
])
def test_each_real_b_rule_is_accepted(frame, updates, rule, operation):
    quality = dict(brightness=120, contrast=50, noise=0, sharpness=200)
    params = select_params({**quality, **updates})
    assert params["rules"] == [rule]
    before = deepcopy(params)
    serialized = json.loads(json.dumps(params, allow_nan=False))
    np.testing.assert_array_equal(apply_ops(frame, serialized), operation(frame))
    assert params == before


def test_b_combined_rules_follow_spec_order(frame):
    params = select_params(dict(brightness=30, contrast=20, noise=0, sharpness=20))
    assert params["rules"] == ["BR_DARK", "CT_LOW", "SH_LOW"]
    expected = unsharp(hist_eq(gamma(frame, 0.5)), 0.8, 1.0, 5)
    np.testing.assert_array_equal(apply_ops(frame, params), expected)
    # Guard against accidentally adopting B's former histogram-before-gamma proposal.
    reversed_order = unsharp(gamma(hist_eq(frame), 0.5), 0.8, 1.0, 5)
    assert not np.array_equal(expected, reversed_order)


def test_adaptive_enhance_loads_production_runner(frame):
    before = frame.copy()
    out, params, quality = adaptive_enhance(frame)
    assert quality == measure_quality(frame)
    assert params == select_params(quality)
    np.testing.assert_array_equal(out, apply_ops(frame, params))
    np.testing.assert_array_equal(frame, before)
    assert out.shape == frame.shape and out.dtype == np.uint8


def test_adaptive_png_batch_and_json_log_with_real_runner(tmp_path, monkeypatch):
    source, target = tmp_path / "orig", tmp_path / "adaptive"
    images = {
        "night_0.png": np.full((19, 23, 3), 30, np.uint8),
        "night_100.png": np.random.default_rng(45).integers(0, 256, (19, 23, 3), dtype=np.uint8),
    }
    for name, img in images.items():
        save_frame(source / name, img)
    monkeypatch.chdir(tmp_path)
    log_path = tmp_path / "adaptive.json"
    records = enhance_frames(source, target, log_path)
    assert set(records) == set(images) == {p.name for p in target.glob("*.png")}
    assert json.loads(log_path.read_text(encoding="utf-8")) == records
    for name, original in images.items():
        record = records[name]
        assert record["rules"] == record["params"]["rules"]
        assert record["enhance_ms"] >= 0
        np.testing.assert_array_equal(load_frame(target / name), apply_ops(original, record["params"]))
        np.testing.assert_array_equal(load_frame(source / name), original)
