"""A-01 through A-03: reference, invariant and input validation tests."""

import numpy as np
import pytest

from src.dip import bgr_to_ycrcb, gamma, hist_eq, ycrcb_to_bgr


def sample_frame():
    return np.random.default_rng(19).integers(0, 256, (64, 87, 3), dtype=np.uint8)


def gray(values):
    return np.repeat(np.asarray(values, dtype=np.uint8)[..., None], 3, axis=-1)


def error(a, b):
    return np.abs(a.astype(np.int16) - b.astype(np.int16))


def test_color_round_trip():
    img = sample_frame()
    assert error(ycrcb_to_bgr(bgr_to_ycrcb(img)), img).max() <= 2


def test_primary_and_neutral_colors():
    img = np.array([[[0, 0, 0], [255, 255, 255], [255, 0, 0],
                     [0, 255, 0], [0, 0, 255]]], dtype=np.uint8)
    converted = bgr_to_ycrcb(img)
    np.testing.assert_array_equal(converted[0, :2], [[0, 128, 128], [255, 128, 128]])
    np.testing.assert_allclose(converted[0, 4], [76, 255, 85], atol=1)
    assert error(ycrcb_to_bgr(converted), img).max() <= 2


@pytest.mark.parametrize("g", [0.3, 0.5, 1, 2, 3.0])
def test_gamma_gray_ramp(g):
    values = np.arange(256, dtype=np.uint8).reshape(16, 16)
    out = gamma(gray(values), g)
    expected = np.rint(255 * (values.astype(float) / 255) ** g).astype(np.uint8)
    np.testing.assert_array_equal(out, gray(expected))


def test_gamma_identity_is_exact_for_color():
    img = sample_frame()
    np.testing.assert_array_equal(gamma(img, 1), img)


@pytest.mark.parametrize("g", [0.29, 3.01, 0, -1, float('nan'), float('inf'),
                              True, None, '0.5', 1j, [0.5]])
def test_gamma_rejects_invalid_exponents(g):
    with pytest.raises(ValueError):
        gamma(sample_frame(), g)


@pytest.mark.parametrize("value", [0, 42, 255])
def test_hist_eq_preserves_constant(value):
    img = np.full((4, 5, 3), value, dtype=np.uint8)
    np.testing.assert_array_equal(hist_eq(img), img)


def test_hist_eq_preserves_constant_colored_frame():
    img = np.tile(np.array([21, 120, 243], dtype=np.uint8), (5, 7, 1))
    np.testing.assert_array_equal(hist_eq(img), img)


def test_hist_eq_hand_computed_distribution():
    img = gray([[10, 10, 20], [20, 30, 40]])
    expected = gray([[0, 0, 128], [128, 191, 255]])
    np.testing.assert_array_equal(hist_eq(img), expected)


@pytest.mark.parametrize("operation", [bgr_to_ycrcb, ycrcb_to_bgr, hist_eq,
                                       lambda img: gamma(img, 0.6)])
def test_operations_preserve_input_and_support_strides(operation):
    img = sample_frame()[:, ::-2]
    before = img.copy()
    out = operation(img)
    np.testing.assert_array_equal(img, before)
    assert out.shape == img.shape and out.dtype == np.uint8
    assert not np.shares_memory(out, img)


@pytest.mark.parametrize("bad", [None, [[[0, 0, 0]]], np.zeros((2, 3)),
    np.zeros((2, 3, 3), dtype=np.float32), np.zeros((2, 3, 4), dtype=np.uint8),
    np.zeros((0, 3, 3), dtype=np.uint8), np.zeros((2, 0, 3), dtype=np.uint8),
    np.zeros((3,), dtype=np.uint8)])
@pytest.mark.parametrize("operation", [bgr_to_ycrcb, ycrcb_to_bgr, hist_eq,
                                       lambda img: gamma(img, 0.6)])
def test_operations_reject_invalid_frames(operation, bad):
    with pytest.raises(ValueError):
        operation(bad)


def test_opencv_color_reference():
    import cv2
    img = sample_frame()
    expected = cv2.cvtColor(img, cv2.COLOR_BGR2YCrCb)
    assert error(bgr_to_ycrcb(img), expected).max() <= 1
    assert error(ycrcb_to_bgr(expected), cv2.cvtColor(expected, cv2.COLOR_YCrCb2BGR)).max() <= 1


def test_opencv_histogram_reference():
    import cv2
    img = sample_frame()
    # Use exactly the same Y plane to isolate equalization from conversion rounding.
    ycrcb = bgr_to_ycrcb(img)
    ycrcb[..., 0] = cv2.equalizeHist(ycrcb[..., 0])
    assert error(hist_eq(img), ycrcb_to_bgr(ycrcb)).mean() <= 1
    ramp = gray(np.random.default_rng(3).integers(25, 180, (80, 90), dtype=np.uint8))
    np.testing.assert_array_equal(hist_eq(ramp)[..., 0], cv2.equalizeHist(ramp[..., 0]))
