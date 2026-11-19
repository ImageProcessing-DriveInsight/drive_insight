"""Run plate recognition over one condition's frames (C-08).

Plate country per frame comes from data/plate_countries.json (see src.plate.country).

Usage:
    python -m src.plate.run orig [--frames DIR] [--results DIR] [--countries FILE]
"""

import argparse
import csv
import time
from collections import Counter
from pathlib import Path

from .country import DEFAULT, country_of, load_countries
from .detect import RESULTS, ROOT, detect_plates
from .imgutil import load_png

FRAMES = ROOT / "data" / "frames"
CONDITIONS = ("orig", "fixed", "adaptive")
COLUMNS = ["frame", "plate", "x", "y", "w", "h", "crop_path", "text", "conf", "status", "ocr_ms"]


def run_ocr(cond, frames_dir=None, results_dir=None, countries=None) -> Path:
    """Read plates in every <frames_dir>/*.png and write <results_dir>/ocr/<cond>.csv.

    One row per plate. A frame with no plate still gets one row with empty plate
    fields, so the CSVs of all conditions list the same frames. countries is a plate
    country file or its {country: [patterns]} dict; None reads data/plate_countries.json.

    Returns:
        Path to the CSV.
    """
    if cond not in CONDITIONS:
        raise ValueError(f"cond must be one of {CONDITIONS}")
    frames_dir = Path(frames_dir or FRAMES / cond)
    results_dir = Path(results_dir or RESULTS)
    paths = sorted(frames_dir.glob("*.png"))
    if not paths:
        raise FileNotFoundError(f"no PNG frames in {frames_dir}")
    if not isinstance(countries, dict):
        countries = load_countries(countries)

    rows = []
    for path in paths:
        t = time.perf_counter()
        country = country_of(path.name, countries)
        extra = {} if country == DEFAULT else {"country": country}  # Korean frames: the call stays as before
        plates = detect_plates(load_png(path), cond=cond, frame_id=path.stem, results_dir=results_dir, **extra)
        ms = round((time.perf_counter() - t) * 1000, 1)
        if not plates:
            rows.append({"frame": path.name, "ocr_ms": ms})
        for i, p in enumerate(plates):
            x, y, w, h = p["bbox"]
            rows.append({"frame": path.name, "plate": i, "x": x, "y": y, "w": w, "h": h,
                         "crop_path": p["crop_path"], "text": p["text"] or "", "conf": p["conf"],
                         "status": p["status"], "ocr_ms": ms})

    out = results_dir / "ocr" / f"{cond}.csv"
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=COLUMNS, restval="")
        writer.writeheader()
        writer.writerows(rows)
    return out


def main():
    ap = argparse.ArgumentParser(description="Run plate recognition over one condition's frames.")
    ap.add_argument("cond", choices=CONDITIONS)
    ap.add_argument("--frames", type=Path, help="default: data/frames/<cond>")
    ap.add_argument("--results", type=Path, help="default: results")
    ap.add_argument("--countries", type=Path, help="plate country of each frame, default: data/plate_countries.json")
    args = ap.parse_args()
    out = run_ocr(args.cond, args.frames, args.results, args.countries)
    with open(out, encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    counts = Counter(r["status"] or "no plate" for r in rows)
    print(f"{out}: {len({r['frame'] for r in rows})} frames, {dict(counts)}")


if __name__ == "__main__":
    main()
