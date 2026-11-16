"""A-01 through A-03: reference, invariant and input validation tests."""

import numpy as np
import pytest

from src.dip import bgr_to_ycrcb, gamma, gaussian, hist_eq, median, ycrcb_to_bgr


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


@pytest.mark.parametrize("ksize", [3, 5, 7, 9])
@pytest.mark.parametrize("sigma", [0.1, 0.7, 1.5, 3.0, 100.0])
@pytest.mark.parametrize("shape", [(17, 23, 3), (1, 1, 3), (1, 7, 3), (9, 1, 3), (2, 2, 3)])
def test_gaussian_reference(ksize, sigma, shape):
    import cv2
    img = np.random.default_rng(29).integers(0, 256, shape, dtype=np.uint8)
    expected = cv2.GaussianBlur(img, (ksize, ksize), sigma, borderType=cv2.BORDER_REFLECT_101)
    assert error(gaussian(img, ksize, sigma), expected).max() <= 1


@pytest.mark.parametrize("value", [0, 71, 255])
def test_gaussian_constant_and_input_preservation(value):
    img = np.full((5, 7, 3), value, dtype=np.uint8)[:, ::-1]
    before = img.copy()
    out = gaussian(img, 9, 1.2)
    np.testing.assert_array_equal(out, before)
    np.testing.assert_array_equal(img, before)
    assert out.dtype == np.uint8 and not np.shares_memory(img, out)


@pytest.mark.parametrize("ksize", [0, 1, 2, 4, 11, 3.0, True, None, '3'])
def test_gaussian_invalid_size(ksize):
    with pytest.raises(ValueError):
        gaussian(sample_frame(), ksize, 1)


@pytest.mark.parametrize("sigma", [0, -1, np.nan, np.inf, True, None, '1', 1j])
def test_gaussian_invalid_sigma(sigma):
    with pytest.raises(ValueError):
        gaussian(sample_frame(), 3, sigma)


@pytest.mark.parametrize("bad", [None, np.zeros((2, 3, 3)), np.zeros((0, 3, 3), np.uint8),
                                 np.zeros((3, 3), np.uint8)])
def test_gaussian_invalid_frame(bad):
    with pytest.raises(ValueError):
        gaussian(bad, 3, 1)


def test_gaussian_channel_independence_and_strides():
    img = np.zeros((13, 17, 3), np.uint8)
    img[6, 8, 0] = 255
    before = img.copy()
    out = gaussian(img[:, ::-1], np.int64(5), np.float64(1.2))
    assert out[..., 0].max() > 0
    assert not out[..., 1:].any()
    np.testing.assert_array_equal(img, before)


@pytest.mark.parametrize("ksize", [3, 5])
@pytest.mark.parametrize("shape", [(70, 23, 3), (1, 1, 3), (1, 7, 3), (9, 1, 3), (2, 2, 3)])
def test_median_reference(ksize, shape):
    import cv2
    img = np.random.default_rng(30).integers(0, 256, shape, dtype=np.uint8)
    np.testing.assert_array_equal(median(img, ksize), cv2.medianBlur(img, ksize))


@pytest.mark.parametrize("ksize", [3, 5])
def test_median_removes_salt_pepper_and_preserves_channels(ksize):
    img = np.tile(np.array([40, 100, 160], np.uint8), (11, 13, 1))
    expected = img.copy()
    img[3, 3] = 0
    img[7, 8] = 255
    before = img.copy()
    np.testing.assert_array_equal(median(img[:, ::-1], ksize), expected[:, ::-1])
    np.testing.assert_array_equal(img, before)


@pytest.mark.parametrize("value", [0, 83, 255])
def test_median_constant(value):
    img = np.full((3, 7, 3), value, np.uint8)
    out = median(img, np.int64(5))
    np.testing.assert_array_equal(out, img)
    assert out.dtype == np.uint8 and not np.shares_memory(img, out)


@pytest.mark.parametrize("ksize", [0, 1, 2, 4, 7, 9, 3.0, True, None, '3'])
def test_median_invalid_size(ksize):
    with pytest.raises(ValueError):
        median(sample_frame(), ksize)


@pytest.mark.parametrize("bad", [None, np.zeros((2, 3, 3)), np.zeros((0, 3, 3), np.uint8),
                                 np.zeros((3, 3), np.uint8)])
def test_median_invalid_frame(bad):
    with pytest.raises(ValueError):
        median(bad, 3)
