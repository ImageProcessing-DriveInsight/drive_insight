"""Small image helpers shared by the plate module (NumPy; cv2 only for file I/O)."""

from pathlib import Path

import cv2
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


def load_png(path):
    """Read an image as uint8 BGR (works with non-ASCII paths on Windows)."""
    img = cv2.imdecode(np.fromfile(str(path), np.uint8), cv2.IMREAD_COLOR)
    if img is None:
        raise ValueError(f"cannot decode image: {path}")
    return img


def save_png(path, img):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    ok, buf = cv2.imencode(".png", img)
    if not ok:
        raise ValueError(f"cannot encode image: {path}")
    buf.tofile(str(path))
