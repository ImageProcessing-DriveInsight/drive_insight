"""Plate crop preprocessing (C-04, own implementation, NumPy only).

gray -> resize to TARGET_H (bilinear) -> contrast stretch -> dark text on light
background -> deskew -> optional Otsu binarization.
"""

import numpy as np

from .imgutil import to_gray

TARGET_H = 64
MAX_ANGLE, ANGLE_STEP = 10.0, 0.5  # deskew search range in degrees


def resize_bilinear(img, out_h, out_w):
    h, w = img.shape[:2]
    ys = np.clip((np.arange(out_h) + 0.5) * h / out_h - 0.5, 0, h - 1)
    xs = np.clip((np.arange(out_w) + 0.5) * w / out_w - 0.5, 0, w - 1)
    y0, x0 = np.floor(ys).astype(int), np.floor(xs).astype(int)
    y1, x1 = np.minimum(y0 + 1, h - 1), np.minimum(x0 + 1, w - 1)
    wy, wx = (ys - y0)[:, None], (xs - x0)[None, :]
    if img.ndim == 3:
        wy, wx = wy[..., None], wx[..., None]
    f = img.astype(np.float64)
    a, b = f[y0][:, x0], f[y0][:, x1]
    c, d = f[y1][:, x0], f[y1][:, x1]
    out = a * (1 - wx) * (1 - wy) + b * wx * (1 - wy) + c * (1 - wx) * wy + d * wx * wy
    return np.clip(out + 0.5, 0, 255).astype(np.uint8)


def contrast_stretch(gray, lo_pct=2, hi_pct=98):
    lo, hi = np.percentile(gray, [lo_pct, hi_pct])
    if hi <= lo:
        return gray
    return np.clip((gray - lo) * 255.0 / (hi - lo), 0, 255).astype(np.uint8)


def otsu(gray):
    """Otsu threshold. Returns (binary with 0/255, threshold)."""
    p = np.bincount(gray.ravel(), minlength=256) / gray.size
    omega, mu = np.cumsum(p), np.cumsum(p * np.arange(256))
    with np.errstate(divide="ignore", invalid="ignore"):
        sigma_b = (mu[-1] * omega - mu) ** 2 / (omega * (1 - omega))
    t = int(np.nanargmax(sigma_b)) if np.isfinite(sigma_b).any() else 127
    return np.where(gray > t, 255, 0).astype(np.uint8), t


def text_is_light(gray):
    """Text covers less area than the plate background, so the minority Otsu class is the text.

    Only the central part is used, where the plate fills the crop (margins may show the bumper).
    """
    h, w = gray.shape
    binary, _ = otsu(gray[h // 5:h - h // 5, w // 5:w - w // 5])
    return (binary == 255).mean() < 0.5


def rotate_bilinear(gray, angle):
    """Rotate about the center by angle degrees, filling the corners with the median."""
    h, w = gray.shape
    t = np.deg2rad(angle)
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float64)
    cx, cy = (w - 1) / 2, (h - 1) / 2
    # inverse mapping: output (x', y') reads input R(-angle) (x', y')
    sx = (xx - cx) * np.cos(t) + (yy - cy) * np.sin(t) + cx
    sy = -(xx - cx) * np.sin(t) + (yy - cy) * np.cos(t) + cy
    inside = (sx >= 0) & (sx <= w - 1) & (sy >= 0) & (sy <= h - 1)
    sx, sy = np.clip(sx, 0, w - 1), np.clip(sy, 0, h - 1)
    x0, y0 = np.floor(sx).astype(int), np.floor(sy).astype(int)
    x1, y1 = np.minimum(x0 + 1, w - 1), np.minimum(y0 + 1, h - 1)
    wx, wy = sx - x0, sy - y0
    f = gray.astype(np.float64)
    out = (f[y0, x0] * (1 - wx) * (1 - wy) + f[y0, x1] * wx * (1 - wy)
           + f[y1, x0] * (1 - wx) * wy + f[y1, x1] * wx * wy)
    out[~inside] = np.median(gray)
    return np.clip(out + 0.5, 0, 255).astype(np.uint8)


def estimate_skew(gray):
    """Angle (degrees) to pass to rotate_bilinear so text rows become horizontal.

    Tries every angle in [-MAX_ANGLE, MAX_ANGLE] and keeps the one whose row
    projection of dark (text) pixels is the most concentrated (largest sum of squares).
    """
    binary, _ = otsu(gray)
    ys, xs = np.nonzero(binary == 0)
    if len(ys) < 10:
        return 0.0
    xs, ys = xs - gray.shape[1] / 2, ys - gray.shape[0] / 2
    best, best_score = 0.0, -1.0
    for a in sorted(np.arange(-MAX_ANGLE, MAX_ANGLE + 1e-9, ANGLE_STEP), key=abs):  # ties keep the smaller angle
        t = np.deg2rad(a)
        rows = np.round(xs * np.sin(t) + ys * np.cos(t)).astype(int)  # row after rotating by a
        score = (np.bincount(rows - rows.min()).astype(np.float64) ** 2).sum()
        if score > best_score + 1e-9:
            best, best_score = float(a), score
    return best


def preprocess_plate(crop, binarize=False, deskew=True):
    """Prepare a plate crop for OCR.

    Args:
        crop: uint8 BGR (H, W, 3) or gray (H, W).
        binarize: apply Otsu at the end.
        deskew: rotate text rows to horizontal.

    Returns:
        uint8 gray (TARGET_H, W') with dark text on a light background.
    """
    if not isinstance(crop, np.ndarray) or crop.dtype != np.uint8 or crop.ndim not in (2, 3) or min(crop.shape[:2]) < 2:
        raise ValueError("crop must be a uint8 image at least 2x2")
    gray = to_gray(crop) if crop.ndim == 3 else crop
    h, w = gray.shape
    gray = resize_bilinear(gray, TARGET_H, max(1, round(w * TARGET_H / h)))
    gray = contrast_stretch(gray)
    if text_is_light(gray):  # e.g. old green plates: white text
        gray = 255 - gray
    if deskew:
        gray = rotate_bilinear(gray, estimate_skew(gray))
    return otsu(gray)[0] if binarize else gray
