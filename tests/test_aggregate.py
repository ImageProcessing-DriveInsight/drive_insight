import csv

import pytest

from src.eval.aggregate import SUMMARY_COLUMNS, aggregate
from src.eval.ocr import SUMMARY_FIELDS

OCR_HEADER = SUMMARY_FIELDS
SCORE_HEADER = ["condition", "clip", "facts", "facts_correct", "checkable_claims", "unsupported_claims",
                "uncheckable_claims", "scene_acc", "hallucination_rate"]
TIMING_HEADER = ["frame", "condition", "enhance_ms", "ocr_ms", "vlm_ms", "total_ms"]
PLATE_HEADER = ["frame", "plate", "x", "y", "w", "h", "crop_path", "text", "conf", "status", "ocr_ms"]


def write_csv(path, header, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(header)
        writer.writerows(rows)


def read_summary(results_dir):
    with open(results_dir / "summary.csv", encoding="utf-8") as f:
        return {r["condition"]: r for r in csv.DictReader(f)}


def test_hand_case_merges_three_sources(tmp_path):
    """orig, all three sources.

    OCR: copied from ocr_summary.csv.
    VLM, pooled over 2 clips: scene acc (1 + 3) / (4 + 6) = 0.4 (mean of clip rates would be 0.375),
        hallucination 100 * (1 + 3) / (4 + 6) = 40.0 (mean would be 37.5), uncheckable 2 + 1 = 3.
    Timing, mean per frame: enhance 0, ocr (1500 + 1700) / 2 = 1600,
        vlm 3000 (empty cell skipped), total (1500 + 4700) / 2 = 3100.
    """
    write_csv(tmp_path / "ocr" / "ocr_summary.csv", OCR_HEADER,
              [["orig", 2, 4, 1, 0, 0.75, 0.5, 0.8125, 1, 0, 0],
               ["fixed", 2, 4, 1, 0, 1.0, 0.75, 0.9375, 0, 0, 0]])
    write_csv(tmp_path / "vlm" / "score.csv", SCORE_HEADER,
              [["orig", "fog_01", 4, 1, 4, 1, 2, 0.25, 25.0],
               ["orig", "fog_02", 6, 3, 6, 3, 1, 0.5, 50.0]])
    write_csv(tmp_path / "timing.csv", TIMING_HEADER,
              [["fog_01_3500.png", "orig", 0, 1500, "", 1500],
               ["fog_01_7000.png", "orig", 0, 1700, 3000, 4700]])

    out = aggregate(tmp_path)
    assert out == tmp_path / "summary.csv"
    s = read_summary(tmp_path)
    assert list(s) == ["orig", "fixed"]
    o = s["orig"]
    assert (o["plates"], o["detection_rate"], o["exact_match"], o["char_accuracy"]) == ("4", "0.75", "0.5", "0.8125")
    assert (o["overconfident"], o["readable_wrong"]) == ("1", "0")
    assert (o["vlm_scene_acc"], o["hallucination_rate"], o["uncheckable_claims"]) == ("0.4", "40.0", "3")
    assert (o["enhance_ms"], o["ocr_ms"], o["vlm_ms"], o["total_ms"]) == ("0.0", "1600.0", "3000.0", "3100.0")
    f = s["fixed"]  # OCR only: VLM and timing cells stay empty
    assert (f["exact_match"], f["vlm_scene_acc"], f["total_ms"]) == ("0.75", "", "")


def test_rates_only_are_averaged_and_na_skipped(tmp_path):
    """No count columns: scene acc (0.5 + 0.7) / 2 = 0.6, N/A skipped; all hallucination N/A -> empty.
    A row with counts mixed with one without also falls back to the mean of rates.
    """
    write_csv(tmp_path / "vlm" / "score.csv", ["condition", "clip", "scene_acc", "hallucination_rate"],
              [["fixed", "a", 0.5, "N/A"], ["fixed", "b", 0.7, "N/A"], ["fixed", "c", "N/A", "N/A"]])
    aggregate(tmp_path)
    f = read_summary(tmp_path)["fixed"]
    assert (f["vlm_scene_acc"], f["hallucination_rate"], f["uncheckable_claims"]) == ("0.6", "", "")

    write_csv(tmp_path / "vlm" / "score.csv", SCORE_HEADER,
              [["fixed", "a", 4, 1, 4, 1, 0, 0.25, 25.0], ["fixed", "b", "", "", "", "", "", 0.75, 15.0]])
    aggregate(tmp_path)
    f = read_summary(tmp_path)["fixed"]
    assert (f["vlm_scene_acc"], f["hallucination_rate"]) == ("0.5", "20.0")


def test_zero_denominators_give_empty(tmp_path):
    write_csv(tmp_path / "vlm" / "score.csv", SCORE_HEADER, [["orig", "a", 0, 0, 0, 0, 3, "N/A", "N/A"]])
    aggregate(tmp_path)
    o = read_summary(tmp_path)["orig"]
    assert (o["vlm_scene_acc"], o["hallucination_rate"], o["uncheckable_claims"]) == ("", "", "3")


def test_missing_sources_and_condition_order(tmp_path):
    out = aggregate(tmp_path / "empty")
    assert out.read_text(encoding="utf-8").splitlines() == [",".join(SUMMARY_COLUMNS)]

    write_csv(tmp_path / "timing.csv", TIMING_HEADER,
              [["x.png", "snow_test", 1, 2, 3, 6], ["x.png", "adaptive", 5, 2, 3, 10], ["x.png", "orig", 0, 2, 3, 5]])
    aggregate(tmp_path)
    s = read_summary(tmp_path)
    assert list(s) == ["orig", "adaptive", "snow_test"]
    assert (s["adaptive"]["enhance_ms"], s["adaptive"]["plates"], s["adaptive"]["vlm_scene_acc"]) == ("5.0", "", "")


def test_labels_rescore_plate_csvs(tmp_path):
    """With labels, ocr/<cond>.csv is scored again and a stale ocr_summary.csv is ignored."""
    write_csv(tmp_path / "ocr" / "ocr_summary.csv", OCR_HEADER, [["orig", 1, 1, 0, 0, 0.0, 0.0, 0.0, 0, 0, 0]])
    write_csv(tmp_path / "ocr" / "orig.csv", PLATE_HEADER,
              [["a.png", 0, 10, 10, 100, 30, "c.png", "12가3456", 0.95, "readable", 1500],
               ["b.png", "", "", "", "", "", "", "", "", "", 900]])
    labels = {"a.png": [{"bbox": [12, 10, 100, 30], "text": "12가3456"}], "b.png": []}
    aggregate(tmp_path, labels)
    o = read_summary(tmp_path)["orig"]
    assert (o["plates"], o["detection_rate"], o["exact_match"], o["char_accuracy"]) == ("1", "1.0", "1.0", "1.0")


def test_timing_per_condition_folders(tmp_path):
    """D's runner writes results/<cond>/timing.csv; a row without a condition takes the folder name."""
    write_csv(tmp_path / "timing.csv", TIMING_HEADER, [["x.png", "orig", 0, 2, "", 2]])
    write_csv(tmp_path / "fixed" / "timing.csv", TIMING_HEADER,
              [["x.png", "fixed", 4, 2, "", 6], ["y.png", "", 6, 2, "", 8]])
    write_csv(tmp_path / "adaptive" / "timing.csv", ["frame", "total_ms"], [["x.png", 9]])
    aggregate(tmp_path)
    s = read_summary(tmp_path)
    assert (s["orig"]["total_ms"], s["fixed"]["enhance_ms"], s["fixed"]["total_ms"], s["adaptive"]["total_ms"]) == \
        ("2.0", "5.0", "7.0", "9.0")

    write_csv(tmp_path / "timing.csv", TIMING_HEADER, [["x.png", "fixed", 0, 2, "", 2]])  # also in fixed/
    with pytest.raises(ValueError, match="twice"):
        aggregate(tmp_path)


def test_needs_condition_column(tmp_path):
    write_csv(tmp_path / "timing.csv", ["frame", "cond", "total_ms"], [["x.png", "orig", 5]])
    with pytest.raises(ValueError, match="condition"):
        aggregate(tmp_path)
