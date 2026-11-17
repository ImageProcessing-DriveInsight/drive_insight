"""Plate size and degradation check: how small and how degraded can a plate be and still be read?

Each sample is shrunk so its plate is W px wide (area averaging, like a camera
farther away), degraded, JPEG-compressed like a video frame, then read. A sample
whose plate is narrower than W is left out of that width (never upscaled):

  crop   hand crops -> read_plate (preprocess -> OCR -> judge): reading only.
  frame  full photos pasted on a 1920x1080 frame -> detect_plates (vehicle ->
         plate candidates -> read). Also runs A's gamma and hist_eq on the fog
         and low-light frames.

Degradations (NumPy, seeded): clean, fog (I = J t + A (1 - t)), low light
(I = J k + sensor noise), blur (horizontal motion blur).

Uses the sample folder of tools/model_check.py (full/, crops/, labels.csv).
Writes <out>/size_<test>.csv (one row per image and variant, with plate text)
and <out>/size_<test>_summary.csv (counts only), and prints the summary.

Usage:
    python tools/plate_size_check.py <samples> [--test crop frame] [--widths 120 80 40] [--out DIR]
"""

import argparse
import csv
import sys
import time
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.dip import gamma, hist_eq  # noqa: E402
from src.eval.ocr import char_accuracy  # noqa: E402
from src.plate.detect import STATUS_RANK, detect_plates, detect_vehicles, read_plate  # noqa: E402
from src.plate.imgutil import load_png  # noqa: E402
from src.plate.judge import PLATE_RE  # noqa: E402

WIDTHS = (120, 100, 80, 60, 50, 40, 30, 25, 20)  # target plate width in px
WIDTH_TOL = 0.95  # a sample counts for width W only if its plate is at least WIDTH_TOL * W wide (no upscaling)
FRAME_SIZE = (1080, 1920)  # (H, W) of a dashcam frame
FILL = 114  # gray around the pasted photo
JPEG_QUALITY = 75
FOG_T, FOG_AIRLIGHT = 0.4, 220.0  # plate contrast drops to 40 %, toward light gray
DARK_K, DARK_NOISE = 0.2, 3.0  # 20 % exposure, noise std in gray levels
BLUR_LEN = 5  # motion blur length in frame px
SEED = 0

ROW_COLUMNS = ["test", "image", "variant", "width", "plate_w", "vehicles", "label", "text", "status", "conf",
               "char_acc", "exact", "ms"]
SUMMARY_COLUMNS = ["test", "variant", "width", "n", "exact", "char_acc", "readable", "readable_wrong", "uncertain",
                   "unreadable", "missed", "vehicles_found"]


def to_u8(a):
    return np.clip(np.rint(a), 0, 255).astype(np.uint8)


def area_weights(n_in, n_out):
    """(n_out, n_in) matrix: each output pixel is the mean of the input pixels it covers."""
    edges = np.arange(n_out + 1) * (n_in / n_out)
    j = np.arange(n_in)
    overlap = np.clip(np.minimum(edges[1:, None], j + 1) - np.maximum(edges[:-1, None], j), 0, None)
    return overlap / overlap.sum(1, keepdims=True)


def shrink(img, scale):
    """Area-average downscale of a gray or color image; scale >= 1 returns a copy."""
    if scale >= 1:
        return img.copy()
    h, w = img.shape[:2]
    wy = area_weights(h, max(1, round(h * scale)))
    wx = area_weights(w, max(1, round(w * scale)))
    out = np.tensordot(wy, img.astype(np.float64), axes=(1, 0))  # (h', w[, c])
    out = np.tensordot(out, wx, axes=(1, 1))  # (h'[, c], w')
    return to_u8(np.moveaxis(out, -1, 1))


def fog(img, t=FOG_T, airlight=FOG_AIRLIGHT):
    """Haze model I = J t + A (1 - t), one transmission t for the whole image."""
    return to_u8(img * t + airlight * (1 - t))


def low_light(img, k=DARK_K, noise=DARK_NOISE, rng=None):
    """Underexposure I = J k plus Gaussian sensor noise."""
    rng = rng if rng is not None else np.random.default_rng(SEED)
    return to_u8(img * k + rng.normal(0.0, noise, img.shape))


def motion_blur(img, length=BLUR_LEN):
    """Horizontal motion blur: mean of `length` neighboring pixels, edge padded."""
    if length <= 1:
        return img.copy()
    left = (length - 1) // 2
    pad = [(0, 0), (left, length - 1 - left)] + [(0, 0)] * (img.ndim - 2)
    c = np.cumsum(np.pad(img.astype(np.float64), pad, mode="edge"), axis=1)
    c = np.concatenate([np.zeros_like(c[:, :1]), c], axis=1)
    return to_u8((c[:, length:] - c[:, :-length]) / length)


def jpeg(img, quality=JPEG_QUALITY):
    """Encode and decode as JPEG, like a compressed video frame."""
    ok, buf = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, quality])
    if not ok:
        raise ValueError("cannot encode JPEG")
    return cv2.imdecode(buf, cv2.IMREAD_UNCHANGED)


DEGRADATIONS = {
    "clean": lambda img, rng: img,
    "fog": lambda img, rng: fog(img),
    "low_light": lambda img, rng: low_light(img, rng=rng),
    "blur": lambda img, rng: motion_blur(img),
}
ENHANCED = {  # frame test only: A's merged ops on a degraded frame (a preview, not A's fixed pipeline)
    "fog+hist_eq": ("fog", hist_eq),
    "low_light+gamma+hist_eq": ("low_light", lambda img: hist_eq(gamma(img, 0.5))),
}


def center_box(shape, size=FRAME_SIZE):
    """(y, x, h, w) of an image of this shape placed in the middle of an (H, W) frame."""
    H, W = size
    h, w = min(shape[0], H), min(shape[1], W)
    return (H - h) // 2, (W - w) // 2, h, w


def paste_center(img, size=FRAME_SIZE, fill=FILL):
    """Put img in the middle of an (H, W) frame, cutting its borders if it is larger."""
    y, x, h, w = center_box(img.shape, size)
    frame = np.full((*size, 3), fill, np.uint8)
    sy, sx = (img.shape[0] - h) // 2, (img.shape[1] - w) // 2
    frame[y:y + h, x:x + w] = img[sy:sy + h, sx:sx + w]
    return frame


def best_read(plates, label):
    """The returned plate closest to the label: (text, status, conf, char_acc), status 'missed' if none."""
    if not plates:
        return None, "missed", 0.0, 0.0
    p = max(plates, key=lambda p: (char_accuracy(p["text"], label), STATUS_RANK[p["status"]]))
    return p["text"], p["status"], p["conf"], char_accuracy(p["text"], label)


def read_labels(path):
    for enc in ("utf-8-sig", "cp949"):  # Excel on Korean Windows saves cp949
        try:
            with open(path, encoding=enc, newline="") as f:
                return {Path(r["file"].strip()).stem: r["text"].strip() for r in csv.DictReader(f)}
        except UnicodeDecodeError:
            continue
    raise ValueError(f"cannot decode {path}")


def real_plates(labels):
    """Split labels into real plates and the names of the rest (e.g. carmaker advertising plates).

    judge never reads a non-plate Hangul as readable, so such samples could never be exact.
    """
    kept = {k: v for k, v in labels.items() if PLATE_RE.match(v)}
    return kept, sorted(set(labels) - set(kept))


def list_images(folder):
    return sorted(p for p in Path(folder).iterdir() if p.suffix.lower() in {".png", ".jpg", ".jpeg"})


def make_row(test, image, variant, width, plate_w, vehicles, label, read, ms):
    text, status, conf, acc = read
    return {"test": test, "image": image, "variant": variant, "width": width, "plate_w": plate_w,
            "vehicles": vehicles, "label": label, "text": text, "status": status, "conf": conf,
            "char_acc": acc, "exact": text == label, "ms": ms}


def crop_test(samples, labels, widths, only=None):
    """OCR only: shrink each hand crop to the plate width, degrade, read. only: variant names to run."""
    rows = []
    for i, path in enumerate(list_images(samples / "crops")):  # i keeps the noise seeds when samples are skipped
        if path.stem not in labels:
            continue
        crop, label = load_png(path), labels[path.stem]
        for width in widths:
            if crop.shape[1] < WIDTH_TOL * width:
                continue
            small = shrink(crop, width / crop.shape[1])
            for d, (variant, degrade) in enumerate(DEGRADATIONS.items()):
                if only and variant not in only:
                    continue
                img = jpeg(degrade(small, np.random.default_rng([SEED, i, width, d])))
                t = time.perf_counter()
                status, text, conf = read_plate(img)
                ms = (time.perf_counter() - t) * 1000
                read = (text, status, conf, char_accuracy(text, label))
                rows.append(make_row("crop", path.stem, variant, width, small.shape[1], None, label, read, ms))
        print(f"crop {path.stem} done", file=sys.stderr, flush=True)
    return rows


def frame_test(samples, labels, widths, out, only=None):
    """Full pipeline: shrink the photo so its plate is `width` px, paste on a frame, degrade, detect and read.

    only: variant names to run. A's ops see only the photo: the flat border would dominate the histogram.
    """
    rows, crops = [], out / "size_frame"
    for i, path in enumerate(list_images(samples / "full")):
        if path.stem not in labels:
            continue
        photo, label = load_png(path), labels[path.stem]
        ref = detect_plates(photo, cond="ref", frame_id=path.stem, results_dir=crops)
        if not ref:
            print(f"frame {path.stem}: no plate in the full photo, skipped", file=sys.stderr)
            continue
        native = max(ref, key=lambda p: char_accuracy(p["text"], label))["bbox"][2]  # plate width in the photo
        variants = {**{v: (v, None) for v in DEGRADATIONS}, **ENHANCED}
        for width in widths:
            if native < WIDTH_TOL * width:
                continue
            scale = min(1.0, width / native)
            small = shrink(photo, scale)
            canvas, (y, x, h, w) = paste_center(small), center_box(small.shape)
            for variant, (base, enhance) in variants.items():
                if only and variant not in only:
                    continue
                rng = np.random.default_rng([SEED, i, width, list(DEGRADATIONS).index(base)])
                frame = jpeg(DEGRADATIONS[base](canvas, rng))  # enhanced variants reuse the same degraded frame
                if enhance:
                    frame[y:y + h, x:x + w] = enhance(frame[y:y + h, x:x + w])
                t = time.perf_counter()
                vehicles = len(detect_vehicles(frame))
                plates = detect_plates(frame, cond=variant, frame_id=f"{path.stem}_{width}", results_dir=crops)
                ms = (time.perf_counter() - t) * 1000
                rows.append(make_row("frame", path.stem, variant, width, round(native * scale), vehicles, label,
                                     best_read(plates, label), ms))
        print(f"frame {path.stem} done (plate {native} px in the photo)", file=sys.stderr, flush=True)
    return rows


def summarize(rows):
    """One row per (test, variant, width), in first-seen order."""
    groups = {}
    for r in rows:
        groups.setdefault((r["test"], r["variant"], r["width"]), []).append(r)
    out = []
    for (test, variant, width), g in groups.items():
        status = [r["status"] for r in g]
        out.append({
            "test": test, "variant": variant, "width": width, "n": len(g),
            "exact": sum(r["exact"] for r in g),
            "char_acc": sum(r["char_acc"] for r in g) / len(g),
            "readable": status.count("readable"),
            "readable_wrong": sum(r["status"] == "readable" and not r["exact"] for r in g),
            "uncertain": status.count("uncertain"),
            "unreadable": status.count("unreadable"),
            "missed": status.count("missed"),
            "vehicles_found": sum(r["vehicles"] > 0 for r in g) if test == "frame" else None,
        })
    return out


def write_rows(path, columns, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=columns)
        writer.writeheader()
        for r in rows:
            writer.writerow({k: "" if r[k] is None else round(r[k], 4) if isinstance(r[k], float) else r[k]
                             for k in columns})
    return path


def load_rows(path):
    """Read back a size_<test>.csv written by write_rows."""
    with open(path, encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    for r in rows:
        r["width"], r["char_acc"], r["exact"] = int(r["width"]), float(r["char_acc"]), r["exact"] == "True"
        r["vehicles"] = int(r["vehicles"]) if r["vehicles"] else None
    return rows


TABLES = {
    "exact / n, [readable but wrong]":
        lambda s: f"{s['exact']}/{s['n']}" + (f" [{s['readable_wrong']}]" if s["readable_wrong"] else ""),
    "mean char accuracy": lambda s: f"{s['char_acc']:.2f}",
    "readable / uncertain / unreadable or missed":
        lambda s: f"{s['readable']}/{s['uncertain']}/{s['unreadable'] + s['missed']}",
    "frames with a vehicle found": lambda s: f"{s['vehicles_found']}/{s['n']}",
}


def print_tables(summary, widths):
    """Markdown tables per test: one row per variant, one column per plate width."""
    for test in dict.fromkeys(s["test"] for s in summary):
        cells = {(s["variant"], s["width"]): s for s in summary if s["test"] == test}
        variants = list(dict.fromkeys(v for v, _ in cells))
        for title, fmt in TABLES.items():
            if title.startswith("frames") and test != "frame":
                continue
            print(f"\n{test}: {title}")
            print("| variant | " + " | ".join(f"{w} px" for w in widths) + " |")
            print("| --- |" + " --- |" * len(widths))
            for v in variants:
                print(f"| {v} | " + " | ".join(fmt(cells[(v, w)]) if (v, w) in cells else "" for w in widths) + " |")


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("samples", type=Path, help="sample folder with full/, crops/ and labels.csv")
    ap.add_argument("--test", nargs="+", choices=["crop", "frame"], default=["crop", "frame"])
    ap.add_argument("--widths", nargs="+", type=int, default=list(WIDTHS))
    ap.add_argument("--out", type=Path, help="output folder, default <samples>/out")
    ap.add_argument("--variants", nargs="+", help="run only these variants, e.g. clean fog+hist_eq")
    ap.add_argument("--reuse", action="store_true", help="print the tables from size_<test>.csv without reading again")
    args = ap.parse_args()
    out = args.out or args.samples / "out"
    labels, skipped = real_plates(read_labels(args.samples / "labels.csv"))
    if skipped:
        print(f"skipped {len(skipped)} samples whose label is not a real plate: {', '.join(skipped)}", file=sys.stderr)

    summary = []
    for test in args.test:
        if args.reuse:
            rows = load_rows(out / f"size_{test}.csv")
        else:
            rows = crop_test(args.samples, labels, args.widths, args.variants) if test == "crop" else \
                frame_test(args.samples, labels, args.widths, out, args.variants)
            write_rows(out / f"size_{test}.csv", ROW_COLUMNS, rows)
            write_rows(out / f"size_{test}_summary.csv", SUMMARY_COLUMNS, summarize(rows))
        summary += summarize(rows)
    print_tables(summary, args.widths)


if __name__ == "__main__":
    main()
