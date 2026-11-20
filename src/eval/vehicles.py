"""Vehicle detection rate against the labeled vehicles (C-02 check, issue #83).

Labels: the `vehicles` of each complete frame in data/annotations/scenes.json (B's schema,
bbox [x, y, w, h]). A detection finds a labeled vehicle at IoU >= 0.5; each frame is matched
one to one, largest IoU first. Rates are split by the labeled box width, a stand-in for the
distance.

On the own dashcam frames the labeled boxes were drafted by YOLO on the clear frames and then
checked by eye (docs/label_draft.md). The clear rate is therefore close to 1 by construction:
it is the reference, and the fog conditions show how many of those vehicles are still found.

1. detect_frames: detect_vehicles on frames/<cond>/*.png -> results/vehicles/<cond>.json,
   {frame: [[x, y, w, h], ...]}
2. vehicle_rates / write_rates: results/vehicles/*.json + labels -> results/vehicles.csv

Usage:
    python -m src.eval.vehicles [--frames data/frames] [--results results]
                                [--scenes data/annotations/scenes.json] [--skip-detect]
"""

import argparse
import csv
import json
from pathlib import Path

from .ocr import iou

ROOT = Path(__file__).resolve().parents[2]
FRAMES = ROOT / "data" / "frames"
RESULTS = ROOT / "results"
SCENES = ROOT / "data" / "annotations" / "scenes.json"
CONDITIONS = ("orig", "fixed", "adaptive", "clear")  # clear: reference frames of the synthetic fog (#79)
MATCH_IOU = 0.5
SIZES = (("<100", 0, 100), ("100-199", 100, 200), (">=200", 200, None))  # labeled box width, px
COLUMNS = ["condition", "size", "frames", "labeled", "found", "rate", "unmatched"]


def load_vehicles(scenes):
    """scenes.json (path or dict) -> {frame: [bbox, ...]} for the complete frames."""
    if not isinstance(scenes, dict):
        scenes = json.loads(Path(scenes).read_text(encoding="utf-8"))
    return {frame: [list(v["bbox"]) for v in entry.get("vehicles", [])]
            for frame, entry in scenes.items() if entry.get("annotation_status", "complete") == "complete"}


def match(detections, labels, threshold=MATCH_IOU):
    """One-to-one matching, largest IoU first. Returns {label index: detection index}."""
    pairs = sorted(((iou(d, g), i, j) for j, d in enumerate(detections) for i, g in enumerate(labels)),
                   reverse=True)
    found, used = {}, set()
    for score, i, j in pairs:
        if score < threshold:
            break
        if i not in found and j not in used:
            found[i] = j
            used.add(j)
    return found


def size_of(box):
    return next(name for name, low, high in SIZES if box[2] >= low and (high is None or box[2] < high))


def detect_frames(cond, frames_dir=None, results_dir=None, detect=None):
    """Detect vehicles in frames/<cond>/*.png and write results/vehicles/<cond>.json. Returns its path."""
    frames_dir = Path(frames_dir or FRAMES / cond)
    results_dir = Path(results_dir or RESULTS)
    paths = sorted(frames_dir.glob("*.png"))
    if not paths:
        raise FileNotFoundError(f"no PNG frames in {frames_dir}")
    if detect is None:
        from src.plate.detect import detect_vehicles as detect  # loads YOLO on first call
    from src.plate.imgutil import load_png

    boxes = {p.name: [list(map(int, v["bbox"])) for v in detect(load_png(p))] for p in paths}
    out = results_dir / "vehicles" / f"{cond}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(boxes, indent=1), encoding="utf-8")
    return out


def rate_rows(cond, detections, labels):
    """Rows for one condition: all sizes first, then each size. Only frames with labels and detections count.

    unmatched counts the detections that found no labeled vehicle, by their own width.
    """
    frames = sorted(set(detections) & set(labels))
    counts = {name: {"labeled": 0, "found": 0, "unmatched": 0} for name, _, _ in SIZES}
    for frame in frames:
        dets, gold = detections[frame], labels[frame]
        found = match(dets, gold)
        for i, box in enumerate(gold):
            c = counts[size_of(box)]
            c["labeled"] += 1
            c["found"] += i in found
        for j in set(range(len(dets))) - set(found.values()):
            counts[size_of(dets[j])]["unmatched"] += 1
    total = {k: sum(c[k] for c in counts.values()) for k in ("labeled", "found", "unmatched")}
    rows = []
    for name, c in (("all", total), *counts.items()):
        rate = c["found"] / c["labeled"] if c["labeled"] else None
        rows.append({"condition": cond, "size": name, "frames": len(frames), **c, "rate": rate})
    return rows


def vehicle_rates(results_dir, scenes):
    """Rows (COLUMNS) for every condition with results/vehicles/<cond>.json, in CONDITIONS order."""
    results_dir = Path(results_dir)
    labels = load_vehicles(scenes)
    rows = []
    for cond in CONDITIONS:
        path = results_dir / "vehicles" / f"{cond}.json"
        if path.exists():
            rows += rate_rows(cond, json.loads(path.read_text(encoding="utf-8")), labels)
    return rows


def write_rates(results_dir, scenes):
    """Write results/vehicles.csv. Returns its path."""
    results_dir = Path(results_dir)
    rows = vehicle_rates(results_dir, scenes)
    if not rows:
        raise FileNotFoundError(f"no vehicle detections in {results_dir / 'vehicles'}")
    out = results_dir / "vehicles.csv"
    with open(out, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=COLUMNS)
        writer.writeheader()
        for r in rows:
            writer.writerow({k: "" if r[k] is None else round(r[k], 4) if isinstance(r[k], float) else r[k]
                             for k in COLUMNS})
    return out


def main():
    ap = argparse.ArgumentParser(description="Vehicle detection rate per condition against the labeled vehicles.")
    ap.add_argument("--frames", type=Path, default=FRAMES, help="folder with orig/, fixed/, adaptive/, clear/")
    ap.add_argument("--results", type=Path, default=RESULTS)
    ap.add_argument("--scenes", type=Path, default=SCENES)
    ap.add_argument("--skip-detect", action="store_true", help="reuse results/vehicles/<cond>.json")
    args = ap.parse_args()
    if not args.skip_detect:
        for cond in CONDITIONS:
            if any((args.frames / cond).glob("*.png")):
                print(detect_frames(cond, args.frames / cond, args.results))
    print(write_rates(args.results, args.scenes))


if __name__ == "__main__":
    main()
