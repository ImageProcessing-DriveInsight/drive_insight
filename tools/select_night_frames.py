"""Freeze A's night frame lists using C's confirmed 2026-11-23 sampling rules."""

import argparse
from collections import defaultdict
import csv
import hashlib
import json
import math
from pathlib import Path
import random
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from src.io.video import resolve
from tools.audit_night_data import DEFAULT_ROOT, audit_dataset

FIELDS = ["split", "condition", "scene", "difficulty", "source", "frame", "tags", "sequence_index", "mean_gray"]
RULES = {"seed": 2026, "rng": "independent Random(2026) per name-sorted cohort",
         "normal_brightness_min": 5, "vehicle_width_min": 100,
         "eligible": "at least 6 frames and qualifying complete frames * 2 >= all frames",
         "normal_split": [4, 1], "hard_split": [1, 1],
         "positions": "[round(i * (n - 1) / 5) for i in range(6)]",
         "capture_timing": "unknown"}


def frame_number(frame):
    match = re.search(r"_(\d+)$", Path(frame["source"]).stem)
    if not match:
        raise ValueError("Source filename needs a numeric final suffix")
    return int(match.group(1))


def choose_frames(report, metadata, *, expected_counts=(41, 137)):
    """Pure selection from a successful audit and CSV metadata; never inspect results."""
    if report.get("issues") or report["summary"]["issues"]:
        raise ValueError("Resolve audit issues before selection")
    scenes = defaultdict(list)
    for frame in report["frames"]:
        scenes[frame["scene"]].append(frame)
    cohorts = {"normal": [], "hard": []}
    for scene, frames in sorted(scenes.items()):
        if scene not in metadata:
            raise ValueError(f"Missing clips.csv metadata: {scene}")
        brightness = float(metadata[scene]["mean_gray"])
        if not math.isfinite(brightness) or not 0 <= brightness <= 255:
            raise ValueError("Invalid mean_gray")
        qualifying = sum(f["has_vehicle_width_ge_100"] for f in frames)
        if len(frames) >= 6 and qualifying * 2 >= len(frames):
            cohorts["normal" if brightness >= 5 else "hard"].append(scene)
    counts = tuple(len(cohorts[k]) for k in ("normal", "hard"))
    if expected_counts is not None and counts != tuple(expected_counts):
        raise ValueError(f"Candidate counts {counts} differ from expected {tuple(expected_counts)}")
    selected, rows, used = {}, [], set()
    for difficulty, size, eval_count in (("normal", 5, 4), ("hard", 2, 1)):
        # Reinitialize independently: changing normal candidates must not affect hard choices.
        picked = random.Random(2026).sample(sorted(cohorts[difficulty]), size)
        selected[difficulty] = picked
        for index, scene in enumerate(picked):
            split = "evaluation" if index < eval_count else "tuning"
            frames = sorted(scenes[scene], key=frame_number)
            numbers = [frame_number(f) for f in frames]
            if len(set(numbers)) != len(numbers):
                raise ValueError(f"Duplicate numeric frame indices: {scene}")
            positions = [round(i * (len(frames) - 1) / 5) for i in range(6)]
            tags = "tunnel" if int(metadata[scene].get("tunnel_polygons", 0)) > 0 else ""
            for position in positions:
                frame = frames[position]
                name = Path(frame["source"]).stem + ".png"
                if name.casefold() in used:
                    raise ValueError("Output frame names must be unique across both splits")
                used.add(name.casefold())
                rows.append(dict(split=split, condition="low_light", scene=scene, difficulty=difficulty,
                                 source=frame["source"], frame=name, tags=tags,
                                 sequence_index=frame_number(frame), mean_gray=float(metadata[scene]["mean_gray"])))
    return {"rules": RULES, "candidate_counts": dict(zip(("normal", "hard"), counts)),
            "selected_scenes": selected, "rows": rows}


def read_metadata(path):
    with path.open(encoding="utf-8-sig", newline="") as stream:
        rows = list(csv.DictReader(stream))
    out = {}
    for row in rows:
        name = row["clip"]
        if name in out:
            raise ValueError("Duplicate clip metadata")
        out[name] = row
    return out


def write_selection(selection, destination):
    """Create a fresh handoff directory. COMPLETE.json is published last."""
    destination = Path(destination)
    destination.mkdir(parents=True, exist_ok=False)
    for split in ("evaluation", "tuning"):
        rows = [r for r in selection["rows"] if r["split"] == split]
        for suffix, fields in (("frames", FIELDS), ("names", ["source", "frame"])):
            with (destination / f"{split}_{suffix}.csv").open("x", encoding="utf-8-sig", newline="") as stream:
                writer = csv.DictWriter(stream, fieldnames=fields, extrasaction="ignore")
                writer.writeheader()
                writer.writerows(rows)
    hashes = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(destination.glob("*.csv"))}
    manifest = {k: v for k, v in selection.items() if k != "rows"}
    manifest["csv_sha256"] = hashes
    (destination / "COMPLETE.json").write_text(json.dumps(manifest, indent=2, allow_nan=False), encoding="utf-8")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=DEFAULT_ROOT)
    parser.add_argument("--output", default="data/manifests/a_night")
    args = parser.parse_args(argv)
    root, output = resolve(args.root).resolve(), resolve(args.output).resolve()
    if output == root or output.is_relative_to(root):
        parser.error("Output must be outside the source dataset")
    try:
        if output.exists():
            raise FileExistsError("Selection output already exists; never overwrite a frozen list")
        report = audit_dataset(root)
        metadata = read_metadata(root / "clips.csv")
        selection = choose_frames(report, metadata)
        labels = {f["source"]: f["label_sha256"] for f in report["frames"]}
        selection["source_label_sha256"] = {r["source"]: labels[r["source"]] for r in selection["rows"]}
        selection["source_image_sha256"] = {r["source"]: hashlib.sha256((root / r["source"]).read_bytes()).hexdigest()
                                             for r in selection["rows"]}
        selection["clips_csv_sha256"] = hashlib.sha256((root / "clips.csv").read_bytes()).hexdigest()
        selection["dataset"] = "AI Hub 71588 Validation front camera"
        write_selection(selection, output)
    except (OSError, ValueError, KeyError, TypeError) as exc:
        parser.exit(2, f"Night selection failed: {exc}\n")
    print(json.dumps({"candidate_counts": selection["candidate_counts"],
                      "selected_scenes": selection["selected_scenes"],
                      "evaluation_frames": 30, "tuning_frames": 12}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
