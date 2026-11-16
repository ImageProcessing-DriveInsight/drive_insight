"""Compare conditions frame by frame (C-11).

For each pair (orig -> fixed, fixed -> adaptive), a frame is better, worse or unchanged by the
mean char accuracy of its readable labeled plates (frame_char_accuracy). Frames without a
readable labeled plate, or missing from either OCR CSV, are counted apart and not compared,
so better + worse + unchanged = frames.

Writes, under results_dir:
    compare.csv      one row per pair: frame counts and metric changes from summary.csv
    worse_cases.csv  one row per plate whose char accuracy dropped in a worse frame, with both crops

Usage:
    python -m src.eval.compare [--results results] [--labels data/labels]
"""

import argparse
import csv
from pathlib import Path

from .ocr import load_labels, plate_details

ROOT = Path(__file__).resolve().parents[2]
PAIRS = (("orig", "fixed"), ("fixed", "adaptive"))
DELTA_METRICS = ["detection_rate", "exact_match", "char_accuracy", "vlm_scene_acc", "hallucination_rate", "total_ms"]
TABLE_COLUMNS = ["base", "target", "frames", "better", "worse", "unchanged", "no_readable_label", "missing",
                 *[f"delta_{m}" for m in DELTA_METRICS]]
CASE_COLUMNS = ["base", "target", "frame", "label",
                "base_text", "base_status", "base_char_acc", "base_crop",
                "target_text", "target_status", "target_char_acc", "target_crop"]
EPS = 1e-9  # differences below this are unchanged


def num(value):
    value = "" if value is None else str(value).strip()
    return None if value.lower() in ("", "n/a", "na", "nan", "none") else float(value)


def load_summary(path):
    """summary.csv -> {condition: {column: float or None}}; {} if the file is missing."""
    path = Path(path)
    if not path.exists():
        return {}
    with open(path, encoding="utf-8-sig", newline="") as f:
        return {r["condition"]: {k: num(v) for k, v in r.items() if k != "condition"} for r in csv.DictReader(f)}


def frame_mean(plates):
    return sum(p["char_acc"] for p in plates) / len(plates)


def compare_pair(base, target, labels):
    """Frame counts and worse plates for one pair of plate-detail dicts (see plate_details)."""
    counts = dict.fromkeys(["frames", "better", "worse", "unchanged", "no_readable_label", "missing"], 0)
    cases = []
    for frame in labels:
        if frame not in base or frame not in target:
            counts["missing"] += 1
            continue
        b, t = base[frame], target[frame]
        if not b:
            counts["no_readable_label"] += 1
            continue
        counts["frames"] += 1
        diff = frame_mean(t) - frame_mean(b)
        if abs(diff) <= EPS:
            counts["unchanged"] += 1
            continue
        counts["better" if diff > 0 else "worse"] += 1
        if diff < 0:
            cases += [(frame, pb, pt) for pb, pt in zip(b, t) if pt["char_acc"] < pb["char_acc"] - EPS]
    return counts, cases


def compare(results_dir, labels):
    """Compare orig -> fixed and fixed -> adaptive.

    Args:
        results_dir: folder with ocr/<cond>.csv and, for metric changes, summary.csv (C-10).
        labels: plate labels (dict, JSON file or folder, see src.eval.ocr).

    Returns:
        (table, cases): lists of dicts with TABLE_COLUMNS and CASE_COLUMNS. Counts are None
        for a pair whose OCR CSV is missing; a delta is None when either value is missing.
        Worse cases are sorted by the drop in char accuracy, largest first.
    """
    results_dir = Path(results_dir)
    gold = load_labels(labels)
    details = {}
    for cond in {c for pair in PAIRS for c in pair}:
        path = results_dir / "ocr" / f"{cond}.csv"
        if path.exists():
            details[cond] = plate_details(path, gold)
    summary = load_summary(results_dir / "summary.csv")

    table, cases = [], []
    for base, target in PAIRS:
        row = dict.fromkeys(TABLE_COLUMNS)
        row.update(base=base, target=target)
        if base in details and target in details:
            counts, worse = compare_pair(details[base], details[target], gold)
            row.update(counts)
            worse.sort(key=lambda c: (c[2]["char_acc"] - c[1]["char_acc"], c[0]))
            cases += [{"base": base, "target": target, "frame": frame, "label": pb["label"],
                       "base_text": pb["text"], "base_status": pb["status"], "base_char_acc": pb["char_acc"],
                       "base_crop": pb["crop_path"],
                       "target_text": pt["text"], "target_status": pt["status"], "target_char_acc": pt["char_acc"],
                       "target_crop": pt["crop_path"]} for frame, pb, pt in worse]
        sb, st = summary.get(base, {}), summary.get(target, {})
        for m in DELTA_METRICS:
            if sb.get(m) is not None and st.get(m) is not None:
                row[f"delta_{m}"] = st[m] - sb[m]
        table.append(row)
    return table, cases


def write_rows(path, columns, rows):
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=columns)
        writer.writeheader()
        for r in rows:
            writer.writerow({k: "" if v is None else round(v, 4) if isinstance(v, float) else v for k, v in r.items()})
    return path


def write_compare(results_dir, labels):
    """Write compare.csv and worse_cases.csv under results_dir. Returns both paths."""
    results_dir = Path(results_dir)
    table, cases = compare(results_dir, labels)
    results_dir.mkdir(parents=True, exist_ok=True)
    return (write_rows(results_dir / "compare.csv", TABLE_COLUMNS, table),
            write_rows(results_dir / "worse_cases.csv", CASE_COLUMNS, cases))


def main():
    ap = argparse.ArgumentParser(description="Compare orig -> fixed and fixed -> adaptive frame by frame.")
    ap.add_argument("--results", type=Path, default=ROOT / "results")
    ap.add_argument("--labels", type=Path, default=ROOT / "data" / "labels")
    args = ap.parse_args()
    table_path, cases_path = write_compare(args.results, args.labels)
    print(table_path)
    print(table_path.read_text(encoding="utf-8"), end="")
    print(cases_path, f"({sum(1 for _ in open(cases_path, encoding='utf-8')) - 1} worse plates)")


if __name__ == "__main__":
    main()
