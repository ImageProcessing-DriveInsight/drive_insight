"""Small image helpers shared by the plate module (NumPy only)."""

import numpy as np


def validate_frame(frame):
    """Raise ValueError unless frame is uint8 BGR with shape (H, W, 3)."""
    if not isinstance(frame, np.ndarray) or frame.dtype != np.uint8:
        raise ValueError("frame must be a uint8 numpy array")
    if frame.ndim != 3 or frame.shape[2] != 3 or min(frame.shape[:2]) < 1:
        raise ValueError("frame must have shape (H, W, 3)")
    return frame


def to_gray(img):
    """BGR -> Y with the BT.601 weighted sum, uint8."""
    return (img[..., 2] * 0.299 + img[..., 1] * 0.587 + img[..., 0] * 0.114 + 0.5).astype(np.uint8)
