"""Aggregate OCR, VLM and timing results per condition (stub)."""

import csv
from pathlib import Path

SUMMARY_COLUMNS = [
    "condition",
    "detection_rate",
    "exact_match",
    "char_accuracy",
    "overconfident",
    "vlm_scene_acc",
    "hallucination_rate",
    "enhance_ms",
    "ocr_ms",
    "vlm_ms",
    "total_ms",
]


def aggregate(results_dir) -> Path:
    """Write <results_dir>/summary.csv with one row per condition.

    Returns:
        Path to summary.csv.
    """
    # TODO(C-10): merge results/ocr, results/vlm/score.csv, timing.csv
    results_dir = Path(results_dir)
    results_dir.mkdir(parents=True, exist_ok=True)
    out_path = results_dir / "summary.csv"
    with open(out_path, "w", newline="", encoding="utf-8") as f:
        csv.writer(f).writerow(SUMMARY_COLUMNS)
    return out_path
