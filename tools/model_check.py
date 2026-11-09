"""Compare pretrained vehicle detector and Korean OCR on plate samples (C-01).

Sample folder layout (keep it outside the repo, do not commit images):
    <samples>/full/        full images with vehicles
    <samples>/crops/       hand-cropped plates
    <samples>/labels.csv   columns: file,text  (plate text of each crop, e.g. 12가3456)

Usage:
    python tools/model_check.py <samples> [--yolo yolov8n.pt] [--ocr easyocr paddleocr]

Writes <samples>/out/vehicles.csv, <samples>/out/ocr.csv and annotated vehicle images.
"""

import argparse
import csv
import re
import time
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

import cv2
import numpy as np

try:  # use the OS cert store for weight downloads (antivirus HTTPS scanning breaks certifi)
    import truststore

    truststore.inject_into_ssl()
except ImportError:
    pass

ROOT = Path(__file__).resolve().parents[1]
VEHICLE_CLASSES = {2: "car", 3: "motorcycle", 5: "bus", 7: "truck"}  # COCO class ids
PLATE_RE = re.compile(r"^([가-힣]{2})?\d{2,3}[가-힣]\d{4}$")
DIGIT_FIX = str.maketrans({"O": "0", "o": "0", "I": "1", "l": "1"})
IMG_EXTS = {".jpg", ".jpeg", ".png", ".bmp"}


def imread(path):  # cv2.imread fails on non-ASCII paths on Windows
    return cv2.imdecode(np.fromfile(str(path), np.uint8), cv2.IMREAD_COLOR)


def imwrite(path, img):
    cv2.imencode(path.suffix, img)[1].tofile(str(path))


def list_images(folder):
    if not folder.is_dir():
        return []
    return sorted(p for p in folder.iterdir() if p.suffix.lower() in IMG_EXTS)


def write_csv(path, rows):
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def read_labels(path):
    for enc in ("utf-8-sig", "cp949"):  # Excel on Korean Windows saves cp949
        try:
            with open(path, newline="", encoding=enc) as f:
                return {row["file"].strip(): normalize(row["text"]) for row in csv.DictReader(f)}
        except UnicodeDecodeError:
            continue
    raise ValueError(f"cannot decode {path}")


def normalize(text):
    """Fix O/I misread as digits, then keep only digits and Hangul."""
    return re.sub(r"[^0-9가-힣]", "", text.translate(DIGIT_FIX))


def edit_distance(a, b):
    d = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        prev, d[0] = d[0], i
        for j, cb in enumerate(b, 1):
            prev, d[j] = d[j], min(d[j] + 1, d[j - 1] + 1, prev + (ca != cb))
    return d[len(b)]


def char_accuracy(pred, label):
    return max(0.0, 1 - edit_distance(pred, label) / len(label)) if label else 0.0


def join_lines(items):
    """Join OCR boxes top-to-bottom, left-to-right (two-line plates). Returns (text, mean conf)."""
    if not items:
        return "", 0.0
    boxes = []
    for box, text, conf in items:
        pts = np.asarray(box, dtype=float).reshape(-1, 2)
        boxes.append((pts[:, 1].mean(), pts[:, 0].min(), np.ptp(pts[:, 1]), text, float(conf)))
    boxes.sort()
    lines, line = [], [boxes[0]]
    for b in boxes[1:]:
        if abs(b[0] - line[-1][0]) < 0.5 * max(b[2], line[-1][2]):
            line.append(b)
        else:
            lines.append(line)
            line = [b]
    lines.append(line)
    text = "".join(b[3] for ln in lines for b in sorted(ln, key=lambda b: b[1]))
    return text, float(np.mean([b[4] for b in boxes]))


class EasyOCREngine:
    name = "easyocr"

    def __init__(self):
        import easyocr

        self.reader = easyocr.Reader(["ko"], gpu=False, verbose=False)

    def read(self, img):
        return self.reader.readtext(img)  # [(box, text, conf)]


class PaddleOCREngine:
    name = "paddleocr"

    def __init__(self):
        from paddleocr import PaddleOCR

        self.ocr = PaddleOCR(
            lang="korean",
            use_doc_orientation_classify=False,
            use_doc_unwarping=False,
            use_textline_orientation=False,
            enable_mkldnn=False,  # paddlepaddle 3.3 CPU + oneDNN fails with NotImplementedError
        )

    def read(self, img):
        res = self.ocr.predict(img)[0]
        return list(zip(res["rec_polys"], res["rec_texts"], res["rec_scores"]))


ENGINES = {"easyocr": EasyOCREngine, "paddleocr": PaddleOCREngine}


def check_vehicles(images, weights, out_dir):
    from ultralytics import YOLO

    model = YOLO(str(weights))
    model.predict(imread(images[0]), verbose=False)  # warm-up
    rows = []
    for path in images:
        img = imread(path)
        t = time.perf_counter()
        r = model.predict(img, conf=0.4, classes=list(VEHICLE_CLASSES), verbose=False)[0]
        ms = (time.perf_counter() - t) * 1000
        names = [VEHICLE_CLASSES[int(c)] for c in r.boxes.cls]
        imwrite(out_dir / f"vehicles_{path.stem}.jpg", r.plot())
        rows.append({"file": path.name, "vehicles": len(names), "classes": " ".join(names), "ms": round(ms, 1)})
    return rows


def check_ocr(engine, crops, labels):
    engine.read(imread(crops[0]))  # warm-up
    rows = []
    for path in crops:
        label = labels.get(path.name, "")
        img = imread(path)
        t = time.perf_counter()
        raw, conf = join_lines(engine.read(img))
        ms = (time.perf_counter() - t) * 1000
        text = normalize(raw)
        rows.append({
            "model": engine.name,
            "file": path.name,
            "label": label,
            "raw": raw,
            "text": text,
            "conf": round(conf, 3),
            "exact": int(bool(label) and text == label),
            "char_acc": round(char_accuracy(text, label), 3),
            "format_ok": int(bool(PLATE_RE.match(text))),
            "ms": round(ms, 1),
        })
    return rows


def pkg_version(name):
    try:
        return version(name)
    except PackageNotFoundError:
        return "not installed"


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("samples", type=Path, help="sample folder with full/, crops/, labels.csv")
    ap.add_argument("--yolo", default="yolov8n.pt", help="YOLO weights name, saved under weights/")
    ap.add_argument("--ocr", nargs="+", default=list(ENGINES), choices=list(ENGINES))
    args = ap.parse_args()

    out_dir = args.samples / "out"
    out_dir.mkdir(parents=True, exist_ok=True)
    for pkg in ("ultralytics", "torch", "easyocr", "paddleocr", "paddlepaddle"):
        print(f"{pkg}: {pkg_version(pkg)}")

    full = list_images(args.samples / "full")
    if full:
        rows = check_vehicles(full, ROOT / "weights" / args.yolo, out_dir)
        write_csv(out_dir / "vehicles.csv", rows)
        found = sum(r["vehicles"] > 0 for r in rows)
        ms = np.mean([r["ms"] for r in rows])
        print(f"\n[vehicles] {args.yolo}: found in {found}/{len(rows)} images, {ms:.0f} ms/img")

    crops = list_images(args.samples / "crops")
    if crops:
        labels = read_labels(args.samples / "labels.csv")
        missing = [p.name for p in crops if p.name not in labels]
        if missing:
            print(f"\nwarning: no label for {missing}")
        rows = []
        print(f"\n[ocr] {'model':<10} {'read':>6} {'char_acc':>9} {'format_ok':>10} {'conf':>6} {'ms':>6}")
        for name in args.ocr:
            r = check_ocr(ENGINES[name](), crops, labels)
            rows += r
            n = len(r)
            print(
                f"      {name:<10} {sum(x['exact'] for x in r):>3}/{n:<2} "
                f"{np.mean([x['char_acc'] for x in r]):>9.2f} "
                f"{sum(x['format_ok'] for x in r):>7}/{n:<2} "
                f"{np.mean([x['conf'] for x in r]):>6.2f} {np.mean([x['ms'] for x in r]):>6.0f}"
            )
        write_csv(out_dir / "ocr.csv", rows)

    if not full and not crops:
        print(f"no images in {args.samples / 'full'} or {args.samples / 'crops'}")
    else:
        print(f"\nresults: {out_dir}")


if __name__ == "__main__":
    main()
