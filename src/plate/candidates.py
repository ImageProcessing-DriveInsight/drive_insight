"""Plate candidate search inside vehicle boxes (C-03, own implementation, NumPy only).

A plate has dense vertical edges (characters) on a bright background, while the
bumper around it is smooth. Every window is scored by center-surround contrast:
its edge density and brightness minus those of a ring around it, using integral
images. The best window of each size is then grown to the full dense-edge area.
"""

import numpy as np

from .imgutil import to_gray, validate_frame

SEARCH_TOP = 0.35  # search below this fraction of the vehicle box height
MARGIN_X, MARGIN_BOTTOM = 0.05, 0.1  # extend the search past the box edges
WIDTH_FRACS = (0.12, 0.15, 0.19, 0.24, 0.3, 0.38, 0.48, 0.6)  # plate width / vehicle width
FRAME_WIDTH_FRACS = (0.05, 0.07, 0.1, 0.14, 0.2, 0.28)  # plate width / frame width, no vehicles
ASPECTS = (2.0, 3.0, 4.5)  # plate width / height: two-line to long one-line plates
MIN_W, MIN_H = 24, 8
BRIGHT_W = 1.0  # weight of the brightness term against the edge term
GROW_FRAC = 0.35  # grow while the edge profile stays above this share of the box mean
TOP_K = 3  # candidates kept per vehicle
NMS_IOU = 0.3


def vertical_edges(gray):
    """Horizontal gradient magnitude |I(x+1) - I(x-1)| / 2, zero at the borders."""
    g = gray.astype(np.float32)
    e = np.zeros_like(g)
    e[:, 1:-1] = np.abs(g[:, 2:] - g[:, :-2]) * 0.5
    return e


def integral(a):
    s = np.zeros((a.shape[0] + 1, a.shape[1] + 1), dtype=np.float64)
    s[1:, 1:] = a.cumsum(0).cumsum(1)
    return s


def box_sums(s, h, w):
    """Sum of every h x w window; result[y, x] is the window whose top-left is (y, x)."""
    return s[h:, w:] - s[:-h, w:] - s[h:, :-w] + s[:-h, :-w]


def moving_mean(a, k):
    """Centered moving average of a 1D array with window k, shrunk at the ends."""
    c = np.concatenate(([0.0], np.cumsum(a, dtype=np.float64)))
    idx = np.arange(len(a))
    lo = np.clip(idx - k // 2, 0, len(a))
    hi = np.clip(idx - k // 2 + k, 0, len(a))
    return (c[hi] - c[lo]) / np.maximum(hi - lo, 1)


def iou(a, b):  # (x, y, w, h)
    ix = max(0, min(a[0] + a[2], b[0] + b[2]) - max(a[0], b[0]))
    iy = max(0, min(a[1] + a[3], b[1] + b[3]) - max(a[1], b[1]))
    inter = ix * iy
    union = a[2] * a[3] + b[2] * b[3] - inter
    return inter / union if union > 0 else 0.0


def nms(scored, thr):
    """scored: [(score, bbox)]. Keep the best box of each overlapping group."""
    kept = []
    for score, box in sorted(scored, key=lambda t: t[0], reverse=True):
        if all(iou(box, k) < thr for _, k in kept):
            kept.append((score, box))
    return kept


def grow_box(edge, box):
    """Grow a box left/right, then up/down, while the edge profile stays dense.

    The best window often covers only the middle characters; this extends it to
    the whole plate (at most 2.5x wider and 2x taller).
    """
    H, W = edge.shape
    x, y, w, h = box
    col = moving_mean(edge[y:y + h].mean(0), max(3, h // 2))
    t = GROW_FRAC * col[x:x + w].mean()
    x0, x1 = x, x + w
    while x0 > 0 and col[x0 - 1] > t and x1 - x0 < 2.5 * w:
        x0 -= 1
    while x1 < W and col[x1] > t and x1 - x0 < 2.5 * w:
        x1 += 1
    row = moving_mean(edge[:, x0:x1].mean(1), 3)
    t = GROW_FRAC * row[y:y + h].mean()
    y0, y1 = y, y + h
    while y0 > 0 and row[y0 - 1] > t and y1 - y0 < 2 * h:
        y0 -= 1
    while y1 < H and row[y1] > t and y1 - y0 < 2 * h:
        y1 += 1
    return (x0, y0, x1 - x0, y1 - y0)


def search_region(gray, widths):
    """Best window for every (width, aspect) in one gray region.

    Returns [(score, (x, y, w, h))] in region coordinates.
    """
    edge = vertical_edges(gray)
    H, W = edge.shape
    sizes = []
    for w in widths:
        for a in ASPECTS:
            h = round(w / a)
            if MIN_W <= w <= W and MIN_H <= h <= H:
                sizes.append((h, w, max(1, h // 2), max(1, w // 4)))  # ring: h/2 above/below, w/4 left/right
    if not sizes:
        return []
    py, px = max(s[2] for s in sizes), max(s[3] for s in sizes)
    se = integral(np.pad(edge, ((py, py), (px, px))))  # no edges outside the region
    g = gray.astype(np.float32)
    sg = integral(np.pad(g, ((py, py), (px, px)), mode="edge"))
    e_norm, g_norm = edge.mean() + 1e-6, g.std() + 1e-6  # make the two terms comparable

    def center_surround(s, h, w, ry, rx, ny, nx):
        inner = box_sums(s, h, w)[py:py + ny, px:px + nx]
        outer = box_sums(s, h + 2 * ry, w + 2 * rx)[py - ry:py - ry + ny, px - rx:px - rx + nx]
        ring_area = (h + 2 * ry) * (w + 2 * rx) - h * w
        return inner / (h * w) - (outer - inner) / ring_area

    found = []
    for h, w, ry, rx in sizes:
        ny, nx = H - h + 1, W - w + 1
        score = (center_surround(se, h, w, ry, rx, ny, nx) / e_norm
                 + BRIGHT_W * center_surround(sg, h, w, ry, rx, ny, nx) / g_norm)
        y, x = np.unravel_index(np.argmax(score), score.shape)
        found.append((float(score[y, x]), grow_box(edge, (int(x), int(y), w, h))))
    return found


def detect_plate_candidates(img, vehicles) -> list[tuple]:
    """Find plate-like regions, searching the lower part of each vehicle box.

    Args:
        img: np.ndarray, uint8, shape (H, W, 3), BGR.
        vehicles: detect_vehicles output. If empty, the whole frame is searched.

    Returns:
        List of bbox (x, y, w, h) in frame coordinates: up to TOP_K per vehicle,
        best first, vehicles in the given order.
    """
    validate_frame(img)
    gray = to_gray(img)
    fh, fw = gray.shape
    if vehicles:
        regions = []
        for v in vehicles:
            x, y, w, h = v["bbox"]
            x0, x1 = max(0, round(x - MARGIN_X * w)), min(fw, round(x + w + MARGIN_X * w))
            y0, y1 = max(0, round(y + SEARCH_TOP * h)), min(fh, round(y + h + MARGIN_BOTTOM * h))
            regions.append((x0, y0, x1, y1, [round(f * w) for f in WIDTH_FRACS]))
    else:
        regions = [(0, 0, fw, fh, [round(f * fw) for f in FRAME_WIDTH_FRACS])]

    candidates = []
    for x0, y0, x1, y1, widths in regions:
        found = search_region(gray[y0:y1, x0:x1], widths)
        for _, (x, y, w, h) in nms(found, NMS_IOU)[:TOP_K]:
            box = (x + x0, y + y0, w, h)
            if all(iou(box, c) < NMS_IOU for c in candidates):  # drop repeats from overlapping vehicles
                candidates.append(box)
    return candidates
