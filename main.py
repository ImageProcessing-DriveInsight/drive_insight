"""DriveInsight entry point: runner, VLM fact-check sheets, scoring, aggregation, package.

Run from the repository root (or press F5 in Visual Studio):

    python main.py                                   # all three conditions, then results/summary.csv
    python main.py --condition fixed --steps vlm     # one condition, one step
    python main.py --clip clip01 --clip clip02       # only these clips for the VLM step
    python main.py --offline                         # no VLM calls: use cached results/vlm/<cond>/<clip>.json
    python main.py --make-sheets                     # blinded fact-check sheets for the team
    python main.py --score                           # score the filled sheets -> results/vlm/score.csv
    python main.py --package clip01                  # review package package/clip01/summary.html

Existing outputs are never overwritten: OCR results, VLM JSON files, filled sheets and
packages are kept, and only missing ones are made.
"""

import argparse
import csv
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.pipeline.runner import (  # noqa: E402
    VALID_CONDITIONS,
    VALID_STEPS,
    execute_experiment,
    run_experiment,
)

CONDITIONS = ["orig", "fixed", "adaptive"]
STEPS = ["enhance", "ocr", "vlm"]

FRAMES_DIR = ROOT / "data" / "frames"
RESULTS_DIR = ROOT / "results"
LABELS_DIR = ROOT / "data" / "labels"
VLM_DIR = RESULTS_DIR / "vlm"
SHEETS_DIR = VLM_DIR / "verify"
SHEET_KEY = VLM_DIR / "verify_key.csv"
SCORE_CSV = VLM_DIR / "score.csv"


def parse_args(argv=None):
    parser = argparse.ArgumentParser(
        description="Run the DriveInsight experiment from one place.",
    )
    parser.add_argument(
        "--condition", action="append", choices=CONDITIONS,
        help="condition to run (repeat for more). Default: all three",
    )
    parser.add_argument(
        "--steps", nargs="+", choices=STEPS, default=STEPS,
        help="steps to run. Default: enhance ocr vlm",
    )
    parser.add_argument(
        "--clip", action="append", dest="clips",
        help="clip ID for the VLM step (repeat for more). Default: all clips",
    )
    parser.add_argument(
        "--offline", action="store_true",
        help="never call the VLM; reuse cached JSON files only",
    )
    parser.add_argument(
        "--make-sheets", action="store_true",
        help="write blinded fact-check sheets to results/vlm/verify/",
    )
    parser.add_argument(
        "--score", action="store_true",
        help="score the filled fact-check sheets into results/vlm/score.csv",
    )
    parser.add_argument(
        "--package", metavar="CLIP",
        help="build the review package for one clip",
    )
    parser.add_argument(
        "--no-run", action="store_true",
        help="skip the runner (only sheets, scoring, aggregation or package)",
    )
    return parser.parse_args(argv)


def frame_names(condition):
    folder = FRAMES_DIR / condition
    if not folder.is_dir():
        raise FileNotFoundError(
            f"Frames folder not found: {folder}. "
            "Frames are not in git; get them from the team (see README, Data)."
        )
    return sorted(path.name for path in folder.glob("*.png"))


def run_conditions(conditions, steps, clips, offline):
    frame_lists = {condition: frame_names(condition) for condition in conditions}

    for condition in conditions:
        print(f"\n=== {condition} ===")
        run_experiment(condition, steps=steps, frame_lists=frame_lists)
        result = execute_experiment(
            condition,
            steps=steps,
            clip_ids=clips,
            frames_dir=FRAMES_DIR / condition,
            results_dir=RESULTS_DIR,
            offline=offline,
        )
        for key in ("frames", "enhance", "ocr", "vlm", "timing"):
            if key in result:
                print(f"{key:>8}: {result[key]}")
        if result["processed_clips"]:
            print(f"     new: {', '.join(result['processed_clips'])}")
        if result["skipped_clips"]:
            print(f"  cached: {', '.join(result['skipped_clips'])}")
        if result["missing_clips"]:
            print(
                f" missing: {', '.join(result['missing_clips'])} "
                "(offline: run once without --offline to make them)"
            )


def make_sheets(conditions):
    """One blinded sheet per (condition, clip); the key file maps sheet IDs back."""
    from src.vlm.claims import extract_claims
    from src.vlm.cache import load_cache

    pairs = []
    for condition in conditions:
        for path in sorted((VLM_DIR / condition).glob("*.json")):
            pairs.append((condition, path.stem, path))

    if not pairs:
        print("No VLM results yet in results/vlm/<condition>/. Run the vlm step first.")
        return

    existing = {}
    if SHEET_KEY.exists():
        with SHEET_KEY.open(newline="", encoding="utf-8") as file:
            for row in csv.DictReader(file):
                existing[(row["condition"], row["clip"])] = row["sheet"]

    new_pairs = [pair for pair in pairs if pair[:2] not in existing]
    random.Random(42).shuffle(new_pairs)

    used = set(existing.values())
    number = 1
    rows = [
        {"sheet": sheet, "condition": condition, "clip": clip}
        for (condition, clip), sheet in existing.items()
    ]

    SHEETS_DIR.mkdir(parents=True, exist_ok=True)
    for condition, clip, path in new_pairs:
        while f"s{number:03d}" in used:
            number += 1
        sheet = f"s{number:03d}"
        used.add(sheet)
        sheet_path = SHEETS_DIR / f"{sheet}.csv"
        if sheet_path.exists():
            raise FileExistsError(f"Sheet already exists: {sheet_path}")
        extract_claims(load_cache(path), output_path=sheet_path)
        rows.append({"sheet": sheet, "condition": condition, "clip": clip})

    with SHEET_KEY.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=["sheet", "condition", "clip"])
        writer.writeheader()
        writer.writerows(sorted(rows, key=lambda row: row["sheet"]))

    print(f"{len(new_pairs)} new sheets in {SHEETS_DIR} ({len(rows)} in total).")
    print(
        "Give the fact checkers only the verify/ folder, not verify_key.csv. "
        "In each sheet set label to correct, unsupported or uncheckable."
    )


def score_sheets():
    from src.vlm.scoring import score_vlm

    if not SHEET_KEY.exists():
        print("No fact-check sheets yet. Run: python main.py --no-run --make-sheets")
        return

    with SHEET_KEY.open(newline="", encoding="utf-8") as file:
        key = list(csv.DictReader(file))

    scored, unfilled = 0, []
    for row in key:
        sheet_path = SHEETS_DIR / f"{row['sheet']}.csv"
        with sheet_path.open(newline="", encoding="utf-8") as file:
            claims = list(csv.DictReader(file))
        if any(
            claim["checkability"].strip().lower() == "checkable"
            and not claim["label"].strip()
            for claim in claims
        ):
            unfilled.append(row["sheet"])
            continue
        score_vlm(
            sheet_path, {}, SCORE_CSV,
            condition=row["condition"], clip=row["clip"],
        )
        scored += 1

    print(f"Scored {scored} sheets into {SCORE_CSV}.")
    if unfilled:
        print(f"Not filled yet (skipped): {', '.join(unfilled)}")


def aggregate_results():
    from src.eval.aggregate import aggregate

    labels = LABELS_DIR if LABELS_DIR.is_dir() else None
    out = aggregate(RESULTS_DIR, labels)
    print(f"\nSummary: {out}")
    print(out.read_text(encoding="utf-8"), end="")


def build_package(clip):
    from src.package.builder import build_package as build

    print(f"\nPackage: {build(clip)}")


def main(argv=None):
    args = parse_args(argv)
    conditions = args.condition or CONDITIONS
    assert set(conditions) <= VALID_CONDITIONS and set(args.steps) <= VALID_STEPS

    try:
        if not args.no_run:
            run_conditions(conditions, args.steps, args.clips, args.offline)
        if args.make_sheets:
            make_sheets(conditions)
        if args.score:
            score_sheets()
        aggregate_results()
        if args.package:
            build_package(args.package)
    except (FileNotFoundError, FileExistsError, ValueError) as error:
        print(f"\nError: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
