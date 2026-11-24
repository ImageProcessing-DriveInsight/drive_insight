"""A-07 operation dispatch and validation, independent of pretrained models."""

from copy import deepcopy
from itertools import permutations

import numpy as np
import pytest

from src.dip import apply_ops, gamma, gaussian, hist_eq, median, unsharp
import src.dip.fixed as fixed


@pytest.fixture
def frame():
    return np.random.default_rng(44).integers(0, 256, (17, 23, 3), dtype=np.uint8)


@pytest.mark.parametrize("params", [{}, {"rules": object()},
    {"gamma": 1, "hist_eq": False, "denoise": "none", "unsharp": 0},
    {"ksize": 5, "sigma": 2, "unsharp_sigma": 2, "unsharp_threshold": 10}])
def test_identity_returns_copy(frame, params):
    out = apply_ops(frame, params)
    np.testing.assert_array_equal(out, frame)
    assert not np.shares_memory(out, frame)


@pytest.mark.parametrize("params,operation", [
    ({"denoise": "gaussian"}, lambda f: gaussian(f, 3, 1.0)),
    ({"denoise": "gaussian", "ksize": 7, "sigma": 1.5}, lambda f: gaussian(f, 7, 1.5)),
    ({"denoise": "median"}, lambda f: median(f, 3)),
    ({"denoise": "median", "ksize": 5}, lambda f: median(f, 5)),
    ({"gamma": 0.5}, lambda f: gamma(f, 0.5)),
    ({"hist_eq": True}, hist_eq),
    ({"unsharp": 0.8}, lambda f: unsharp(f, 0.8, 1.0, 5.0)),
    ({"unsharp": 1.2, "unsharp_sigma": 0.5, "unsharp_threshold": 10},
     lambda f: unsharp(f, 1.2, 0.5, 10)),
])
def test_single_operation_and_defaults(frame, params, operation):
    np.testing.assert_array_equal(apply_ops(frame, params), operation(frame))


@pytest.mark.parametrize("denoise", ["gaussian", "median"])
def test_complete_chain_and_input_preservation(frame, denoise):
    params = {"denoise": denoise, "ksize": 5, "sigma": 1.5, "gamma": 0.7,
              "hist_eq": True, "unsharp": 1.2, "unsharp_sigma": 0.5,
              "unsharp_threshold": 3, "rules": ["TEST"]}
    before, config_before = frame.copy(), deepcopy(params)
    denoised = gaussian(frame, 5, 1.5) if denoise == "gaussian" else median(frame, 5)
    expected = unsharp(hist_eq(gamma(denoised, 0.7)), 1.2, 0.5, 3)
    out = apply_ops(frame, params)
    np.testing.assert_array_equal(out, expected)
    np.testing.assert_array_equal(frame, before)
    assert params == config_before
    assert out.shape == frame.shape and out.dtype == np.uint8


def test_order_is_independent_of_key_insertion(frame, monkeypatch):
    calls = []
    for name in ("gaussian", "gamma", "hist_eq", "unsharp"):
        def record(img, *args, name=name):
            calls.append((name, int(img[0, 0, 0])))
            return img + np.uint8(1)
        monkeypatch.setattr(fixed.ops, name, record)
    for keys in permutations(("denoise", "gamma", "hist_eq", "unsharp")):
        calls.clear()
        values = dict(denoise="gaussian", gamma=0.5, hist_eq=True, unsharp=0.8)
        apply_ops(np.zeros_like(frame), {key: values[key] for key in keys})
        assert calls == [("gaussian", 0), ("gamma", 1), ("hist_eq", 2), ("unsharp", 3)]


@pytest.mark.parametrize("params", [None, [], "gamma", 1, {"unknown": 1}, {1: 0},
    {"denoise": None}, {"denoise": True}, {"denoise": "bilateral"},
    {"ksize": 0}, {"ksize": 3.0}, {"ksize": True}, {"denoise": "median", "ksize": 7},
    {"sigma": 0}, {"sigma": np.nan}, {"sigma": True},
    {"gamma": 0.29}, {"gamma": 3.01}, {"gamma": np.inf}, {"gamma": True}, {"gamma": "0.5"},
    {"hist_eq": 1}, {"hist_eq": None}, {"hist_eq": "true"}, {"hist_eq": np.bool_(True)},
    {"unsharp": -1}, {"unsharp": True}, {"unsharp": np.nan},
    {"unsharp_sigma": 0}, {"unsharp_sigma": np.inf},
    {"unsharp_threshold": -1}, {"unsharp_threshold": True}, {"unsharp_threshold": None}])
def test_invalid_params_fail_before_processing(frame, params, monkeypatch):
    def unexpected(*args):
        pytest.fail("an operation ran before validation completed")
    monkeypatch.setattr(fixed.ops, "gamma", unexpected)
    # An invalid later option must not allow an earlier valid gamma to run.
    if isinstance(params, dict):
        params = {"gamma": 0.5, **params}
    with pytest.raises(ValueError):
        apply_ops(frame, params)


@pytest.mark.parametrize("bad", [None, np.zeros((2, 3, 3)),
    np.zeros((0, 3, 3), np.uint8), np.zeros((2, 3), np.uint8)])
def test_invalid_frames_even_with_no_ops(bad):
    with pytest.raises(ValueError):
        apply_ops(bad, {})


def test_read_only_strided_input(frame):
    view = frame[:, ::-2]
    before = view.copy()
    view.flags.writeable = False
    out = apply_ops(view, {"denoise": "median", "gamma": 0.5})
    np.testing.assert_array_equal(out, gamma(median(before, 3), 0.5))
    np.testing.assert_array_equal(view, before)
