"""C's whole chain in one command (C-08 to C-11, issue #81).

1. OCR (src.plate.run) on every condition with frames under --frames: orig, fixed, adaptive,
   and the clear reference (#79) when clear/ exists. orig, fixed and adaptive must list the
   same frames, and clear only frames of orig; otherwise it stops before any OCR.
2. Evaluation (src.eval.ocr)          -> <results>/ocr/ocr_summary.csv
3. Aggregation (src.eval.aggregate)   -> <results>/summary.csv
4. Comparison (src.eval.compare)      -> <results>/compare.csv, worse_cases.csv
5. Slide images (tools/compare_images.py) -> <results>/figures/
6. Vehicle detection rate (src.eval.vehicles, #83) -> <results>/vehicles.csv, when the
   vehicle labels (--scenes) exist: YOLO on every condition's frames, matched to the labels

--skip-ocr reuses the existing <results>/ocr/<cond>.csv and <results>/vehicles/<cond>.json,
e.g. after the labels changed.
Run it again after A's or B's enhancement changes so all numbers come from one run.

Usage:
    python tools/plate_report.py [--frames data/frames] [--results results] [--labels data/labels]
                                 [--scenes data/annotations/scenes.json] [--skip-ocr] [--hide N]
"""

import argparse
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.eval.aggregate import aggregate  # noqa: E402
from src.eval.compare import write_compare  # noqa: E402
from src.eval.ocr import eval_conditions, write_summary  # noqa: E402
from src.eval.vehicles import SCENES, detect_frames, write_rates  # noqa: E402
from src.plate.run import CONDITIONS, REFERENCE, run_ocr  # noqa: E402
from tools.compare_images import write_images  # noqa: E402

FRAMES = ROOT / "data" / "frames"
RESULTS = ROOT / "results"
LABELS = ROOT / "data" / "labels"


def frame_names(frames_dir):
    """{condition: sorted PNG names} for the conditions with frames, in pipeline order."""
    out = {}
    for cond in (*CONDITIONS, REFERENCE):
        names = sorted(p.name for p in (Path(frames_dir) / cond).glob("*.png"))
        if names:
            out[cond] = names
    return out


def check_frames(names):
    """Raise ValueError unless orig exists, fixed and adaptive list its frames, and clear a subset of them."""
    if "orig" not in names:
        raise ValueError("no frames in orig/")
    orig = set(names["orig"])
    for cond in CONDITIONS[1:]:
        if cond in names and set(names[cond]) != orig:
            diff = sorted(set(names[cond]) ^ orig)
            raise ValueError(f"{cond}/ and orig/ list different frames, e.g. {diff[:3]}")
    if REFERENCE in names and not set(names[REFERENCE]) <= orig:
        raise ValueError(f"{REFERENCE}/ has frames that are not in orig/, e.g. {sorted(set(names[REFERENCE]) - orig)[:3]}")


def report(frames_dir=FRAMES, results_dir=RESULTS, labels=LABELS, skip_ocr=False, hide=0, ocr=run_ocr, log=print,
           scenes=None, detect=None):
    """Run the chain. scenes: vehicle labels for step 6 (None skips it); detect: vehicle detector.

    Returns {"ocr": [csv paths], "ocr_summary", "summary", "compare", "worse_cases", "figures": [...],
    "vehicles": vehicles.csv path or None}.
    """
    frames_dir, results_dir = Path(frames_dir), Path(results_dir)
    out = {"ocr": []}
    if skip_ocr:
        out["ocr"] = [p for c in (*CONDITIONS, REFERENCE) if (p := results_dir / "ocr" / f"{c}.csv").exists()]
    else:
        names = frame_names(frames_dir)
        check_frames(names)
        for cond in names:
            start = time.perf_counter()
            out["ocr"].append(ocr(cond, frames_dir / cond, results_dir))
            log(f"ocr {cond}: {len(names[cond])} frames in {time.perf_counter() - start:.0f} s")
            if scenes is not None:
                detect_frames(cond, frames_dir / cond, results_dir, detect=detect)
    rows = eval_conditions(results_dir, labels)
    if not rows:
        raise FileNotFoundError(f"no OCR results in {results_dir / 'ocr'}")
    out["ocr_summary"] = write_summary(rows, results_dir / "ocr" / "ocr_summary.csv")
    out["summary"] = aggregate(results_dir)
    out["compare"], out["worse_cases"] = write_compare(results_dir, labels)
    found = {r["condition"] for r in rows}
    out["figures"] = (write_images(results_dir, labels, frames_dir, hide=hide)
                      if "orig" in found and found & set(CONDITIONS[1:]) else [])
    out["vehicles"] = (write_rates(results_dir, scenes)
                       if scenes is not None and any((results_dir / "vehicles").glob("*.json")) else None)
    log(f"wrote {out['ocr_summary']}, {out['summary']}, {out['compare']}, {len(out['figures'])} images"
        + (f", {out['vehicles']}" if out["vehicles"] else ""))
    return out


def main():
    ap = argparse.ArgumentParser(description="OCR, evaluation, aggregation, comparison and slide images in one run.")
    ap.add_argument("--frames", type=Path, default=FRAMES, help="folder with orig/, fixed/, adaptive/, clear/")
    ap.add_argument("--results", type=Path, default=RESULTS)
    ap.add_argument("--labels", type=Path, default=LABELS)
    ap.add_argument("--scenes", type=Path, default=SCENES, help="vehicle labels; the vehicle rate is skipped without them")
    ap.add_argument("--skip-ocr", action="store_true", help="reuse <results>/ocr/<cond>.csv")
    ap.add_argument("--hide", type=int, default=0, help="cover the last N characters in the slide images")
    args = ap.parse_args()
    scenes = args.scenes if args.scenes.exists() else None
    if scenes is None:
        print(f"no vehicle labels at {args.scenes}: skipping the vehicle detection rate")
    report(args.frames, args.results, args.labels, args.skip_ocr, args.hide, scenes=scenes)


if __name__ == "__main__":
    main()
