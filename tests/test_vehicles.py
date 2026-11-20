import csv
import json

import numpy as np
import pytest

from src.eval.vehicles import COLUMNS, detect_frames, load_vehicles, match, rate_rows, size_of, write_rates
from src.plate.imgutil import save_png

V1, V2, V3, V4 = [0, 0, 50, 40], [100, 0, 150, 100], [300, 0, 250, 150], [0, 0, 120, 80]
SCENES = {
    "a.png": {"annotation_status": "complete", "vehicles": [{"bbox": V1, "class": "car"}, {"bbox": V2, "class": "car"},
                                                            {"bbox": V3, "class": "truck"}]},
    "b.png": {"annotation_status": "complete", "vehicles": [{"bbox": V4, "class": "car"}]},
    "c.png": {"annotation_status": "pending", "vehicles": [{"bbox": V1, "class": "car"}]},
}
# orig: finds V1 (IoU 0.84) and V3, misses V2 and V4, and one box that is no labeled vehicle
ORIG = {"a.png": [[2, 2, 50, 40], V3, [600, 600, 80, 40]], "b.png": []}


def test_load_vehicles_skips_pending_frames():
    assert load_vehicles(SCENES) == {"a.png": [V1, V2, V3], "b.png": [V4]}


def test_match_is_one_to_one_largest_iou_first():
    labels = [[0, 0, 100, 100], [10, 0, 100, 100]]
    assert match([[10, 0, 100, 100]], labels) == {1: 0}  # IoU 1.0 beats 0.82
    assert match([[10, 0, 100, 100], [0, 0, 100, 100]], labels) == {1: 0, 0: 1}
    assert match([[60, 0, 100, 100]], [[0, 0, 100, 100]]) == {}  # IoU 0.25


def test_size_bins():
    assert [size_of([0, 0, w, 10]) for w in (36, 99, 100, 199, 200, 759)] == [
        "<100", "<100", "100-199", "100-199", ">=200", ">=200"]


def test_rate_rows_by_hand():
    rows = {r["size"]: r for r in rate_rows("orig", ORIG, load_vehicles(SCENES))}
    assert list(rows) == ["all", "<100", "100-199", ">=200"]
    assert [rows["all"][k] for k in ("frames", "labeled", "found", "unmatched")] == [2, 4, 2, 1]
    assert rows["all"]["rate"] == 0.5
    assert [rows["<100"][k] for k in ("labeled", "found", "unmatched", "rate")] == [1, 1, 1, 1.0]
    assert [rows["100-199"][k] for k in ("labeled", "found", "rate")] == [2, 0, 0.0]  # V2, V4
    assert [rows[">=200"][k] for k in ("labeled", "found", "rate")] == [1, 1, 1.0]


def test_detect_and_write_rates(tmp_path):
    for name in ("a.png", "b.png"):
        save_png(tmp_path / "frames" / "orig" / name, np.zeros((20, 20, 3), np.uint8))
    save_png(tmp_path / "frames" / "clear" / "a.png", np.zeros((20, 20, 3), np.uint8))
    results = tmp_path / "results"
    detections = {"orig": ORIG, "clear": {"a.png": [V1, V2, V3]}}

    for cond in ("orig", "clear"):
        frames = iter(sorted(detections[cond]))
        fake = lambda img, c=cond, f=frames: [{"bbox": tuple(b), "cls": "car", "conf": 0.9}
                                              for b in detections[c][next(f)]]
        path = detect_frames(cond, tmp_path / "frames" / cond, results, detect=fake)
        assert json.loads(path.read_text(encoding="utf-8")) == detections[cond]

    scenes = tmp_path / "scenes.json"
    scenes.write_text(json.dumps(SCENES), encoding="utf-8")
    out = write_rates(results, scenes)
    rows = list(csv.DictReader(open(out, encoding="utf-8")))
    assert list(rows[0]) == COLUMNS
    assert [(r["condition"], r["size"]) for r in rows][::4] == [("orig", "all"), ("clear", "all")]
    assert (rows[0]["rate"], rows[4]["frames"], rows[4]["rate"]) == ("0.5", "1", "1.0")  # clear: its own frame only
    assert rows[6]["rate"] == "1.0" and rows[2]["rate"] == "0.0"


def test_write_rates_needs_detections(tmp_path):
    with pytest.raises(FileNotFoundError):
        write_rates(tmp_path, SCENES)
