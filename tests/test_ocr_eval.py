import csv
import json
import sys

import pytest

from src.eval import ocr as ev


def row(frame, x, y, w, h, text, status):
    return {"frame": frame, "x": x, "y": y, "w": w, "h": h, "text": text, "status": status}


def test_hand_case_1_mixed_reads():
    """One frame: an exact read, an uncertain read, and a confident read of an unreadable plate.

    detection 2/2 = 1.0, exact 1/2 = 0.5
    char accuracy: 12가3456 -> 1.0; 123?4567 vs 123나4567 -> 1 - 1/8 = 0.875; mean 0.9375
    overconfident 1 (readable answer on the unreadable plate)
    """
    labels = {"a.png": [{"bbox": [10, 10, 100, 30], "text": "12가3456"},
                        {"bbox": [200, 10, 100, 30], "text": "123나4567"},
                        {"bbox": [400, 10, 100, 30], "text": None}]}
    results = [row("a.png", 12, 10, 100, 30, "12가3456", "readable"),
               row("a.png", 205, 12, 100, 30, "123?4567", "uncertain"),
               row("a.png", 400, 10, 100, 30, "34다5678", "readable")]
    s = ev.eval_ocr(results, labels)
    assert (s["plates"], s["unreadable_labels"]) == (2, 1)
    assert s["detection_rate"] == 1.0 and s["exact_match"] == 0.5
    assert s["char_accuracy"] == pytest.approx(0.9375)
    assert (s["overconfident"], s["readable_wrong"]) == (1, 0)


def test_hand_case_2_miss_and_wrong_read():
    """Frame a: box off by 60 px, overlap 1200 / 3000 = 0.4 of the smaller box -> missed, char accuracy 0.
    Frame b: 56라7891 vs 56라7890 -> 1 - 1/7, readable but wrong.
    Frame c: no labeled plate, the prediction is ignored.

    detection 1/2 = 0.5, exact 0/2 = 0, char accuracy (0 + 6/7) / 2 = 3/7
    """
    labels = {"a.png": [{"bbox": [0, 0, 100, 30], "text": "12가3456"}],
              "b.png": [{"bbox": [0, 0, 100, 30], "text": "56라7890"}],
              "c.png": []}
    results = [row("a.png", 60, 0, 100, 30, "12가3456", "readable"),
               row("b.png", 0, 0, 100, 30, "56라7891", "readable"),
               row("c.png", 0, 0, 100, 30, "11가1111", "readable")]
    s = ev.eval_ocr(results, labels)
    assert s["detection_rate"] == 0.5 and s["exact_match"] == 0.0
    assert s["char_accuracy"] == pytest.approx(3 / 7)
    assert (s["overconfident"], s["readable_wrong"]) == (0, 1)
    assert ev.frame_char_accuracy(results, labels) == {"a": 0.0, "b": pytest.approx(6 / 7), "c": None}


def test_hand_case_3_one_to_one_highest_iou_first():
    """Plate A at x=0, plate B at x=90. Predictions: p1 x=5 (IoU 0.905 with A), p2 x=85 (0.905 with B),
    p3 x=0 (IoU 1.0 with A, wrong text). p3 takes A first, so p1 is left over (overlap 0.15 with B).

    A: 99가9999 vs 12가3456 -> 6 substitutions -> 1/7; B: exact -> 1
    detection 1.0, exact 0.5, char accuracy (1/7 + 1) / 2 = 4/7, readable_wrong 1
    """
    labels = {"a.png": [{"bbox": [0, 0, 100, 30], "text": "12가3456"},
                        {"bbox": [90, 0, 100, 30], "text": "34나5678"}]}
    results = [row("a.png", 5, 0, 100, 30, "12가3456", "readable"),
               row("a.png", 85, 0, 100, 30, "34나5678", "readable"),
               row("a.png", 0, 0, 100, 30, "99가9999", "readable")]
    s = ev.eval_ocr(results, labels)
    assert s["detection_rate"] == 1.0 and s["exact_match"] == 0.5
    assert s["char_accuracy"] == pytest.approx(4 / 7)
    assert s["readable_wrong"] == 1


def test_tighter_or_looser_box_still_matches():
    """Label box 160x40. A tight box inside it (IoU 0.32) and a loose box around it (IoU 0.33)
    both overlap all of the smaller box, so both reads count. A box half off the plate
    overlaps 0.4 of it and is missed.
    """
    label = {"bbox": [100, 100, 160, 40], "text": "12가3456"}
    tight = row("a.png", 130, 110, 100, 20, "12가3456", "readable")
    loose = row("b.png", 60, 80, 240, 80, "12가3456", "readable")
    off = row("c.png", 196, 100, 160, 40, "12가3456", "readable")
    assert ev.iou((130, 110, 100, 20), (100, 100, 160, 40)) == pytest.approx(0.3125)
    s = ev.eval_ocr([tight, loose, off], {"a.png": [label], "b.png": [label], "c.png": [label]})
    assert s["detection_rate"] == pytest.approx(2 / 3) and s["exact_match"] == pytest.approx(2 / 3)


def test_box_closest_in_size_wins():
    """A small box inside the plate and the plate box itself both qualify; the plate box has the
    higher IoU, so its read is scored and the small box is left over."""
    labels = {"a.png": [{"bbox": [0, 0, 100, 30], "text": "12가3456"}]}
    results = [row("a.png", 10, 5, 20, 10, "", "unreadable"),
               row("a.png", 2, 1, 98, 29, "12가3456", "readable")]
    assert ev.overlap((10, 5, 20, 10), (0, 0, 100, 30)) == 1.0
    s = ev.eval_ocr(results, labels)
    assert s["exact_match"] == 1.0


def test_edit_distance():
    assert ev.edit_distance("12가3456", "12가3456") == 0
    assert ev.edit_distance("12?3456", "12가3456") == 1
    assert ev.edit_distance("1234567", "123가4567") == 1
    assert ev.edit_distance("", "abc") == 3


def test_missing_frames_and_no_plates():
    s = ev.eval_ocr([row("b.png", 0, 0, 1, 1, "x", "readable")], {"a.png": [{"bbox": [0, 0, 9, 9], "text": None}]})
    assert s["missing_frames"] == 1 and s["plates"] == 0
    assert s["detection_rate"] is None and s["char_accuracy"] is None


def test_load_labels_from_folder(tmp_path):
    (tmp_path / "fog.json").write_text(json.dumps({"fog_01_100.png": [{"bbox": [1, 2, 3, 4], "text": "unreadable"}]}),
                                       encoding="utf-8")
    (tmp_path / "snow.json").write_text(json.dumps({"snow_01_100": [{"bbox": [1, 2, 3, 4], "text": "12가3456"}]}),
                                        encoding="utf-8")
    labels = ev.load_labels(tmp_path)
    assert labels == {"fog_01_100": [{"bbox": (1, 2, 3, 4), "text": None}],
                      "snow_01_100": [{"bbox": (1, 2, 3, 4), "text": "12가3456"}]}


def test_cli_writes_summary(tmp_path, monkeypatch):
    ocr_dir = tmp_path / "results" / "ocr"
    ocr_dir.mkdir(parents=True)
    with open(ocr_dir / "orig.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["frame", "plate", "x", "y", "w", "h", "crop_path", "text", "conf", "status", "ocr_ms"])
        w.writeheader()
        w.writerow({"frame": "a.png", "plate": 0, "x": 0, "y": 0, "w": 100, "h": 30, "text": "12가3456", "conf": 0.9,
                    "status": "readable"})
        w.writerow({"frame": "b.png"})
    (tmp_path / "labels.json").write_text(json.dumps({"a.png": [{"bbox": [0, 0, 100, 30], "text": "12가3456"}], "b.png": []}),
                                          encoding="utf-8")
    monkeypatch.setattr(sys, "argv", ["ocr", "--labels", str(tmp_path / "labels.json"), "--results", str(tmp_path / "results")])
    ev.main()
    rows = list(csv.DictReader(open(ocr_dir / "ocr_summary.csv", encoding="utf-8")))
    assert [r["condition"] for r in rows] == ["orig"]
    assert (rows[0]["frames"], rows[0]["exact_match"], rows[0]["missing_frames"]) == ("2", "1.0", "0")
