"""Read-only image/label audit; does not select scenes or infer capture times."""

import argparse
from collections import Counter
import hashlib
import json
import math
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.io.video import load_frame, resolve
from tools.aihub_vehicles import image_name, objects, scene_entry

DEFAULT_ROOT = "team_data/A_night/71588_night_highway_front"


def _index(folder, suffixes, issues):
    indexed = {}
    for path in sorted(folder.rglob("*")):
        if path.suffix.lower() not in suffixes:
            continue
        relative = path.relative_to(folder)
        if path.is_symlink() or any(p.is_symlink() for p in path.parents if p != folder.parent):
            issues.append({"path": relative.as_posix(), "message": "Symlink input is not supported"})
            continue
        if not path.is_file():
            continue
        key = relative.with_suffix("").as_posix().casefold()
        if key in indexed:
            issues.append({"path": relative.as_posix(), "message": "Duplicate image/label stem"})
        else:
            indexed[key] = path
    return indexed


def audit_dataset(root=DEFAULT_ROOT, *, decode_images=False):
    """Pair by relative stem; report C-compatible boxes without choosing evaluation data.

    Width >=100 counts only in complete (non-group) frames. This is an audit count,
    not approval of scene eligibility, brightness aggregation or sampling rules.
    """
    root = resolve(root).resolve()
    issues, frames = [], []
    for name in ("images", "labels"):
        if not (root / name).is_dir():
            raise ValueError(f"Missing dataset directory: {name}")
    images = _index(root / "images", {".jpg", ".jpeg", ".png"}, issues)
    labels = _index(root / "labels", {".json"}, issues)
    if not images:
        issues.append({"path": "images", "message": "No image files"})
    for key in sorted(set(images) | set(labels)):
        image, label_path = images.get(key), labels.get(key)
        if image is None or label_path is None:
            existing = image or label_path
            issues.append({"path": existing.relative_to(root).as_posix(),
                           "message": "Missing matching label" if label_path is None else "Missing matching image"})
            continue
        relative = image.relative_to(root / "images")
        try:
            raw = label_path.read_bytes()
            label = json.loads(raw.decode("utf-8-sig"))
            if image_name(label, label_path) != image.name:
                raise ValueError("Label image filename does not match the source")
            _, objs, size = objects(label, label_path)
            if not size or min(size) <= 0:
                raise ValueError("Label has no positive image dimensions")
            if any(not math.isfinite(float(v)) for _, points in objs for point in points for v in point):
                raise ValueError("Label contains non-finite coordinates")
            entry = scene_entry(label, label_path)
            if decode_images:
                frame = load_frame(image)
                if (frame.shape[1], frame.shape[0]) != size:
                    raise ValueError("Decoded image dimensions differ from the label")
            frames.append({"source": image.relative_to(root).as_posix(), "source_name": image.name,
                           "label": label_path.relative_to(root).as_posix(),
                           "label_sha256": hashlib.sha256(raw).hexdigest(),
                           "scene": relative.parent.as_posix(), "width": size[0], "height": size[1],
                           "annotation_status": entry["annotation_status"],
                           "vehicle_count": len(entry["vehicles"]),
                           "has_vehicle_width_ge_100": entry["annotation_status"] == "complete"
                               and any(v["bbox"][2] >= 100 for v in entry["vehicles"])})
        except (OSError, ValueError, TypeError, KeyError, IndexError, OverflowError) as exc:
            issues.append({"path": relative.as_posix(), "message": str(exc)})
    scenes = Counter(f["scene"] for f in frames)
    return {"schema_version": 1, "decode_images": decode_images,
            "selection_status": "not_selected", "capture_timing": "unknown",
            "summary": {"images": len(images), "labels": len(labels), "paired_valid": len(frames),
                        "scenes": len(scenes), "group_frames": sum(f["annotation_status"] == "group" for f in frames),
                        "complete_frames": sum(f["annotation_status"] == "complete" for f in frames),
                        "issues": len(issues)}, "frames": frames, "issues": issues}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=DEFAULT_ROOT)
    parser.add_argument("--decode-images", action="store_true", help="Also decode every source locally and check dimensions")
    parser.add_argument("--output", default="data/annotations/a_night_audit.json")
    args = parser.parse_args(argv)
    output = resolve(args.output).resolve()
    root = resolve(args.root).resolve()
    if output == root or output.is_relative_to(root):
        parser.error("Audit output must be outside the source dataset")
    try:
        report = audit_dataset(root, decode_images=args.decode_images)
        if output.exists():
            raise FileExistsError("Audit output exists; choose a new report path")
        output.parent.mkdir(parents=True, exist_ok=True)
        with output.open("x", encoding="utf-8") as stream:
            json.dump(report, stream, ensure_ascii=False, indent=2, allow_nan=False)
    except (OSError, ValueError) as exc:
        parser.exit(2, f"Night data audit failed: {exc}\n")
    print(json.dumps(report["summary"], sort_keys=True))
    return 1 if report["issues"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
