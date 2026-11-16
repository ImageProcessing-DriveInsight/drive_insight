"""Full-range BT.601 BGR/YCrCb conversion, implemented with NumPy."""

import numpy as np


def validate_frame(img):
    """Require a nonempty uint8 array with three channels."""
    if not isinstance(img, np.ndarray) or img.dtype != np.uint8:
        raise ValueError("img must be a uint8 numpy array")
    if img.ndim != 3 or img.shape[2] != 3 or min(img.shape[:2]) == 0:
        raise ValueError("img must have shape (H, W, 3) with H, W > 0")


def to_uint8(values):
    """Round to nearest integer and saturate instead of wrapping."""
    return np.clip(np.rint(values), 0, 255).astype(np.uint8)


def bgr_to_ycrcb(img):
    """Convert uint8 BGR to uint8 (Y, Cr, Cb), with chroma centered at 128."""
    validate_frame(img)
    b, g, r = np.moveaxis(img.astype(np.float64), -1, 0)
    y = 0.114 * b + 0.587 * g + 0.299 * r
    cr = (r - y) * 0.713 + 128.0
    cb = (b - y) * 0.564 + 128.0
    return to_uint8(np.stack((y, cr, cb), axis=-1))


def ycrcb_to_bgr(img):
    """Convert uint8 (Y, Cr, Cb) to uint8 BGR, clipping out-of-gamut colors."""
    validate_frame(img)
    y, cr, cb = np.moveaxis(img.astype(np.float64), -1, 0)
    r = y + (cr - 128.0) / 0.713
    b = y + (cb - 128.0) / 0.564
    g = (y - 0.299 * r - 0.114 * b) / 0.587
    return to_uint8(np.stack((b, g, r), axis=-1))
