import csv
import json

import numpy as np
import pytest
from PIL import Image

from src.plate.imgutil import save_png
from tools.compare_images import (BAD, GOOD, HIDDEN, PART, PLATE_H, VEHICLE_H, change, collect, color, cover,
                                  hide_text, pick, plate_area, read_of, vehicle_pick, vehicle_read_of, vehicle_rows,
                                  write_images, write_vehicle_images)

H, W = 60, 100
HEADER = ["frame", "plate", "x", "y", "w", "h", "crop_path", "text", "conf", "status", "ocr_ms"]
LABELS = {"a.png": [{"bbox": [20, 20, 40, 12], "text": "12가3456"}],
          "b.png": [{"bbox": [30, 30, 40, 12], "text": "34나5678"}]}
READS = {  # frame -> (text, status); None = no plate found
    "orig": {"a.png": ("12가3400", "readable"), "b.png": ("34나5678", "readable")},
    "fixed": {"a.png": ("12가3456", "readable"), "b.png": None},
    "adaptive": {"a.png": ("12가3456", "readable"), "b.png": ("34나5670", "readable")},
}


@pytest.fixture
def run(tmp_path):
    labels = tmp_path / "plates.json"
    labels.write_text(json.dumps(LABELS, ensure_ascii=False), encoding="utf-8")
    for cond, reads in READS.items():
        rows = []
        for frame, read in reads.items():
            save_png(tmp_path / "frames" / cond / frame, np.full((H, W, 3), 200, np.uint8))
            if read is None:
                rows.append({"frame": frame})
            else:
                x, y, w, h = LABELS[frame][0]["bbox"]
                rows.append({"frame": frame, "plate": 0, "x": x, "y": y, "w": w, "h": h,
                             "text": read[0], "conf": 0.9, "status": read[1], "ocr_ms": 1})
        path = tmp_path / "results" / "ocr" / f"{cond}.csv"
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=HEADER, restval="")
            writer.writeheader()
            writer.writerows(rows)
    return tmp_path / "results", labels, tmp_path / "frames"


def test_hide_text():
    assert hide_text("12가3456", 2) == "12가34**" and hide_text("12", 5) == "**"
    assert hide_text(None, 2) is None and hide_text("12가3456", 0) == "12가3456"


def test_collect_and_pick(run):
    results, labels, _ = run
    conds, rows = collect(results, labels)
    assert conds == ["orig", "fixed", "adaptive"]
    a, b = sorted(rows, key=lambda r: r["frame"])
    assert a["bbox"] == (20, 20, 40, 12) and a["reads"]["fixed"]["text"] == "12가3456"
    assert change(a)[0] > 0 and change(b)[1] == pytest.approx(-1.0)  # fixed missed b
    assert pick(rows, 6) == ([a], [b]) and pick(rows, 0) == ([], [])
    # adaptive against fixed: a is exact in both; b missed in fixed, 34나5670 in adaptive (6/7)
    assert change(b, "fixed") == (pytest.approx(6 / 7), pytest.approx(6 / 7))
    assert pick(rows, 6, "fixed") == ([b], [])


def test_read_of_marks_confident_wrong_reads():
    exact = {"status": "readable", "text": "12가3456", "char_acc": 1.0}
    wrong = {"status": "readable", "text": "12가3400", "char_acc": 0.75}
    unsure = {"status": "uncertain", "text": "12?3456", "char_acc": 6 / 7}
    missed = {"status": None, "text": None, "char_acc": 0.0}
    assert (read_of(exact), color(exact)) == ("12가3456  1.00  readable", GOOD)
    assert (read_of(wrong), color(wrong)) == ("12가3400  0.75  readable, wrong", BAD)
    assert (read_of(unsure), color(unsure)) == ("12?3456  0.86  uncertain", PART)
    assert (read_of(missed), color(missed)) == ("missed  0.00", BAD)
    assert read_of({"status": "unreadable", "text": None, "char_acc": 0.0}) == "unreadable  0.00"
    assert read_of(wrong, hide=2) == "12가34**  0.75  readable, wrong"


def test_cover_and_plate_area():
    image = np.zeros((H, W, 3), np.uint8)
    cover(image, (20, 20, 40, 12), "12가3456", 2)  # right 2/7 of the box: columns 49..59
    assert tuple(image[25, 55]) == HIDDEN and tuple(image[25, 45]) == (0, 0, 0)
    assert tuple(image[19, 55]) == (0, 0, 0) and tuple(image[32, 55]) == (0, 0, 0)
    assert plate_area(image, (20, 20, 40, 12)).shape == (14, 48, 3)  # 10 % margin on each side
    assert plate_area(image, (90, 55, 40, 12)).shape == (6, 14, 3)  # clipped at the edges


def test_write_images(run, tmp_path):
    results, labels, frames = run
    paths = write_images(results, labels, frames, hide=2)
    figures = results / "figures"
    assert paths == [figures / "better.png", figures / "worse.png", figures / "better_vs_fixed.png",
                     figures / "frames" / "a.png", figures / "frames" / "b.png"]
    better = np.asarray(Image.open(paths[0]))
    assert better.shape[0] == 48 + PLATE_H + 34 + 2 * 12  # header and one row
    assert (better == HIDDEN).all(axis=-1).any()  # the hidden characters are covered
    frame_a = np.asarray(Image.open(paths[3]))
    assert frame_a.shape[1] == 3 * 640 + 2 * 12 and (frame_a == HIDDEN).all(axis=-1).any()


def test_frames_option_and_missing_conditions(run):
    results, labels, frames = run
    paths = write_images(results, labels, frames, top=0, frames=["b.png"])
    assert [p.name for p in paths] == ["b.png"]
    save_png(frames / "orig" / "c.png", np.zeros((H, W, 3), np.uint8))  # no label: drawn without boxes
    assert [p.name for p in write_images(results, labels, frames, top=0, frames=["c"])] == ["c.png"]
    with pytest.raises(ValueError, match="z.png"):
        write_images(results, labels, frames, frames=["z"])
    (results / "ocr" / "adaptive.csv").unlink()
    assert collect(results, labels)[0] == ["orig", "fixed"]
    assert not any("vs_fixed" in p.name for p in write_images(results, labels, frames))  # nothing after fixed
    (results / "ocr" / "orig.csv").unlink()
    with pytest.raises(FileNotFoundError):
        collect(results, labels)


def test_clear_reference_column(run):
    """ocr/clear.csv for a.png only: clear comes first, b.png has no clear read, and the lists still
    compare orig, fixed and adaptive."""
    results, labels, frames = run
    save_png(frames / "clear" / "a.png", np.full((H, W, 3), 220, np.uint8))
    x, y, w, h = LABELS["a.png"][0]["bbox"]
    with (results / "ocr" / "clear.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=HEADER, restval="")
        writer.writeheader()
        writer.writerow({"frame": "a.png", "plate": 0, "x": x, "y": y, "w": w, "h": h, "text": "12가3456",
                         "conf": 0.95, "status": "readable", "ocr_ms": 1})
    conds, rows = collect(results, labels)
    assert conds == ["clear", "orig", "fixed", "adaptive"]
    a, b = sorted(rows, key=lambda r: r["frame"])
    assert a["reads"]["clear"]["char_acc"] == 1.0 and b["reads"]["clear"] is None
    assert read_of(None) == "no clear frame"
    assert change(a) == (pytest.approx(2 / 7), pytest.approx(2 / 7))  # clear is not compared
    paths = write_images(results, labels, frames)
    frame_a = np.asarray(Image.open(results / "figures" / "frames" / "a.png"))
    assert frame_a.shape[1] == 4 * 640 + 3 * 12 and len(paths) == 5


VA, VB = [10, 10, 60, 40], [5, 5, 30, 20]  # labeled vehicles in a.png (around its plate) and b.png
SCENES = {"a.png": {"vehicles": [{"bbox": VA, "class": "car"}]}, "b.png": {"vehicles": [{"bbox": VB, "class": "car"}]}}
BOXES = {  # a: found, missed (near miss, IoU 1200 / 3600), found; b: missed, found, found
    "orig": {"a.png": [VA], "b.png": []},
    "fixed": {"a.png": [[40, 10, 60, 40]], "b.png": [VB]},
    "adaptive": {"a.png": [VA], "b.png": [VB]},
}


@pytest.fixture
def vehicles(run):
    results, labels, frames = run
    for cond, boxes in BOXES.items():
        path = results / "vehicles" / f"{cond}.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(boxes), encoding="utf-8")
    return results, labels, frames


def test_vehicle_rows_and_pick(vehicles):
    results, _, _ = vehicles
    conds, rows = vehicle_rows(results, SCENES)
    assert conds == ["orig", "fixed", "adaptive"]
    a, b = sorted(rows, key=lambda r: r["frame"])
    assert (a["frame"], a["bbox"]) == ("a", tuple(VA))
    assert vehicle_read_of(a["reads"]["fixed"]) == "missed  IoU 0.33"
    assert vehicle_read_of(b["reads"]["orig"]) == "missed" and vehicle_read_of(a["reads"]["orig"]) == "found  IoU 1.00"
    assert vehicle_pick(rows, 6) == ([b], [a])  # b found only after enhancement, a lost in fixed
    assert vehicle_pick(rows, 6, "fixed") == ([a], []) and vehicle_pick(rows, 0) == ([], [])


def test_write_vehicle_images(vehicles):
    results, labels, frames = vehicles
    paths = write_vehicle_images(results, SCENES, labels, frames, hide=2)
    figures = results / "figures"
    assert paths == [figures / "vehicles_better.png", figures / "vehicles_worse.png",
                     figures / "vehicles_better_vs_fixed.png"]
    worse = np.asarray(Image.open(paths[1]))  # a: found in orig and adaptive, missed in fixed
    assert worse.shape[0] == 48 + 12 + VEHICLE_H + 30 + 12  # header and one row
    assert (worse == GOOD).all(axis=-1).any() and (worse == BAD).all(axis=-1).any()
    assert (worse == HIDDEN).all(axis=-1).any()  # a's plate is inside the vehicle area and covered
    (results / "vehicles" / "fixed.json").unlink()
    (results / "vehicles" / "adaptive.json").unlink()
    assert write_vehicle_images(results, SCENES, labels, frames) == []  # orig alone: nothing to compare


def test_vehicle_clear_reference_column(vehicles):
    results, labels, frames = vehicles
    save_png(frames / "clear" / "a.png", np.full((H, W, 3), 220, np.uint8))
    (results / "vehicles" / "clear.json").write_text(json.dumps({"a.png": [VA]}), encoding="utf-8")
    conds, rows = vehicle_rows(results, SCENES)
    assert conds == ["clear", "orig", "fixed", "adaptive"]
    a, b = sorted(rows, key=lambda r: r["frame"])
    assert a["reads"]["clear"]["found"] and b["reads"]["clear"] is None
    assert vehicle_read_of(None) == "no clear frame"
    assert vehicle_pick(rows, 6) == ([b], [a])  # clear is not compared
    better = np.asarray(Image.open(write_vehicle_images(results, SCENES, labels, frames)[0]))
    assert better.shape[1] == 260 + 4 * (2 * VEHICLE_H + 12) + 12
