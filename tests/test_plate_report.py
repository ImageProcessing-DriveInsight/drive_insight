import csv
import json

import numpy as np
import pytest

from src.plate.imgutil import save_png
from src.plate.run import COLUMNS
from tools.plate_report import check_frames, frame_names, report

H, W = 60, 100
LABEL = {"bbox": [20, 20, 40, 12], "text": "12가3456"}
READS = {"orig": "12가3400", "fixed": "12가3456", "adaptive": "12가3400", "clear": "12가3456"}


def fake_ocr(cond, frames_dir, results_dir):
    """Writes ocr/<cond>.csv like run_ocr: one plate per frame, read as READS[cond]."""
    path = results_dir / "ocr" / f"{cond}.csv"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=COLUMNS, restval="")
        w.writeheader()
        for p in sorted(frames_dir.glob("*.png")):
            x, y, bw, bh = LABEL["bbox"]
            w.writerow({"frame": p.name, "plate": 0, "x": x, "y": y, "w": bw, "h": bh, "text": READS[cond],
                        "conf": 0.9, "status": "readable", "ocr_ms": 1000})
    return path


@pytest.fixture
def setup(tmp_path):
    frames = tmp_path / "frames"
    for cond in ("orig", "fixed", "adaptive"):
        for name in ("a.png", "b.png"):
            save_png(frames / cond / name, np.full((H, W, 3), 200, np.uint8))
    save_png(frames / "clear" / "a.png", np.full((H, W, 3), 220, np.uint8))
    labels = tmp_path / "plates.json"
    labels.write_text(json.dumps({"a.png": [LABEL], "b.png": []}, ensure_ascii=False), encoding="utf-8")
    return frames, tmp_path / "results", labels


def test_frame_names_and_checks(setup):
    frames, _, _ = setup
    names = frame_names(frames)
    assert list(names) == ["orig", "fixed", "adaptive", "clear"] and names["clear"] == ["a.png"]
    check_frames(names)
    with pytest.raises(ValueError, match="fixed"):
        check_frames({**names, "fixed": ["a.png"]})
    with pytest.raises(ValueError, match="clear"):
        check_frames({**names, "clear": ["z.png"]})
    with pytest.raises(ValueError, match="orig"):
        check_frames({"fixed": ["a.png"]})


def test_report_runs_the_whole_chain(setup):
    frames, results, labels = setup
    seen = []

    def ocr(cond, frames_dir, results_dir):
        seen.append(cond)
        return fake_ocr(cond, frames_dir, results_dir)

    out = report(frames, results, labels, ocr=ocr, log=lambda *a: None)
    assert seen == ["orig", "fixed", "adaptive", "clear"]
    rows = {r["condition"]: r for r in csv.DictReader(open(out["ocr_summary"], encoding="utf-8"))}
    assert list(rows) == ["orig", "fixed", "adaptive", "clear"]
    assert (rows["fixed"]["exact_match"], rows["clear"]["frames"]) == ("1.0", "1")  # clear: its own frame only
    summary = {r["condition"]: r for r in csv.DictReader(open(out["summary"], encoding="utf-8"))}
    assert summary["orig"]["ocr_ms"] == "1000.0"  # step times from the OCR CSV (no timing file)
    compare = list(csv.DictReader(open(out["compare"], encoding="utf-8")))
    assert [(r["base"], r["target"], r["better"], r["worse"]) for r in compare] == [
        ("orig", "fixed", "1", "0"), ("fixed", "adaptive", "0", "1")]
    assert {p.name for p in out["figures"]} >= {"better.png", "worse_vs_fixed.png", "a.png"}


def test_report_stops_before_ocr_on_mismatched_frames(setup):
    frames, results, labels = setup
    (frames / "adaptive" / "b.png").unlink()
    with pytest.raises(ValueError, match="adaptive"):
        report(frames, results, labels, ocr=lambda *a: pytest.fail("OCR ran"), log=lambda *a: None)
    assert not (results / "ocr").exists()


def test_report_adds_the_vehicle_rate(setup, tmp_path):
    frames, results, labels = setup
    scenes = tmp_path / "scenes.json"
    scenes.write_text(json.dumps({"a.png": {"annotation_status": "complete", "vehicles": [{"bbox": [10, 10, 60, 40]}]},
                                  "b.png": {"annotation_status": "complete", "vehicles": []}}), encoding="utf-8")
    out = report(frames, results, labels, ocr=fake_ocr, log=lambda *a: None, scenes=scenes,
                 detect=lambda img: [{"bbox": (10, 10, 60, 40), "cls": "car", "conf": 0.9}])
    rows = [r for r in csv.DictReader(open(out["vehicles"], encoding="utf-8")) if r["size"] == "all"]
    assert [(r["condition"], r["frames"], r["rate"], r["unmatched"]) for r in rows] == [
        ("orig", "2", "1.0", "1"), ("fixed", "2", "1.0", "1"), ("adaptive", "2", "1.0", "1"), ("clear", "1", "1.0", "0")]
    compare = list(csv.DictReader(open(out["vehicle_compare"], encoding="utf-8")))
    assert [(r["labeled"], r["gained"], r["lost"], r["both"]) for r in compare] == [("1", "0", "0", "1")] * 2
    assert not any(p.name.startswith("vehicles_") for p in out["figures"])  # no vehicle changed
    out = report(frames, results, labels, skip_ocr=True, log=lambda *a: None)  # no scenes
    assert out["vehicles"] is None and out["vehicle_compare"] is None


def test_report_compares_vehicles(setup, tmp_path):
    """fixed/a.png darker: the fake detector misses its vehicle, so fixed loses it and adaptive gains it back."""
    frames, results, labels = setup
    save_png(frames / "fixed" / "a.png", np.full((H, W, 3), 150, np.uint8))
    scenes = tmp_path / "scenes.json"
    scenes.write_text(json.dumps({"a.png": {"vehicles": [{"bbox": [10, 10, 60, 40]}]}, "b.png": {"vehicles": []}}),
                      encoding="utf-8")
    detect = lambda img: [{"bbox": (10, 10, 60, 40), "cls": "car", "conf": 0.9}] if img[0, 0, 0] == 200 else []  # noqa: E731
    out = report(frames, results, labels, ocr=fake_ocr, log=lambda *a: None, scenes=scenes, detect=detect)
    compare = list(csv.DictReader(open(out["vehicle_compare"], encoding="utf-8")))
    assert [(r["base"], r["gained"], r["lost"]) for r in compare] == [("orig", "0", "1"), ("fixed", "1", "0")]
    names = {p.name for p in out["figures"]}
    assert {"vehicles_worse.png", "vehicles_better_vs_fixed.png"} <= names and "vehicles_better.png" not in names
    changes = list(csv.DictReader(open(results / "vehicles" / "changes.csv", encoding="utf-8")))
    assert [(c["change"], c["frame"]) for c in changes] == [("lost", "a.png"), ("gained", "a.png")]


def test_skip_ocr_reuses_the_csvs(setup):
    frames, results, labels = setup
    for cond in ("orig", "fixed"):
        fake_ocr(cond, frames / cond, results)
    out = report(frames, results, labels, skip_ocr=True, ocr=lambda *a: pytest.fail("OCR ran"), log=lambda *a: None)
    assert [p.name for p in out["ocr"]] == ["orig.csv", "fixed.csv"]
    assert [r["condition"] for r in csv.DictReader(open(out["ocr_summary"], encoding="utf-8"))] == ["orig", "fixed"]
