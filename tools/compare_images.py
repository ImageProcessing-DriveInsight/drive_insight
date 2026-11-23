"""Comparison images for slides (C-11): the same plates and frames in orig, fixed and adaptive.

Plate lists, one row per labeled plate: its label, then the plate area in each condition with
what OCR read there, the char accuracy and the status, colored green (exact), orange (partly
right) or red (wrong or missed). A read judged readable but not the labeled text says
"readable, wrong" and is red, since it is the worst case: a confident wrong answer.
    better.png          plates read better in fixed or adaptive than in orig, largest gain first
    worse.png           plates read worse in fixed or adaptive than in orig, largest loss first
    better_vs_fixed.png plates read better in adaptive than in fixed (when both exist)
    worse_vs_fixed.png  plates read worse in adaptive than in fixed
Frame images, frames/<frame>.png: the whole frame in each condition side by side, with the
labeled plate boxes in the same colors. Made for the frames in the lists, or for --frames
(a frame without a readable labeled plate is drawn without boxes).

When results/ocr/clear.csv exists (OCR on the clear frames of the synthetic fog clips, #79), a
clear column comes first, as a reference: what the plate looked like and read without fog. Frames
without a clear frame leave that column empty. The lists still compare only orig, fixed and adaptive.

The plate area is cut from each condition's frame at the label box, so every column shows the
same place, also where OCR missed the plate. Small plates are enlarged without smoothing, so the
real resolution shows.

Vehicle lists (#87), when the vehicle labels (--scenes) and results/vehicles/<cond>.json (#83)
exist: one row per labeled vehicle, its area in each condition with the labeled box in gray and
the detection box in green (found, IoU >= 0.5) or red (missed: the detection overlapping it
most, from IoU 0.1), widest vehicle first.
    vehicles_better.png          vehicles found in fixed or adaptive but not in orig
    vehicles_worse.png           vehicles found in orig but not in fixed or adaptive
    vehicles_better_vs_fixed.png vehicles found in adaptive but not in fixed
    vehicles_worse_vs_fixed.png  vehicles found in fixed but not in adaptive

Images show real plates. They go to results/figures/, which git ignores. --hide N covers the last
N characters of every labeled plate, in the images and the texts. Other plates in the frame
images and the vehicle lists are not covered.

Usage:
    python tools/compare_images.py [--results DIR] [--labels PATH] [--frames-dir DIR] [--out DIR]
                                   [--top N] [--hide N] [--frames FRAME ...] [--scenes PATH ...]
"""

import argparse
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.eval.ocr import frame_key, load_labels, plate_details  # noqa: E402
from src.eval.vehicles import SCENES, load_detections, load_vehicles, scenes_arg, vehicle_reads  # noqa: E402
from src.plate.imgutil import load_png  # noqa: E402
from tools.label_draft import font  # noqa: E402

CONDS = ("orig", "fixed", "adaptive")
REFERENCE = "clear"  # clear frames of the synthetic fog clips, shown first when read
RESULTS = ROOT / "results"
LABELS = ROOT / "data" / "labels"
FRAMES = ROOT / "data" / "frames"
MARGIN = 0.1  # share of the label box added on each side, like the OCR crops
PLATE_H = 80  # px, plate area height in the lists
CELL_W = 5 * PLATE_H  # px, widest plate area in the lists
LABEL_W = 260  # px, label column
PANEL_W = 640  # px, width of each condition in the frame images
VEHICLE_H = 140  # px, vehicle area height in the vehicle lists
VEHICLE_W = 2 * VEHICLE_H  # px, widest vehicle area in the vehicle lists
VEHICLE_MARGIN = 0.15  # share of the label box added on each side, so a loose detection box shows
PAD = 12
EPS = 1e-9
WHITE, INK, FAINT = (255, 255, 255), (20, 20, 20), (120, 120, 120)
GOOD, PART, BAD = (30, 150, 60), (220, 130, 0), (200, 40, 40)  # exact, partly right, wrong or missed
HIDDEN = (90, 90, 90)


def hide_text(text, n):
    """text with its last n characters as '*'."""
    if not text or n <= 0:
        return text
    return text[:max(0, len(text) - n)] + "*" * min(n, len(text))


def wrong_readable(plate):
    """True for a confident wrong read: judged readable, but not the labeled text."""
    return plate["status"] == "readable" and plate["char_acc"] < 1 - EPS


def color(plate):
    if plate is None:
        return FAINT
    acc = plate["char_acc"]
    if wrong_readable(plate):
        return BAD
    return GOOD if acc >= 1 - EPS else PART if acc > EPS else BAD


def read_of(plate, hide=0):
    """What OCR gave for a labeled plate: text, char accuracy and status."""
    if plate is None:
        return "no clear frame"
    acc = f"{plate['char_acc']:.2f}"
    if plate["status"] is None:
        return f"missed  {acc}"
    text = hide_text(plate["text"], hide)
    if not text:
        return f"{plate['status']}  {acc}"
    return f"{text}  {acc}  {'readable, wrong' if wrong_readable(plate) else plate['status']}"


def collect(results=RESULTS, labels=LABELS, conds=CONDS):
    """(conditions found, rows): one row per readable labeled plate read in every found condition.

    Row: {"frame", "label", "bbox", "reads": {condition: plate_details entry}}. orig and at least
    one other condition must have results/ocr/<cond>.csv. With ocr/clear.csv, the conditions start
    with clear and reads["clear"] is None for a frame without a clear frame.
    """
    gold = load_labels(labels)
    details = {}
    for cond in conds:
        path = Path(results) / "ocr" / f"{cond}.csv"
        if path.exists():
            details[cond] = plate_details(path, gold)
    if "orig" not in details or len(details) < 2:
        raise FileNotFoundError(f"need ocr/orig.csv and another condition in {results}")
    clear_path = Path(results) / "ocr" / f"{REFERENCE}.csv"
    clear = plate_details(clear_path, gold) if clear_path.exists() else None
    rows = []
    for frame, plates in details["orig"].items():
        if all(frame in d for d in details.values()):
            for i, p in enumerate(plates):
                reads = {c: d[frame][i] for c, d in details.items()}
                if clear is not None:
                    reads = {REFERENCE: clear[frame][i] if frame in clear else None, **reads}
                rows.append({"frame": frame, "label": p["label"], "bbox": p["label_bbox"], "reads": reads})
    return ([REFERENCE] if clear is not None else []) + list(details), rows


def later(conds, base):
    """The conditions after base in CONDS order, among conds (never the clear reference)."""
    return [c for c in conds if c in CONDS and CONDS.index(c) > CONDS.index(base)]


def change(row, base="orig"):
    """(best, worst) char accuracy change of the conditions after base against base."""
    ref = row["reads"][base]["char_acc"]
    others = [row["reads"][c]["char_acc"] - ref for c in later(row["reads"], base)]
    return max(others), min(others)


def pick(rows, top, base="orig"):
    """(better, worse) against base: at most top rows each, largest change first."""
    better = sorted((r for r in rows if change(r, base)[0] > EPS), key=lambda r: (-change(r, base)[0], r["frame"]))
    worse = sorted((r for r in rows if change(r, base)[1] < -EPS), key=lambda r: (change(r, base)[1], r["frame"]))
    return better[:top], worse[:top]


def load_frame(frames_dir, cond, frame):
    """RGB frame, or None if the file is missing."""
    path = Path(frames_dir) / cond / f"{frame}.png"
    return load_png(path)[..., ::-1].copy() if path.exists() else None


def cover(image, bbox, label, n):
    """Cover the last n characters of a plate in place: the right n/len(label) of its box."""
    if n <= 0 or not label:
        return image
    x, y, w, h = bbox
    cut = round(x + w * (1 - min(n, len(label)) / len(label)))
    image[max(0, y):max(0, y + h), max(0, cut):max(0, x + w)] = HIDDEN
    return image


def area_of(shape, bbox, margin=MARGIN):
    """(x0, y0, x1, y1): the box plus margin on each side, clipped to an image of this shape."""
    x, y, w, h = bbox
    mx, my = round(w * margin), round(h * margin)
    return max(0, x - mx), max(0, y - my), min(shape[1], x + w + mx), min(shape[0], y + h + my)


def plate_area(image, bbox):
    """The label box plus MARGIN on each side, clipped to the image."""
    x0, y0, x1, y1 = area_of(image.shape, bbox)
    return image[y0:y1, x0:x1]


def fit(area, height=PLATE_H, width=CELL_W):
    """PIL image of an RGB area scaled to the height (or the width, if wider). Enlarging keeps pixels square."""
    img = Image.fromarray(np.ascontiguousarray(area))
    scale = min(height / img.height, width / img.width)
    size = (max(1, round(img.width * scale)), max(1, round(img.height * scale)))
    return img.resize(size, Image.NEAREST if scale >= 1 else Image.LANCZOS)


def plate_list(rows, conds, frames_dir=FRAMES, hide=0):
    """One image for the rows: header, then label and plate area per condition."""
    big, small = font(26), font(18)
    row_h = PAD + PLATE_H + 34 + PAD
    sheet = Image.new("RGB", (LABEL_W + len(conds) * (CELL_W + PAD) + PAD, 48 + len(rows) * row_h), WHITE)
    d = ImageDraw.Draw(sheet)
    d.text((PAD, 10), "label", fill=INK, font=big)
    for j, cond in enumerate(conds):
        d.text((LABEL_W + j * (CELL_W + PAD), 10), cond, fill=INK, font=big)
    for i, row in enumerate(rows):
        top = 48 + i * row_h
        d.line([(0, top), (sheet.width, top)], fill=(220, 220, 220), width=1)
        d.text((PAD, top + PAD + 20), hide_text(row["label"], hide), fill=INK, font=big)
        d.text((PAD, top + PAD + 56), row["frame"], fill=FAINT, font=small)
        for j, cond in enumerate(conds):
            left, plate = LABEL_W + j * (CELL_W + PAD), row["reads"][cond]
            image = load_frame(frames_dir, cond, row["frame"])
            if image is None:
                d.text((left, top + PAD + 20), "no frame", fill=FAINT, font=small)
            else:
                sheet.paste(fit(plate_area(cover(image, row["bbox"], row["label"], hide), row["bbox"])),
                            (left, top + PAD))
            d.text((left, top + PAD + PLATE_H + 4), read_of(plate, hide), fill=color(plate), font=small)
    return sheet


def frame_image(frame, rows, conds, frames_dir=FRAMES, hide=0):
    """The frame in each condition side by side, its labeled plate boxes colored by that condition's read."""
    small = font(18)
    panels = []
    for cond in conds:
        image = load_frame(frames_dir, cond, frame)
        if image is None:
            panels.append((cond, None))
            continue
        for row in rows:
            cover(image, row["bbox"], row["label"], hide)
        panels.append((cond, image))
    height = max((round(img.shape[0] * PANEL_W / img.shape[1]) for _, img in panels if img is not None),
                 default=PANEL_W * 9 // 16)
    sheet = Image.new("RGB", (len(conds) * (PANEL_W + PAD) - PAD, 36 + height), WHITE)
    d = ImageDraw.Draw(sheet)
    for j, (cond, image) in enumerate(panels):
        left = j * (PANEL_W + PAD)
        d.text((left + 4, 6), cond, fill=INK, font=font(24))
        if image is None:
            d.text((left, 50), "no frame", fill=FAINT, font=small)
            continue
        scale = PANEL_W / image.shape[1]
        sheet.paste(fit(image, round(image.shape[0] * scale), PANEL_W), (left, 36))
        for row in rows:
            x, y, w, h = (round(v * scale) for v in row["bbox"])
            plate = row["reads"][cond]
            if plate is None:
                continue
            box = [left + x, 36 + y, left + x + max(w, 2), 36 + y + max(h, 2)]
            d.rectangle(box, outline=color(plate), width=2)
            text, at = read_of(plate, hide), (box[0], box[3] + 3)
            d.rectangle(d.textbbox(at, text, font=small), fill=WHITE)  # readable over the photo
            d.text(at, text, fill=color(plate), font=small)
    return sheet


def write_images(results=RESULTS, labels=LABELS, frames_dir=FRAMES, out=None, top=6, hide=0, frames=None):
    """Write the plate lists (better.png, worse.png, and better_vs_fixed.png, worse_vs_fixed.png
    when fixed and adaptive exist) and frames/<frame>.png. Returns the written paths."""
    out = Path(out) if out else Path(results) / "figures"
    conds, rows = collect(results, labels)
    paths, listed = [], []
    out.mkdir(parents=True, exist_ok=True)
    for base, suffix in (("orig", ""), ("fixed", "_vs_fixed")):
        if base not in conds or not later(conds, base):
            continue
        for name, chosen in zip(("better", "worse"), pick(rows, top, base)):
            listed += chosen
            if chosen:
                paths.append(out / f"{name}{suffix}.png")
                plate_list(chosen, conds, frames_dir, hide).save(paths[-1])
    names = [frame_key(f) for f in frames] if frames else list(dict.fromkeys(r["frame"] for r in listed))
    for frame in names:
        if not any((Path(frames_dir) / c / f"{frame}.png").exists() for c in conds):
            raise ValueError(f"{frame}.png is in none of {', '.join(conds)} under {frames_dir}")
        paths.append(out / "frames" / f"{frame}.png")
        paths[-1].parent.mkdir(parents=True, exist_ok=True)
        in_frame = [r for r in rows if r["frame"] == frame]  # none if no readable standard labeled plate
        frame_image(frame, in_frame, conds, frames_dir, hide).save(paths[-1])
    return paths


def vehicle_rows(results=RESULTS, scenes=SCENES):
    """(conditions found, rows): one row per labeled vehicle in a frame with boxes in every found condition.

    Row: {"frame", "bbox", "reads": {condition: vehicle_reads entry}}. With vehicles/clear.json the
    conditions start with clear, and reads["clear"] is None for a frame without a clear frame.
    """
    labels = load_vehicles(scenes)
    reads = {cond: vehicle_reads(dets, labels) for cond, dets in load_detections(results).items()}
    found = [c for c in CONDS if c in reads]
    rows = []
    for frame in reads[found[0]] if found else []:
        if all(frame in reads[c] for c in found):
            for i, box in enumerate(labels[frame]):
                row = {c: reads[c][frame][i] for c in found}
                if REFERENCE in reads:
                    row = {REFERENCE: reads[REFERENCE][frame][i] if frame in reads[REFERENCE] else None, **row}
                rows.append({"frame": frame_key(frame), "bbox": tuple(box), "reads": row})
    return ([REFERENCE] if REFERENCE in reads else []) + found, rows


def vehicle_pick(rows, top, base="orig"):
    """(better, worse) against base: vehicles found in a later condition but not in base, and found
    in base but missed in a later one. At most top each, widest first."""
    def later_found(row):
        return [row["reads"][c]["found"] for c in later(row["reads"], base)]

    better = [r for r in rows if not r["reads"][base]["found"] and any(later_found(r))]
    worse = [r for r in rows if r["reads"][base]["found"] and not all(later_found(r))]
    key = lambda r: (-r["bbox"][2], r["frame"])  # noqa: E731
    return sorted(better, key=key)[:top], sorted(worse, key=key)[:top]


def vehicle_color(read):
    return FAINT if read is None else GOOD if read["found"] else BAD


def vehicle_read_of(read):
    """found or missed, with the IoU of the matched or near-miss detection."""
    if read is None:
        return "no clear frame"
    if read["det"] is None:
        return "missed"
    return f"{'found' if read['found'] else 'missed'}  IoU {read['iou']:.2f}"


def vehicle_cell(image, bbox, read):
    """The vehicle area, its labeled box in gray and the detection box in the read's color."""
    x0, y0, x1, y1 = area_of(image.shape, bbox, VEHICLE_MARGIN)
    cell = fit(image[y0:y1, x0:x1], VEHICLE_H, VEHICLE_W)
    scale = cell.width / max(1, x1 - x0)
    d = ImageDraw.Draw(cell)
    for box, ink, width in ((bbox, FAINT, 2), (read and read["det"], vehicle_color(read), 3)):
        if box:
            x, y, w, h = box
            d.rectangle([(x - x0) * scale, (y - y0) * scale, (x + w - x0) * scale - 1, (y + h - y0) * scale - 1],
                        outline=ink, width=width)
    return cell


def vehicle_list(rows, conds, frames_dir=FRAMES, plates=None, hide=0):
    """One image for the vehicle rows: header, then size and vehicle area per condition."""
    big, small = font(26), font(18)
    row_h = PAD + VEHICLE_H + 30 + PAD
    sheet = Image.new("RGB", (LABEL_W + len(conds) * (VEHICLE_W + PAD) + PAD, 48 + len(rows) * row_h), WHITE)
    d = ImageDraw.Draw(sheet)
    d.text((PAD, 10), "vehicle", fill=INK, font=big)
    for j, cond in enumerate(conds):
        d.text((LABEL_W + j * (VEHICLE_W + PAD), 10), cond, fill=INK, font=big)
    for i, row in enumerate(rows):
        top = 48 + i * row_h
        d.line([(0, top), (sheet.width, top)], fill=(220, 220, 220), width=1)
        d.text((PAD, top + PAD + 20), f"{row['bbox'][2]} x {row['bbox'][3]} px", fill=INK, font=big)
        d.text((PAD, top + PAD + 56), row["frame"], fill=FAINT, font=small)
        for j, cond in enumerate(conds):
            left, read = LABEL_W + j * (VEHICLE_W + PAD), row["reads"][cond]
            image = load_frame(frames_dir, cond, row["frame"])
            if image is None:
                d.text((left, top + PAD + 20), "no frame", fill=FAINT, font=small)
            else:
                for plate in (plates or {}).get(row["frame"], []):
                    cover(image, plate["bbox"], plate["text"], hide)
                sheet.paste(vehicle_cell(image, row["bbox"], read), (left, top + PAD))
            d.text((left, top + PAD + VEHICLE_H + 4), vehicle_read_of(read), fill=vehicle_color(read), font=small)
    return sheet


def write_vehicle_images(results=RESULTS, scenes=SCENES, labels=LABELS, frames_dir=FRAMES, out=None, top=6, hide=0):
    """Write the vehicle lists that have vehicles (see the module docstring). Returns the written
    paths: none without boxes for orig and a later condition. labels are read only for --hide."""
    out = Path(out) if out else Path(results) / "figures"
    conds, rows = vehicle_rows(results, scenes)
    plates = load_labels(labels) if hide > 0 else {}
    paths = []
    for base, suffix in (("orig", ""), ("fixed", "_vs_fixed")):
        if base not in conds or not later(conds, base):
            continue
        for name, chosen in zip(("better", "worse"), vehicle_pick(rows, top, base)):
            if chosen:
                out.mkdir(parents=True, exist_ok=True)
                paths.append(out / f"vehicles_{name}{suffix}.png")
                vehicle_list(chosen, conds, frames_dir, plates, hide).save(paths[-1])
    return paths


def main():
    ap = argparse.ArgumentParser(description="Comparison images of plates and frames across conditions.")
    ap.add_argument("--results", type=Path, default=RESULTS, help="folder with ocr/<cond>.csv")
    ap.add_argument("--labels", type=Path, default=LABELS)
    ap.add_argument("--frames-dir", type=Path, default=FRAMES, help="folder with orig/, fixed/, adaptive/")
    ap.add_argument("--out", type=Path, help="default: <results>/figures")
    ap.add_argument("--top", type=int, default=6, help="plates per list")
    ap.add_argument("--hide", type=int, default=0, help="cover the last N characters of every labeled plate")
    ap.add_argument("--frames", nargs="+", help="frame images for these frames instead of the listed ones")
    ap.add_argument("--scenes", type=Path, nargs="+",
                    help="vehicle label files, merged (default: data/annotations/scenes.json); no vehicle lists without them")
    args = ap.parse_args()
    paths = write_images(args.results, args.labels, args.frames_dir, args.out, args.top, args.hide, args.frames)
    scenes = scenes_arg(args.scenes)
    if scenes is not None:
        paths += write_vehicle_images(args.results, scenes, args.labels, args.frames_dir, args.out, args.top,
                                      args.hide)
    print("\n".join(str(p) for p in paths) if paths else "no plate changed between conditions")


if __name__ == "__main__":
    main()
