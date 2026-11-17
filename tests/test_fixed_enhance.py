"""A-08 fixed configuration, reproducibility and mutation isolation."""

import json

import numpy as np
import pytest

from src.dip import FIXED_PARAMS, apply_ops, fixed_enhance, gamma, gaussian, unsharp
import src.dip.fixed as fixed


def test_baseline_matches_documented_initial_configuration():
    assert dict(FIXED_PARAMS) == {
        "denoise": "gaussian", "ksize": 3, "sigma": 1.0, "gamma": 0.75,
        "hist_eq": False, "unsharp": 0.8, "unsharp_sigma": 1.0,
        "unsharp_threshold": 5.0,
    }


def test_same_params_for_different_frames():
    images = [np.full((11, 13, 3), value, np.uint8) for value in (0, 30, 120, 255)]
    images.append(np.random.default_rng(46).integers(0, 256, (17, 19, 3), dtype=np.uint8))
    configs = []
    for img in images:
        out, params = fixed_enhance(img)
        assert params == dict(FIXED_PARAMS)
        assert type(params) is dict
        assert json.loads(json.dumps(params, allow_nan=False)) == params
        assert out.dtype == np.uint8 and out.shape == img.shape
        configs.append(params)
    assert len({id(p) for p in configs}) == len(images)


def test_real_output_matches_explicit_operations_and_repeats():
    img = np.random.default_rng(47).integers(0, 256, (21, 29, 3), dtype=np.uint8)
    before = img.copy()
    out, params = fixed_enhance(img)
    expected = unsharp(gamma(gaussian(img, 3, 1.0), 0.75), 0.8, 1.0, 5.0)
    np.testing.assert_array_equal(out, expected)
    np.testing.assert_array_equal(out, apply_ops(img, params))
    np.testing.assert_array_equal(fixed_enhance(img)[0], out)
    np.testing.assert_array_equal(img, before)
    assert not np.shares_memory(out, img)


def test_returned_params_and_output_cannot_change_future_results():
    img = np.full((7, 9, 3), 40, np.uint8)
    out, params = fixed_enhance(img)
    expected = out.copy()
    params["gamma"] = 3.0
    params["extra"] = ["caller metadata"]
    params.clear()
    out[:] = 0
    next_out, next_params = fixed_enhance(img)
    np.testing.assert_array_equal(next_out, expected)
    assert next_params == dict(FIXED_PARAMS)


def test_global_configuration_is_read_only():
    with pytest.raises(TypeError):
        FIXED_PARAMS["gamma"] = 3.0


def test_delegates_to_shared_runner_with_fresh_dict(monkeypatch):
    img = np.full((3, 5, 3), 80, np.uint8)
    calls = []
    def capture(frame, params):
        assert frame is img
        calls.append(params)
        return frame.copy()
    monkeypatch.setattr(fixed, "apply_ops", capture)
    out, params = fixed_enhance(img)
    assert calls == [params] and calls[0] is params
    assert params == dict(FIXED_PARAMS)
    assert params is not FIXED_PARAMS
    np.testing.assert_array_equal(out, img)


@pytest.mark.parametrize("shape", [(1, 1, 3), (1, 9, 3), (9, 1, 3)])
def test_small_and_read_only_frames(shape):
    img = np.full(shape, 60, np.uint8)[:, ::-1]
    img.flags.writeable = False
    before = img.copy()
    out, params = fixed_enhance(img)
    np.testing.assert_array_equal(img, before)
    np.testing.assert_array_equal(out, apply_ops(before, params))


@pytest.mark.parametrize("bad", [None, np.zeros((2, 3, 3)), np.zeros((0, 3, 3), np.uint8),
                                 np.zeros((2, 3), np.uint8)])
def test_invalid_frame(bad):
    with pytest.raises(ValueError):
        fixed_enhance(bad)
