import csv

import pytest

from src.eval.compare import CASE_COLUMNS, TABLE_COLUMNS, compare, write_compare
from src.eval.ocr import frame_char_accuracy, plate_details

PLATE_HEADER = ["frame", "plate", "x", "y", "w", "h", "crop_path", "text", "conf", "status", "ocr_ms"]
BOX = [0, 0, 100, 30]


def plate(frame, text, status, cond):
    return [frame, 0, *BOX, f"results/ocr/crops/{cond}/{frame[:-4]}_0.png", text, 0.9, status, 1500]


def no_plate(frame):
    return [frame, "", "", "", "", "", "", "", "", "", 900]


def write_csv(path, header, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(header)
        writer.writerows(rows)


LABELS = {
    "a.png": [{"bbox": BOX, "text": "12가3456"}],
    "b.png": [{"bbox": BOX, "text": "34나5678"}],
    "c.png": [{"bbox": BOX, "text": "56다7890"}],
    "d.png": [],                                    # no plate
    "e.png": [{"bbox": BOX, "text": None}],         # plate not readable by eye
    "f.png": [{"bbox": BOX, "text": "78라1234"}],   # missing from fixed.csv
}


def write_fake(tmp_path):
    write_csv(tmp_path / "ocr" / "orig.csv", PLATE_HEADER,
              [plate("a.png", "12가3456", "readable", "orig"), plate("b.png", "34나567", "uncertain", "orig"),
               plate("c.png", "56다7890", "readable", "orig"), no_plate("d.png"),
               plate("e.png", "11가1111", "readable", "orig"), plate("f.png", "78라1234", "readable", "orig")])
    write_csv(tmp_path / "ocr" / "fixed.csv", PLATE_HEADER,
              [plate("a.png", "12가3456", "readable", "fixed"), plate("b.png", "34나5678", "readable", "fixed"),
               plate("c.png", "56다7899", "readable", "fixed"), no_plate("d.png"),
               plate("e.png", "11가1111", "readable", "fixed")])


def test_hand_case_orig_to_fixed(tmp_path):
    """orig -> fixed, char accuracy per frame:
    a 1 -> 1 unchanged; b 34나567 -> 6/7, then exact 1: better; c exact 1 -> 56다7899 6/7: worse.
    d, e have no readable labeled plate; f is missing from fixed.csv.
    frames 3 = better 1 + worse 1 + unchanged 1. adaptive.csv is missing, so that pair has no counts.

    summary.csv: exact_match 0.5 -> 0.75 -> 0.8, total_ms 4100 -> 3985; hallucination missing for fixed.
    """
    write_fake(tmp_path)
    write_csv(tmp_path / "summary.csv", ["condition", "exact_match", "hallucination_rate", "total_ms"],
              [["orig", 0.5, 30.0, 4100], ["fixed", 0.75, "", 3985], ["adaptive", 0.8, 10.0, 4010]])
    table, cases = compare(tmp_path, LABELS)

    first, second = table
    assert (first["base"], first["target"]) == ("orig", "fixed")
    assert [first[k] for k in ("frames", "better", "worse", "unchanged", "no_readable_label", "missing")] == [3, 1, 1, 1, 2, 1]
    assert first["better"] + first["worse"] + first["unchanged"] == first["frames"]
    assert first["delta_exact_match"] == pytest.approx(0.25)
    assert first["delta_total_ms"] == pytest.approx(-115)
    assert first["delta_hallucination_rate"] is None and first["delta_detection_rate"] is None

    assert (second["base"], second["target"], second["frames"], second["worse"]) == ("fixed", "adaptive", None, None)
    assert second["delta_exact_match"] == pytest.approx(0.05)

    assert len(cases) == 1
    c = cases[0]
    assert (c["base"], c["target"], c["frame"], c["label"]) == ("orig", "fixed", "c", "56다7890")
    assert (c["base_text"], c["base_char_acc"], c["base_crop"]) == ("56다7890", 1.0, "results/ocr/crops/orig/c_0.png")
    assert (c["target_text"], c["target_status"], c["target_char_acc"]) == ("56다7899", "readable", pytest.approx(6 / 7))
    assert c["target_crop"] == "results/ocr/crops/fixed/c_0.png"


def test_missed_plate_and_mixed_frame(tmp_path):
    """Frame g, two plates: orig reads P exactly and misses Q; adaptive misses P and reads Q exactly.
    Mean 0.5 in both -> unchanged, no worse case. Frame h: read in fixed, missed in adaptive -> worse,
    the case has no target text or crop. Worse cases are sorted by the drop, largest first:
    h drops 1.0, i drops 1/7.
    """
    labels = {"g.png": [{"bbox": [0, 0, 100, 30], "text": "12가3456"}, {"bbox": [300, 0, 100, 30], "text": "34나5678"}],
              "h.png": [{"bbox": BOX, "text": "56다7890"}],
              "i.png": [{"bbox": BOX, "text": "78라1234"}]}
    rows_fixed = [["g.png", 0, 0, 0, 100, 30, "fg.png", "12가3456", 0.9, "readable", 1],
                  plate("h.png", "56다7890", "readable", "fixed"), plate("i.png", "78라1234", "readable", "fixed")]
    rows_adaptive = [["g.png", 0, 300, 0, 100, 30, "ag.png", "34나5678", 0.9, "readable", 1],
                     no_plate("h.png"), plate("i.png", "78라1235", "readable", "adaptive")]
    write_csv(tmp_path / "ocr" / "fixed.csv", PLATE_HEADER, rows_fixed)
    write_csv(tmp_path / "ocr" / "adaptive.csv", PLATE_HEADER, rows_adaptive)
    table, cases = compare(tmp_path, labels)

    first, second = table
    assert first["frames"] is None  # orig.csv missing
    assert [second[k] for k in ("frames", "better", "worse", "unchanged")] == [3, 0, 2, 1]
    assert [c["frame"] for c in cases] == ["h", "i"]
    h = cases[0]
    assert (h["target_text"], h["target_status"], h["target_crop"], h["target_char_acc"]) == (None, None, None, 0.0)


def test_plate_details_match_frame_char_accuracy(tmp_path):
    write_fake(tmp_path)
    for cond in ("orig", "fixed"):
        path = tmp_path / "ocr" / f"{cond}.csv"
        details, frames = plate_details(path, LABELS), frame_char_accuracy(path, LABELS)
        for frame, plates in details.items():
            mean = sum(p["char_acc"] for p in plates) / len(plates) if plates else None
            assert mean == pytest.approx(frames[frame]) if plates else frames[frame] is None
    assert "f" not in plate_details(tmp_path / "ocr" / "fixed.csv", LABELS)


def test_write_compare_files(tmp_path):
    write_fake(tmp_path)
    table_path, cases_path = write_compare(tmp_path, LABELS)
    with open(table_path, encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    assert list(rows[0]) == TABLE_COLUMNS
    assert [rows[0][k] for k in ("frames", "better", "worse", "unchanged")] == ["3", "1", "1", "1"]
    assert rows[1]["frames"] == "" and rows[0]["delta_exact_match"] == ""  # no adaptive.csv, no summary.csv
    with open(cases_path, encoding="utf-8") as f:
        cases = list(csv.DictReader(f))
    assert list(cases[0]) == CASE_COLUMNS
    assert (cases[0]["frame"], cases[0]["target_char_acc"]) == ("c", "0.8571")
