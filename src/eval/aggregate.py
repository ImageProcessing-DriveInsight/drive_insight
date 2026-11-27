"""Aggregate OCR, VLM and timing results per condition (C-10).

Reads, under results_dir:
    ocr/ocr_summary.csv   OCR metrics per condition (python -m src.eval.ocr, C-09),
                          or ocr/<cond>.csv scored against labels when labels are given
    vlm/score.csv         VLM scores (D-08), one row per condition or per condition and clip
    timing.csv            step times per frame (D-04), and/or <cond>/timing.csv per condition
    ocr/<cond>.csv, params/<cond>.json
                          step times of a condition without a timing file: ocr_ms of the OCR run
                          (C-08) and enhance_ms of the fixed (A) or adaptive (B) batch
and writes summary.csv with one row per condition. A missing source leaves its columns empty.

Usage:
    python -m src.eval.aggregate [--results results] [--labels data/labels]
"""

import argparse
import csv
import json
from pathlib import Path

from .ocr import CONDITIONS, eval_conditions

ROOT = Path(__file__).resolve().parents[2]
OCR_COLUMNS = ["plates", "detection_rate", "exact_match", "char_accuracy", "overconfident", "readable_wrong"]
VLM_COLUMNS = ["vlm_scene_acc", "hallucination_rate", "uncheckable_claims"]
TIME_COLUMNS = ["enhance_ms", "ocr_ms", "vlm_ms", "total_ms"]
SUMMARY_COLUMNS = ["condition", *OCR_COLUMNS, *VLM_COLUMNS, *TIME_COLUMNS]
COUNT_COLUMNS = {"plates", "overconfident", "readable_wrong", "uncheckable_claims"}
VLM_COUNTS = ("facts", "facts_correct", "checkable_claims", "unsupported_claims")
EMPTY = {"", "n/a", "na", "nan", "none", "null"}


def num(value):
    """CSV cell -> float, or None for empty and N/A."""
    if value is None or str(value).strip().lower() in EMPTY:
        return None
    return float(value)


def mean(values):
    values = [v for v in values if v is not None]
    return sum(values) / len(values) if values else None


def read_rows(path, condition=None):
    """Rows of a CSV with a condition column; [] if the file is missing or empty.

    With condition given, the column may be missing and empty cells take that condition.
    """
    path = Path(path)
    if not path.exists():
        return []
    with open(path, encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        if reader.fieldnames is None:  # empty file
            return []
        if "condition" not in reader.fieldnames and condition is None:
            raise ValueError(f"{path}: needs a 'condition' column")
        rows = list(reader)
    if condition is not None:
        for r in rows:
            r["condition"] = (r.get("condition") or "").strip() or condition
    return rows


def by_condition(rows):
    groups = {}
    for r in rows:
        groups.setdefault(r["condition"].strip(), []).append(r)
    return groups


def ocr_metrics(results_dir, labels=None):
    """{cond: OCR metrics}. Scores ocr/<cond>.csv when labels are given, else reads ocr/ocr_summary.csv."""
    ocr_dir = Path(results_dir) / "ocr"
    if labels is not None:
        return {r.pop("condition"): r for r in eval_conditions(results_dir, labels)}
    return {cond: {k: num(rs[0].get(k)) for k in OCR_COLUMNS}
            for cond, rs in by_condition(read_rows(ocr_dir / "ocr_summary.csv")).items()}


def vlm_metrics(path):
    """{cond: VLM scores}.

    With the count columns in every row, the counts are pooled over clips:
        scene acc = facts_correct / facts, hallucination rate = 100 * unsupported / checkable.
    Otherwise the scene_acc and hallucination_rate of the rows are averaged, skipping N/A.
    """
    out = {}
    for cond, rs in by_condition(read_rows(path)).items():
        counts = [[num(r.get(k)) for k in VLM_COUNTS] for r in rs]
        if all(v is not None for c in counts for v in c):
            facts, correct, checkable, unsupported = (sum(c[i] for c in counts) for i in range(4))
            scene = correct / facts if facts else None
            hallucination = 100 * unsupported / checkable if checkable else None
        else:
            scene = mean(num(r.get("scene_acc")) for r in rs)
            hallucination = mean(num(r.get("hallucination_rate")) for r in rs)
        uncheckable = [num(r.get("uncheckable_claims")) for r in rs]
        out[cond] = {"vlm_scene_acc": scene, "hallucination_rate": hallucination,
                     "uncheckable_claims": sum(uncheckable) if all(v is not None for v in uncheckable) else None}
    return out


def timing_rows(results_dir):
    """Rows of timing.csv and of every <cond>/timing.csv under results_dir.

    D's runner (D-04) writes one file per condition folder; a row there without a condition
    takes the folder name. The same condition and frame twice is an error, so no frame counts twice.
    """
    results_dir = Path(results_dir)
    rows = read_rows(results_dir / "timing.csv")
    for path in sorted(results_dir.glob("*/timing.csv")):
        rows += read_rows(path, condition=path.parent.name)
    seen = set()
    for r in rows:
        key = (r["condition"].strip(), (r.get("frame") or "").strip())
        if key[1] and key in seen:
            raise ValueError(f"timing of {key[1]} in {key[0]} appears twice under {results_dir}")
        seen.add(key)
    return rows


def log_rows(results_dir, conds):
    """Step times from the stage logs, for conditions without a timing file.

    ocr_ms comes from ocr/<cond>.csv (once per frame; every plate row of a frame has the same
    value) and enhance_ms from params/<cond>.json, the per-frame log of A's fixed batch and B's
    adaptive batch. orig has no enhancement step. total_ms stays empty: the VLM step is not in
    these logs, and D's runner (D-04) measures the whole frame.
    """
    results_dir, rows = Path(results_dir), []
    for cond in conds:
        path = results_dir / "ocr" / f"{cond}.csv"
        if not path.exists():
            continue
        params = results_dir / "params" / f"{cond}.json"
        enhance = json.loads(params.read_text(encoding="utf-8")) if params.exists() else {}
        frames = {}
        for r in read_rows(path, condition=cond):
            frames.setdefault(r["frame"], r.get("ocr_ms"))
        rows += [{"condition": cond, "frame": frame, "ocr_ms": ms, "enhance_ms": (enhance.get(frame) or {}).get("enhance_ms")}
                 for frame, ms in frames.items()]
    return rows


def time_metrics(rows):
    """{cond: mean ms per frame for each step}. Empty cells are skipped, e.g. vlm_ms on frames without a VLM call."""
    return {cond: {k: mean(num(r.get(k)) for r in rs) for k in TIME_COLUMNS}
            for cond, rs in by_condition(rows).items()}


def summarize(results_dir, labels=None):
    """Rows of summary.csv as dicts: orig, fixed, adaptive first, then any other condition found."""
    results_dir = Path(results_dir)
    timing = timing_rows(results_dir)
    timed = {r["condition"].strip() for r in timing}
    timing += log_rows(results_dir, [c for c in CONDITIONS if c not in timed])
    sources = [ocr_metrics(results_dir, labels),
               vlm_metrics(results_dir / "vlm" / "score.csv"),
               time_metrics(timing)]
    found = {cond for s in sources for cond in s}
    order = [c for c in CONDITIONS if c in found] + sorted(found - set(CONDITIONS))
    rows = []
    for cond in order:
        row = dict.fromkeys(SUMMARY_COLUMNS)
        row["condition"] = cond
        for s in sources:
            row.update({k: v for k, v in s.get(cond, {}).items() if k in row})
        rows.append(row)
    return rows


def cell(column, value):
    if value is None:
        return ""
    if column in COUNT_COLUMNS and float(value).is_integer():
        return int(value)
    return round(value, 4) if isinstance(value, float) else value


def aggregate(results_dir, labels=None) -> Path:
    """Write <results_dir>/summary.csv with one row per condition.

    Args:
        results_dir: folder with ocr/, vlm/score.csv and timing.csv or <cond>/timing.csv.
        labels: optional plate labels (see src.eval.ocr). If given, ocr/<cond>.csv is
            scored again instead of reading ocr/ocr_summary.csv.

    Returns:
        Path to summary.csv. Rates are 0–1 except hallucination_rate (percent);
        times are mean ms per frame.
    """
    results_dir = Path(results_dir)
    results_dir.mkdir(parents=True, exist_ok=True)
    out_path = results_dir / "summary.csv"
    with open(out_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=SUMMARY_COLUMNS)
        writer.writeheader()
        for row in summarize(results_dir, labels):
            writer.writerow({k: cell(k, v) for k, v in row.items()})
    return out_path


def main():
    ap = argparse.ArgumentParser(description="Merge OCR, VLM and timing results into results/summary.csv.")
    ap.add_argument("--results", type=Path, default=ROOT / "results")
    ap.add_argument("--labels", type=Path, default=None,
                    help="score ocr/<cond>.csv against these labels instead of reading ocr_summary.csv")
    args = ap.parse_args()
    out = aggregate(args.results, args.labels)
    print(out)
    print(out.read_text(encoding="utf-8"), end="")


if __name__ == "__main__":
    main()
