"""Repeatable CPU-only DIP benchmark: python -m tools.benchmark_dip."""

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import platform
import subprocess
import time

import numpy as np

from src.dip import FIXED_PARAMS, fixed_enhance, gaussian, median
from src.dip.color import validate_frame

ROOT = Path(__file__).resolve().parents[1]
CASES = {
    "gaussian3": ({"ksize": 3, "sigma": 1.0}, 500.0),
    "gaussian5": ({"ksize": 5, "sigma": 1.0}, 500.0),
    "gaussian9": ({"ksize": 9, "sigma": 1.5}, 500.0),
    "median3": ({"ksize": 3}, 1500.0),
    "median5": ({"ksize": 5}, 1500.0),
    "fixed": (dict(FIXED_PARAMS), 2000.0),
}


def benchmark_frame(frame, *, warmups=2, repeats=5, cases=None):
    """Time operations only; full-size warmups, same immutable input, no I/O."""
    validate_frame(frame)
    if type(warmups) is not int or warmups < 0 or type(repeats) is not int or repeats < 1:
        raise ValueError("warmups must be a nonnegative int; repeats a positive int")
    names = list(CASES) if cases is None else list(cases)
    if not names or any(name not in CASES for name in names) or len(set(names)) != len(names):
        raise ValueError("cases must contain unique known case names")
    results = {}
    for name in names:
        params, target = CASES[name]
        def operation():
            if name.startswith("gaussian"):
                return gaussian(frame, **params)
            if name.startswith("median"):
                return median(frame, **params)
            return fixed_enhance(frame)[0]
        for _ in range(warmups):
            operation()
        samples = []
        for _ in range(repeats):
            start = time.perf_counter()
            operation()
            samples.append((time.perf_counter() - start) * 1000)
        median_ms = float(np.median(samples))
        applicable = frame.shape == (1080, 1920, 3)
        results[name] = {
            "params": params.copy(), "samples_ms": samples, "median_ms": median_ms,
            "p95_ms": float(np.percentile(samples, 95)), "target_ms": target,
            "target_applicable": applicable,
            "target_met": median_ms <= target if applicable else None,
        }
        print(f"{name}: median={median_ms:.3f}ms p95={results[name]['p95_ms']:.3f}ms", flush=True)
    return results


def environment():
    commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT,
                            capture_output=True, text=True, check=True).stdout.strip()
    return {
        "python": platform.python_version(), "numpy": np.__version__,
        "platform": platform.platform(), "processor": platform.processor(),
        "logical_cpus": os.cpu_count(), "commit": commit,
        "source_sha256": {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest()
                          for name in ("src/dip/ops.py", "src/dip/color.py", "src/dip/fixed.py")},
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--warmups", type=int, default=2)
    parser.add_argument("--repeats", type=int, default=5)
    parser.add_argument("--cases", nargs="+", choices=CASES)
    parser.add_argument("--seed", type=int, default=29)
    parser.add_argument("--width", type=int, default=1920)
    parser.add_argument("--height", type=int, default=1080)
    parser.add_argument("--image", help="Real PNG input; never resized. Relative to project root.")
    parser.add_argument("--output", default="results/benchmarks/dip.json")
    args = parser.parse_args(argv)
    if args.width < 1 or args.height < 1 or args.seed < 0:
        parser.error("width/height must be positive and seed nonnegative")
    target = Path(args.output)
    target = target if target.is_absolute() else ROOT / target
    if target.suffix.lower() != ".json":
        parser.error("output must be a .json file")
    if args.image:
        from src.io.video import load_frame, resolve
        source = resolve(args.image)
        if source.suffix.lower() != ".png":
            parser.error("image must be a PNG file")
        frame = load_frame(source)
        provenance = {"kind": "real_png", "filename": source.name}
    else:
        frame = np.random.default_rng(args.seed).integers(0, 256, (args.height, args.width, 3), dtype=np.uint8)
        provenance = {"kind": "synthetic_uniform_uint8", "seed": args.seed}
    report = {
        "schema_version": 1, "created_utc": datetime.now(timezone.utc).isoformat(),
        "environment": environment(), "input": {
            **provenance, "shape": list(frame.shape), "dtype": str(frame.dtype),
            "pixel_sha256": hashlib.sha256(frame.tobytes()).hexdigest(),
        },
        "warmups": args.warmups, "repeats": args.repeats,
        "timing_scope": "operation call including output disposal; excluding input generation, decoding and JSON IO",
        "target_rule": "1080p median <= target; p95 is reported separately",
        "results": benchmark_frame(frame, warmups=args.warmups, repeats=args.repeats, cases=args.cases),
    }
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(report, indent=2, ensure_ascii=False, allow_nan=False), encoding="utf-8")
    print(f"Report: {target}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
