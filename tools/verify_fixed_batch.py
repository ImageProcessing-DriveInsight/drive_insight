"""Snapshot originals before A's batch and validate fixed outputs after it."""

import argparse
import hashlib
import json
import math
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from src.dip import FIXED_PARAMS
from src.io.video import load_frame, resolve


def _files(folder):
    folder = resolve(folder)
    paths = sorted(p for p in folder.iterdir() if p.suffix.lower() == ".png")
    if not paths:
        raise ValueError("No PNG input files")
    if len({p.name.casefold() for p in paths}) != len(paths):
        raise ValueError("Case-insensitive frame-name collision")
    if any(p.is_symlink() or not p.is_file() for p in paths):
        raise ValueError("Expected regular non-symlink PNG files")
    return {p.name: p for p in paths}


def snapshot_inputs(folder):
    frames = {}
    for name, path in _files(folder).items():
        before = path.read_bytes()
        image = load_frame(path)
        if path.read_bytes() != before:
            raise ValueError("Original changed while creating the snapshot")
        frames[name] = {"sha256": hashlib.sha256(before).hexdigest(), "shape": list(image.shape)}
    return {"schema_version": 1, "frames": frames}


def verify_outputs(original, fixed, params_path, snapshot):
    """Reject missing/stale/tampered originals, output shape errors and invalid logs.

    This verifies the handoff contract, not enhancement quality or independently
    recomputed pixel correctness; pixel correctness is covered by DIP tests.
    """
    orig, outputs = _files(original), _files(fixed)
    expected = snapshot.get("frames")
    if snapshot.get("schema_version") != 1 or not isinstance(expected, dict) or not expected:
        raise ValueError("Invalid original snapshot")
    if set(orig) != set(outputs) or set(orig) != set(expected):
        raise ValueError("Original, fixed and snapshot frame names differ")
    if resolve(original).resolve() == resolve(fixed).resolve():
        raise ValueError("Original and fixed directories must differ")
    records = json.loads(resolve(params_path).read_text(encoding="utf-8"))
    if not isinstance(records, dict) or set(records) != set(orig):
        raise ValueError("Parameter log frame names differ")
    times = []
    for name, path in orig.items():
        if hashlib.sha256(path.read_bytes()).hexdigest() != expected[name]["sha256"]:
            raise ValueError(f"Original bytes changed: {name}")
        if list(load_frame(path).shape) != expected[name]["shape"]:
            raise ValueError(f"Original shape changed: {name}")
        if list(load_frame(outputs[name]).shape) != expected[name]["shape"]:
            raise ValueError(f"Fixed shape differs: {name}")
        record = records[name]
        if not isinstance(record, dict) or record.get("params") != dict(FIXED_PARAMS):
            raise ValueError(f"Fixed params differ: {name}")
        timing = [record.get(k) for k in ("enhance_ms", "total_ms")]
        if any(isinstance(t, bool) or not isinstance(t, (int, float)) or not math.isfinite(t) or t < 0
               for t in timing) or timing[1] < timing[0]:
            raise ValueError(f"Invalid timing: {name}")
        times.append(timing[0])
    return {"frames_verified": len(orig), "originals_unchanged": True,
            "fixed_params": dict(FIXED_PARAMS), "mean_enhance_ms": sum(times) / len(times),
            "scope": "handoff integrity only; quality and benchmark claims require separate experiments"}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("snapshot", "verify"))
    parser.add_argument("--orig", default="data/frames/orig")
    parser.add_argument("--fixed", default="data/frames/fixed")
    parser.add_argument("--params", default="results/params/fixed.json")
    parser.add_argument("--snapshot", required=True, help="A new file before enhancement; existing file for verify")
    args = parser.parse_args(argv)
    target = resolve(args.snapshot).resolve()
    try:
        for folder in (args.orig, args.fixed):
            parent = resolve(folder).resolve()
            if target == parent or target.is_relative_to(parent):
                raise ValueError("Snapshot must be outside original and fixed folders")
        if args.action == "snapshot":
            if target.exists():
                raise FileExistsError("Snapshot already exists; do not replace original evidence")
            report = snapshot_inputs(args.orig)
            target.parent.mkdir(parents=True, exist_ok=True)
            with target.open("x", encoding="utf-8") as stream:
                json.dump(report, stream, indent=2, allow_nan=False)
            print(f"Snapshotted {len(report['frames'])} original PNG files")
        else:
            snapshot = json.loads(target.read_text(encoding="utf-8"))
            print(json.dumps(verify_outputs(args.orig, args.fixed, args.params, snapshot), allow_nan=False))
    except (OSError, ValueError, KeyError, TypeError) as exc:
        parser.exit(1, f"Fixed handoff check failed: {exc}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
