"""Label drafts and check images for labeling (ALL-02) and label review (ALL-03).

draft  Fill the untouched entries of B's label template (python -m tools.b_labels init)
       with vehicle boxes (YOLO) and plate boxes (detect_plates). Plate status and
       text stay empty: the labeler reads each plate, and B's validator rejects the
       frame until every status is set. An entry someone already edited is never changed.
check  Draw the boxes of the annotation file on a copy of each frame, with their list
       index (V0, P0), so boxes and texts can be checked by eye.

Check images show real plates. They go to data/annotations/check/, which git ignores.

Usage:
    python tools/label_draft.py draft [--annotations FILE] [--frames DIR] [--check DIR]
    python tools/label_draft.py check [--annotations FILE] [--frames DIR] [--check DIR] [--only FRAME ...]
"""

import argparse
import json
import os
import sys
import tempfile
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.plate.imgutil import load_png, save_png  # noqa: E402

ANNOTATIONS = ROOT / "data" / "annotations" / "scenes.json"
FRAMES = ROOT / "data" / "frames" / "orig"
CHECK = ROOT / "data" / "annotations" / "check"
COLORS = {"vehicle": (60, 140, 255), "readable": (40, 200, 80), "unreadable": (255, 190, 0),
          None: (255, 40, 40)}  # RGB; None = plate status still to fill
FONTS = [Path(r"C:\Windows\Fonts\malgun.ttf"), Path("/System/Library/Fonts/AppleSDGothicNeo.ttc"),
         Path("/usr/share/fonts/truetype/nanum/NanumGothic.ttf")]  # Hangul plate text
NEXT_STEPS = """Next, for every frame:
  - open its check image; fix or delete wrong boxes and add plates and vehicles the draft missed
  - set each plate's status (readable / unreadable) and text (null when unreadable)
  - fill annotator and set annotation_status to complete
Then redraw with `python tools/label_draft.py check` and export with `python -m tools.b_labels export`."""


def detect(frame):
    """(vehicles, plates) label entries from the C pipeline; plate status and text left empty."""
    from src.plate.detect import detect_plates, detect_vehicles  # heavy, loaded only when drafting

    vehicles = detect_vehicles(frame)
    with tempfile.TemporaryDirectory() as tmp:  # detect_plates saves crops; a draft does not need them
        plates = detect_plates(frame, results_dir=tmp)
    return ([{"bbox": v["bbox"], "class": v["cls"]} for v in vehicles],
            [{"bbox": p["bbox"], "status": None, "text": None} for p in plates])


def fit(box, width, height):
    """Box clipped to the frame as four ints [x, y, w, h], or None if nothing is left."""
    x0, y0 = max(0, int(box[0])), max(0, int(box[1]))
    x1, y1 = min(width, int(box[0]) + int(box[2])), min(height, int(box[1]) + int(box[3]))
    return [x0, y0, x1 - x0, y1 - y0] if x1 > x0 and y1 > y0 else None


def untouched(entry):
    """True for a template entry nobody has edited yet."""
    return entry.get("annotation_status") == "pending" and not entry.get("vehicles") and not entry.get("plates")


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def write_json(path, data):
    """Replace the file in one step, so an interrupted run never leaves half a file."""
    path = Path(path)
    handle, tmp = tempfile.mkstemp(prefix=".draft-", suffix=".json", dir=path.parent)
    try:
        with os.fdopen(handle, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        os.replace(tmp, path)
    finally:
        Path(tmp).unlink(missing_ok=True)


def draft(annotations=ANNOTATIONS, frames=FRAMES, check=CHECK, detector=None):
    """Draft every untouched entry and draw its check image. Returns the drafted frame names.

    The file is read again before each write and only a still untouched entry is filled,
    so edits made while the draft runs are kept.
    """
    annotations, frames = Path(annotations), Path(frames)
    detector = detector or detect
    start = read_json(annotations)
    todo = [name for name, entry in start.items() if untouched(entry)]
    for n, name in enumerate(todo, 1):
        frame = load_png(frames / name)
        h, w = frame.shape[:2]
        if (start[name].get("height"), start[name].get("width")) != (h, w):
            raise ValueError(f"{name}: frame is {w}x{h}, annotation says "
                             f"{start[name].get('width')}x{start[name].get('height')}")
        vehicles, plates = detector(frame)
        vehicles = [{**v, "bbox": b} for v in vehicles if (b := fit(v["bbox"], w, h))]
        plates = [{**p, "bbox": b} for p in plates if (b := fit(p["bbox"], w, h))]
        data = read_json(annotations)
        entry = data[name]
        if untouched(entry):
            entry.update(vehicles=vehicles, plates=plates)
            write_json(annotations, data)
        if check:
            save_png(Path(check) / name, draw(frame, entry))
        print(f"[{n}/{len(todo)}] {name}: {len(vehicles)} vehicles, {len(plates)} plates")
    return todo


def check_images(annotations=ANNOTATIONS, frames=FRAMES, check=CHECK, only=None):
    """Draw the current boxes of every frame (or only those named). Returns the image paths."""
    data = read_json(annotations)
    paths = []
    for name in only or data:
        path = Path(check) / name
        save_png(path, draw(load_png(Path(frames) / name), data[name]))
        paths.append(path)
    return paths


def font(size):
    for path in FONTS:
        if path.exists():
            return ImageFont.truetype(str(path), size)
    return ImageFont.load_default(size)  # Hangul may show as boxes


def draw(frame, entry):
    """Copy of a BGR frame with the entry's vehicle and plate boxes, labeled V0.. and P0.."""
    img = Image.fromarray(np.ascontiguousarray(frame[..., ::-1]))
    d = ImageDraw.Draw(img)
    f = font(max(12, frame.shape[0] // 54))  # 20 px on a 1080p frame
    width = max(1, frame.shape[0] // 540)
    items = [(v["bbox"], COLORS["vehicle"], f"V{i} {v.get('class', '')}") for i, v in enumerate(entry.get("vehicles", []))]
    for i, p in enumerate(entry.get("plates", [])):
        status = p.get("status")
        items.append((p["bbox"], COLORS.get(status, COLORS[None]), f"P{i} {p.get('text') or status or 'status?'}"))
    for (x, y, w, h), color, label in items:
        d.rectangle([x, y, x + w - 1, y + h - 1], outline=color, width=width)
        left, top, right, bottom = d.textbbox((0, 0), label, font=f)
        ty = y - (bottom - top) - 4 if y - (bottom - top) - 4 >= 0 else y + h + 2
        d.rectangle([x, ty, x + right - left + 4, ty + bottom - top + 4], fill=color)
        d.text((x + 2 - left, ty + 2 - top), label, fill=(0, 0, 0), font=f)
    return np.asarray(img)[..., ::-1].copy()


def main():
    ap = argparse.ArgumentParser(description="Label drafts and check images.")
    sub = ap.add_subparsers(dest="command", required=True)
    for name in ("draft", "check"):
        p = sub.add_parser(name)
        p.add_argument("--annotations", type=Path, default=ANNOTATIONS)
        p.add_argument("--frames", type=Path, default=FRAMES)
        p.add_argument("--check", type=Path, default=CHECK, help="folder for the check images")
        if name == "check":
            p.add_argument("--only", nargs="+", help="frame file names to draw (default: all)")
    args = ap.parse_args()
    if args.command == "draft":
        done = draft(args.annotations, args.frames, args.check)
        print(f"drafted {len(done)} frames; check images in {args.check}\n{NEXT_STEPS}")
    else:
        paths = check_images(args.annotations, args.frames, args.check, args.only)
        print(f"drew {len(paths)} check images in {args.check}")


if __name__ == "__main__":
    main()
