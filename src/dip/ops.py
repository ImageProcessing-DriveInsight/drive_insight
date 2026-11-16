"""Luminance corrections. OpenCV is deliberately absent from this module."""

from numbers import Real

import numpy as np

from .color import bgr_to_ycrcb, to_uint8, validate_frame, ycrcb_to_bgr


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
