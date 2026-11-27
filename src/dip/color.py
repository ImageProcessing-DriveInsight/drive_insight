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


def _store_channel(values, destination):
    """Quantize an owned float buffer into one output channel without stacking."""
    np.rint(values, out=values)
    np.clip(values, 0, 255, out=values)
    destination[:] = values


def bgr_to_ycrcb(img):
    """Convert uint8 BGR to uint8 (Y, Cr, Cb), with chroma centered at 128."""
    validate_frame(img)
    # Preserve the original float64 operation order while avoiding full BGR
    # float conversion, channel stacking and repeated full-image clipping copies.
    y = np.multiply(img[..., 0], 0.114, dtype=np.float64)
    scratch = np.empty_like(y)
    np.multiply(img[..., 1], 0.587, out=scratch)
    np.add(y, scratch, out=y)
    np.multiply(img[..., 2], 0.299, out=scratch)
    np.add(y, scratch, out=y)
    out = np.empty_like(img)
    np.subtract(img[..., 2], y, out=scratch)
    np.multiply(scratch, 0.713, out=scratch)
    np.add(scratch, 128.0, out=scratch)
    _store_channel(scratch, out[..., 1])
    np.subtract(img[..., 0], y, out=scratch)
    np.multiply(scratch, 0.564, out=scratch)
    np.add(scratch, 128.0, out=scratch)
    _store_channel(scratch, out[..., 2])
    _store_channel(y, out[..., 0])
    return out


def ycrcb_to_bgr(img):
    """Convert uint8 (Y, Cr, Cb) to uint8 BGR, clipping out-of-gamut colors."""
    validate_frame(img)
    r = np.subtract(img[..., 1], 128.0, dtype=np.float64)
    np.divide(r, 0.713, out=r)
    np.add(img[..., 0], r, out=r)
    b = np.subtract(img[..., 2], 128.0, dtype=np.float64)
    np.divide(b, 0.564, out=b)
    np.add(img[..., 0], b, out=b)
    g = np.multiply(r, 0.299)
    np.subtract(img[..., 0], g, out=g)
    scratch = np.multiply(b, 0.114)
    np.subtract(g, scratch, out=g)
    np.divide(g, 0.587, out=g)
    out = np.empty_like(img)
    _store_channel(b, out[..., 0])
    _store_channel(g, out[..., 1])
    _store_channel(r, out[..., 2])
    return out
