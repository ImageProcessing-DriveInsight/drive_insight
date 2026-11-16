"""Luminance corrections. OpenCV is deliberately absent from this module."""

from numbers import Integral, Real

import numpy as np

from .color import bgr_to_ycrcb, to_uint8, validate_frame, ycrcb_to_bgr


def _validate_ksize(ksize, allowed):
    if isinstance(ksize, (bool, np.bool_)) or not isinstance(ksize, Integral) or ksize not in allowed:
        raise ValueError(f"ksize must be one of {tuple(allowed)}")


def _validate_real(value, name, minimum=0.0, strictly_positive=False):
    if isinstance(value, (bool, np.bool_)) or not isinstance(value, Real):
        raise ValueError(f"{name} must be a finite real number")
    if not np.isfinite(value) or value < minimum or (strictly_positive and value == 0):
        raise ValueError(f"{name} must be finite and {'positive' if strictly_positive else f'>= {minimum}'}")


def _gaussian_blur(img, ksize, sigma):
    """Float blur without intermediate rounding; reflect excludes the edge pixel."""
    radius = ksize // 2
    positions = np.arange(-radius, radius + 1, dtype=np.float64)
    with np.errstate(over="ignore", under="ignore"):
        kernel = np.exp(-0.5 * (positions / sigma) ** 2)
    kernel /= kernel.sum()
    # Symmetric 8-bit coefficients, with residual carried to the next tap.
    # This matches the uint8 Gaussian reference's fixed-point convention.
    residual = 0.0
    integer_kernel = np.zeros(ksize, dtype=np.int64)
    for index in range(radius):
        value = kernel[index] * 256.0 + residual
        coefficient = int(np.rint(value))
        residual = value - coefficient
        integer_kernel[index] = integer_kernel[-index - 1] = coefficient
    integer_kernel[radius] = 256 - 2 * integer_kernel[:radius].sum()
    kernel = integer_kernel / 256.0
    source = img.astype(np.float64)
    height, width = img.shape[:2]
    padded = np.pad(source, ((0, 0), (radius, radius), (0, 0)), mode="reflect")
    horizontal = np.zeros_like(source)
    # Only the small kernel is iterated, never pixels or rows.
    for index, weight in enumerate(kernel):
        horizontal += weight * padded[:, index:index + width]
    padded = np.pad(horizontal, ((radius, radius), (0, 0), (0, 0)), mode="reflect")
    result = np.zeros_like(source)
    for index, weight in enumerate(kernel):
        result += weight * padded[index:index + height]
    return result


def gaussian(img, ksize, sigma):
    """Blur BGR channels with a normalized separable Gaussian and REFLECT_101 borders.

    ksize is an odd integer from 3 through 9; sigma must be finite and positive.
    Round only after both 1D passes. Single-row/column frames are supported.
    """
    validate_frame(img)
    _validate_ksize(ksize, (3, 5, 7, 9))
    _validate_real(sigma, "sigma", strictly_positive=True)
    return np.clip(np.floor(_gaussian_blur(img, ksize, sigma) + 0.5), 0, 255).astype(np.uint8)


def gamma(img, g):
    """Apply Y'=255*(Y/255)**g via a 256-entry LUT; g<1 brightens."""
    validate_frame(img)
    if isinstance(g, (bool, np.bool_)) or not isinstance(g, Real):
        raise ValueError("g must be a finite real number in [0.3, 3.0]")
    if not np.isfinite(g) or not 0.3 <= g <= 3.0:
        raise ValueError("g must be a finite real number in [0.3, 3.0]")
    if g == 1:
        return img.copy()
    lut = to_uint8(255.0 * (np.arange(256, dtype=np.float64) / 255.0) ** g)
    ycrcb = bgr_to_ycrcb(img)
    ycrcb[..., 0] = lut[ycrcb[..., 0]]
    return ycrcb_to_bgr(ycrcb)


def hist_eq(img):
    """Equalize the 256-bin Y histogram using a CDF with its minimum removed."""
    validate_frame(img)
    ycrcb = bgr_to_ycrcb(img)
    y = ycrcb[..., 0]
    hist = np.bincount(y.ravel(), minlength=256)
    occupied = np.flatnonzero(hist)
    if occupied.size == 1:
        return img.copy()
    cdf = hist.cumsum()
    cdf_min = cdf[occupied[0]]
    lut = to_uint8((cdf - cdf_min) * (255.0 / (y.size - cdf_min)))
    ycrcb[..., 0] = lut[y]
    return ycrcb_to_bgr(ycrcb)
