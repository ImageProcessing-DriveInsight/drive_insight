"""Luminance corrections. OpenCV is deliberately absent from this module."""

from numbers import Integral, Real
from concurrent.futures import ThreadPoolExecutor
import os

import numpy as np

from .color import bgr_to_ycrcb, to_uint8, validate_frame, ycrcb_to_bgr

_MEDIAN_BLOCK_ROWS = 32
_MEDIAN_MAX_WORKERS = 4
_MEDIAN_PARALLEL_MIN_PIXELS = 512 * 512


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
    kernel = integer_kernel.astype(np.float32) / 256.0
    # Products have at most 8 integer + 16 fraction bits after two passes,
    # so float32 stores these fixed-point sums exactly while halving buffers.
    source = img.astype(np.float32)
    height, width = img.shape[:2]
    padded = np.pad(source, ((0, 0), (radius, radius), (0, 0)), mode="reflect")
    horizontal = kernel[radius] * padded[:, radius:radius + width]
    scratch = source  # Padding already owns a copy; reuse the converted input buffer.
    # Pair symmetric taps, reusing one scratch array instead of per-tap products.
    # These nonnegative fixed-point sums are exact even when regrouped.
    for index in range(radius):
        np.add(padded[:, index:index + width],
               padded[:, ksize - 1 - index:ksize - 1 - index + width], out=scratch)
        np.multiply(scratch, kernel[index], out=scratch)
        np.add(horizontal, scratch, out=horizontal)
    padded = np.pad(horizontal, ((radius, radius), (0, 0), (0, 0)), mode="reflect")
    result = kernel[radius] * padded[radius:radius + height]
    for index in range(radius):
        np.add(padded[index:index + height],
               padded[ksize - 1 - index:ksize - 1 - index + height], out=scratch)
        np.multiply(scratch, kernel[index], out=scratch)
        np.add(result, scratch, out=result)
    return result


def gaussian(img, ksize, sigma):
    """Blur BGR channels with a normalized separable Gaussian and REFLECT_101 borders.

    ksize is an odd integer from 3 through 9; sigma must be finite and positive.
    Round only after both 1D passes. Single-row/column frames are supported.
    """
    validate_frame(img)
    _validate_ksize(ksize, (3, 5, 7, 9))
    _validate_real(sigma, "sigma", strictly_positive=True)
    result = _gaussian_blur(img, ksize, sigma)
    np.add(result, 0.5, out=result)
    np.floor(result, out=result)
    np.clip(result, 0, 255, out=result)
    return result.astype(np.uint8)


def median(img, ksize):
    """Median of each BGR channel in a 3x3 or 5x5 window, replicating borders.

    Process vectorized 32-row blocks using int32 partition buffers (exact for uint8).
    Large images use at most four workers with disjoint outputs. No pixel loops,
    channel mixing or input mutation; smaller images run in the calling thread.
    """
    validate_frame(img)
    _validate_ksize(ksize, (3, 5))
    radius = ksize // 2
    padded = np.pad(img, ((radius, radius), (radius, radius), (0, 0)), mode="edge")
    windows = np.lib.stride_tricks.sliding_window_view(padded, (ksize, ksize), axis=(0, 1))
    out = np.empty_like(img)
    def process(start):
        stop = start + _MEDIAN_BLOCK_ROWS
        # NumPy's int32 selection path is faster here; values 0..255 remain exact.
        # Each worker owns its partition buffer, never writing the overlapping view.
        block = np.array(windows[start:stop], dtype=np.int32, order="C")
        block = block.reshape(*block.shape[:3], ksize * ksize)
        out[start:stop] = np.median(block, axis=-1, overwrite_input=True)
    starts = range(0, img.shape[0], _MEDIAN_BLOCK_ROWS)
    workers = min(_MEDIAN_MAX_WORKERS, os.cpu_count() or 1, len(starts))
    if workers > 1 and img.shape[0] * img.shape[1] >= _MEDIAN_PARALLEL_MIN_PIXELS:
        with ThreadPoolExecutor(max_workers=workers) as pool:
            # Observe every result so worker errors propagate before returning.
            list(pool.map(process, starts))
    else:
        for start in starts:
            process(start)
    return out


def unsharp(img, amount, sigma, threshold):
    """Sharpen BGR channels: img + amount*(img-blur), clipped to uint8.

    Apply only where abs(img-blur) >= threshold (per channel).
    amount/threshold are finite and nonnegative; sigma is finite and positive.
    Gaussian radius is ceil(3*sigma), limited to 1..4 (ksize 3..9).
    """
    validate_frame(img)
    _validate_real(amount, "amount")
    _validate_real(sigma, "sigma", strictly_positive=True)
    _validate_real(threshold, "threshold")
    if amount == 0:
        return img.copy()
    radius = max(1, int(np.ceil(min(3.0 * sigma, 4.0))))
    difference = img.astype(np.int16) - gaussian(img, 2 * radius + 1, sigma).astype(np.int16)
    difference[np.abs(difference) < threshold] = 0
    with np.errstate(over="ignore"):
        result = np.multiply(difference, amount, dtype=np.float64)
        np.add(result, img, out=result)
    np.rint(result, out=result)
    np.clip(result, 0, 255, out=result)
    return result.astype(np.uint8)


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
