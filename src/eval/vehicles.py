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
3. compare_vehicles / write_vehicle_compare (#86): orig -> fixed and fixed -> adaptive, vehicle
   by vehicle. A labeled vehicle is gained (found only in the target), lost (only in the base),
   both or neither, so gained + lost + both + neither = labeled. sign_p is the sign test (#84) on
   gained against lost. Vehicles in one frame share its fog, so they are not fully independent:
   read sign_p as a guide, not an exact level.
   -> results/vehicle_compare.csv (counts) and results/vehicles/changes.csv (gained and lost
   vehicles with their boxes; git ignores results/vehicles/)

Usage:
    python -m src.eval.vehicles [--frames data/frames] [--results results]
                                [--scenes data/annotations/scenes.json] [--skip-detect]
"""

import argparse
import json
from pathlib import Path

from .compare import PAIRS, sign_p, write_rows
from .ocr import iou

ROOT = Path(__file__).resolve().parents[2]
FRAMES = ROOT / "data" / "frames"
RESULTS = ROOT / "results"
SCENES = ROOT / "data" / "annotations" / "scenes.json"
CONDITIONS = ("orig", "fixed", "adaptive", "clear")  # clear: reference frames of the synthetic fog (#79)
MATCH_IOU = 0.5
NEAR_IOU = 0.1  # a missed vehicle's most overlapping detection below this is another vehicle, not a near miss
SIZES = (("<100", 0, 100), ("100-199", 100, 200), (">=200", 200, None))  # labeled box width, px
COLUMNS = ["condition", "size", "frames", "labeled", "found", "rate", "unmatched"]
CHANGES = ("gained", "lost")
COMPARE_COLUMNS = ["base", "target", "frames", "labeled", "gained", "lost", "both", "neither", "sign_p"]
CASE_COLUMNS = ["base", "target", "change", "frame", "size", "x", "y", "w", "h", "base_iou", "target_iou"]


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


def load_detections(results_dir):
    """{condition: {frame: [bbox, ...]}} for every results/vehicles/<cond>.json, in CONDITIONS order."""
    folder = Path(results_dir) / "vehicles"
    return {cond: json.loads((folder / f"{cond}.json").read_text(encoding="utf-8"))
            for cond in CONDITIONS if (folder / f"{cond}.json").exists()}


def vehicle_rates(results_dir, scenes):
    """Rows (COLUMNS) for every condition with results/vehicles/<cond>.json, in CONDITIONS order."""
    labels = load_vehicles(scenes)
    return [row for cond, dets in load_detections(results_dir).items() for row in rate_rows(cond, dets, labels)]


def vehicle_reads(detections, labels):
    """{frame: [read per labeled vehicle]} for one condition, frames with labels and detections only.

    Read: {"found": bool, "det": box or None, "iou": float}. det is the matched detection, or for a
    missed vehicle the detection overlapping it most, so a near miss shows; None when that IoU is
    below NEAR_IOU (an edge of a neighboring vehicle). iou is the IoU of that detection either way.
    """
    out = {}
    for frame in sorted(set(detections) & set(labels)):
        dets, found = detections[frame], match(detections[frame], labels[frame])
        reads = []
        for i, box in enumerate(labels[frame]):
            j = found.get(i, max(range(len(dets)), key=lambda k: iou(box, dets[k]), default=None))
            score = iou(box, dets[j]) if j is not None else 0.0
            reads.append({"found": i in found, "det": dets[j] if score >= NEAR_IOU else None, "iou": score})
        out[frame] = reads
    return out


def change_of(base, target):
    """gained, lost, both or neither for one labeled vehicle, from its base and target reads."""
    if base["found"]:
        return "both" if target["found"] else "lost"
    return "gained" if target["found"] else "neither"


def compare_vehicles(results_dir, scenes):
    """Compare orig -> fixed and fixed -> adaptive vehicle by vehicle.

    Returns (table, cases): lists of dicts with COMPARE_COLUMNS and CASE_COLUMNS. Only frames with
    detections in both conditions count; counts are None for a pair whose boxes are missing.
    Cases: gained vehicles first, then lost, each widest first.
    """
    labels = load_vehicles(scenes)
    reads = {cond: vehicle_reads(dets, labels) for cond, dets in load_detections(results_dir).items()}
    table, cases = [], []
    for base, target in PAIRS:
        row = dict.fromkeys(COMPARE_COLUMNS)
        row.update(base=base, target=target)
        if base in reads and target in reads:
            frames = sorted(set(reads[base]) & set(reads[target]))
            counts = dict.fromkeys(["labeled", *CHANGES, "both", "neither"], 0)
            pair_cases = []
            for frame in frames:
                for box, b, t in zip(labels[frame], reads[base][frame], reads[target][frame]):
                    kind = change_of(b, t)
                    counts["labeled"] += 1
                    counts[kind] += 1
                    if kind in CHANGES:
                        x, y, w, h = box
                        pair_cases.append({"base": base, "target": target, "change": kind, "frame": frame,
                                           "size": size_of(box), "x": x, "y": y, "w": w, "h": h,
                                           "base_iou": b["iou"], "target_iou": t["iou"]})
            row.update(counts, frames=len(frames), sign_p=sign_p(counts["gained"], counts["lost"]))
            cases += sorted(pair_cases, key=lambda c: (CHANGES.index(c["change"]), -c["w"], c["frame"]))
        table.append(row)
    return table, cases


def write_vehicle_compare(results_dir, scenes):
    """Write results/vehicle_compare.csv and results/vehicles/changes.csv. Returns both paths."""
    results_dir = Path(results_dir)
    table, cases = compare_vehicles(results_dir, scenes)
    (results_dir / "vehicles").mkdir(parents=True, exist_ok=True)
    return (write_rows(results_dir / "vehicle_compare.csv", COMPARE_COLUMNS, table),
            write_rows(results_dir / "vehicles" / "changes.csv", CASE_COLUMNS, cases))


def write_rates(results_dir, scenes):
    """Write results/vehicles.csv. Returns its path."""
    results_dir = Path(results_dir)
    rows = vehicle_rates(results_dir, scenes)
    if not rows:
        raise FileNotFoundError(f"no vehicle detections in {results_dir / 'vehicles'}")
    return write_rows(results_dir / "vehicles.csv", COLUMNS, rows)


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
    print(*write_vehicle_compare(args.results, args.scenes), sep="\n")


if __name__ == "__main__":
    main()
