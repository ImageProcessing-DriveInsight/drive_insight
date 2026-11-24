"""AI Hub vehicle labels as ground truth for the vehicle detection rate (#90).

Reads AI Hub label JSONs and writes a scenes file with the parts of B's schema that
src.eval.vehicles reads:

    {frame: {"annotation_status": "complete", "vehicles": [{"bbox": [x, y, w, h], "class": str}]}}

Two label formats:
- labelme: {"imagePath", "imageWidth", "imageHeight", "shapes": [{"label", "points": [[x, y], ...]}]}
  (71588 night highway, 630 weather)
- polygon: {"information": {"filename", "resolution": [w, h]}, "annotations": [{"class", "polygon": [x1, y1, ...]}]}
  (71570 day highway, 71930 upcycling)

A vehicle box is the bounding box of its polygon, clipped to the image. Only VEHICLES count, the
classes the vehicle detector can find (car, bus, truck, motorcycle). The own car's hood (ego vehicle),
people, bicycles, trains, signs and road classes are left out.

A frame with a group label (cargroup, busgroup, ...) gets annotation_status "group", which
src.eval.vehicles leaves out: the vehicles inside a group have no box of their own, so a detection
of one of them would count as unmatched. A frame with no vehicle is complete with an empty list.

Frame names: the label's image file stem + ".png" (the evaluation frames are PNG), or the frame
column of a CSV with columns source, frame (source is the original image file name). With a CSV,
labels whose image is not listed are skipped.

The scenes file spells no plate, but it is derived from AI Hub labels: keep it in data/annotations/,
which git ignores.

Usage:
    python tools/aihub_vehicles.py LABELS_DIR [LABELS_DIR ...] [--out FILE] [--names CSV]
    python -m src.eval.vehicles --frames FRAMES_DIR --scenes FILE
"""

import argparse
import csv
import json
import sys
from collections import Counter
from pathlib import Path, PureWindowsPath

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.eval.vehicles import SIZES, size_of  # noqa: E402

OUT = ROOT / "data" / "annotations" / "aihub_vehicles.json"
VEHICLES = {
    "labelme": {"car", "truck", "bus", "motorcycle", "trailer", "caravan"},
    "polygon": {"vehicle", "truck", "bus", "ambulance", "schoolBus", "otherCar", "policeCar"},
}


def is_group(label):
    return label.lower().endswith("group")


def image_name(label, path):
    """Original image file name of one label file: its imagePath or filename, else the JSON's stem + .jpg."""
    name = label.get("imagePath") or (label.get("information") or {}).get("filename")
    return PureWindowsPath(name).name if name else Path(path).stem + ".jpg"


def objects(label, path):
    """[(class, [(x, y), ...])] and (width, height) or None, for either label format."""
    if "shapes" in label:
        size = (label.get("imageWidth"), label.get("imageHeight"))
        objs = [(s["label"], [tuple(p) for p in s["points"]]) for s in label["shapes"]]
        fmt = "labelme"
    elif "annotations" in label:
        size = tuple((label.get("information") or {}).get("resolution") or (None, None))
        objs = []
        for a in label["annotations"]:
            flat = a["polygon"]
            if len(flat) % 2:
                raise ValueError(f"{path}: polygon with an odd number of coordinates")
            objs.append((a["class"], list(zip(flat[::2], flat[1::2]))))
        fmt = "polygon"
    else:
        raise ValueError(f"{path}: neither labelme shapes nor polygon annotations")
    try:
        size = (int(size[0]), int(size[1]))
    except (TypeError, ValueError):
        size = None
    return fmt, objs, size


def bbox(points, size):
    """Bounding box [x, y, w, h] of a polygon, clipped to the image; None if nothing is left."""
    xs, ys = [p[0] for p in points], [p[1] for p in points]
    x1, y1, x2, y2 = min(xs), min(ys), max(xs), max(ys)
    if size:
        x1, y1, x2, y2 = max(x1, 0), max(y1, 0), min(x2, size[0]), min(y2, size[1])
    x1, y1, x2, y2 = (int(round(v)) for v in (x1, y1, x2, y2))
    return [x1, y1, x2 - x1, y2 - y1] if x2 > x1 and y2 > y1 else None


def scene_entry(label, path):
    """Scenes entry of one label file."""
    fmt, objs, size = objects(label, path)
    vehicles = []
    for cls, points in objs:
        if cls in VEHICLES[fmt] and points:
            box = bbox(points, size)
            if box:
                vehicles.append({"bbox": box, "class": cls})
    status = "group" if any(is_group(cls) for cls, _ in objs) else "complete"
    return {"annotation_status": status, "vehicles": vehicles}


def load_names(path):
    """{source image name: frame name} from a CSV with columns source, frame."""
    with open(path, newline="", encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
    if rows and not {"source", "frame"} <= set(rows[0]):
        raise ValueError(f"{path}: needs columns source, frame")
    return {PureWindowsPath(r["source"]).name: r["frame"] for r in rows}


def convert(label_dirs, names=None):
    """(scenes, skipped) for every *.json under label_dirs.

    names: {source image name: frame name}, or None for the image stem + .png. skipped counts the
    labels whose image is not in names.
    """
    scenes, origin, skipped = {}, {}, 0
    for folder in label_dirs:
        files = sorted(Path(folder).rglob("*.json"))
        if not files:
            raise FileNotFoundError(f"no label JSON in {folder}")
        for path in files:
            label = json.loads(path.read_text(encoding="utf-8-sig"))
            source = image_name(label, path)
            if names is None:
                frame = Path(source).stem + ".png"
            elif source in names:
                frame = names[source]
            else:
                skipped += 1
                continue
            if frame in scenes:
                raise ValueError(f"frame {frame} comes from both {origin[frame]} and {path}")
            scenes[frame], origin[frame] = scene_entry(label, path), path
    return scenes, skipped


def summary(scenes):
    """One line of counts: frames by status, vehicles by class and by labeled box width."""
    status = Counter(e["annotation_status"] for e in scenes.values())
    complete = [v for e in scenes.values() if e["annotation_status"] == "complete" for v in e["vehicles"]]
    classes = Counter(v["class"] for v in complete)
    sizes = Counter(size_of(v["bbox"]) for v in complete)
    return (f"{len(scenes)} frames ({status['complete']} complete, {status['group']} with a group label left out); "
            f"{len(complete)} vehicles in complete frames {dict(classes.most_common())}; "
            f"width {', '.join(f'{name} px {sizes[name]}' for name, _, _ in SIZES)}")


def main():
    ap = argparse.ArgumentParser(description="AI Hub vehicle labels -> scenes file for src.eval.vehicles.")
    ap.add_argument("labels", nargs="+", type=Path, help="folders with AI Hub label JSONs (searched recursively)")
    ap.add_argument("--out", type=Path, default=OUT, help="default: data/annotations/aihub_vehicles.json")
    ap.add_argument("--names", type=Path, help="CSV with columns source, frame (default: image stem + .png)")
    args = ap.parse_args()
    scenes, skipped = convert(args.labels, load_names(args.names) if args.names else None)
    if not scenes:
        raise SystemExit("no labeled frame matched")
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(scenes, indent=1), encoding="utf-8")
    print(f"{args.out}: {summary(scenes)}" + (f"; {skipped} labels not in --names skipped" if skipped else ""))


if __name__ == "__main__":
    main()
