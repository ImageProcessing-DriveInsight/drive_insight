import csv

import numpy as np
import pytest

import src.plate.detect as detect
import src.plate.run as run
from src.plate.candidates import iou
from src.plate.imgutil import save_png

PLATE = (250, 330, 110, 24)
VEHICLE = {"bbox": (100, 100, 440, 300), "cls": "car", "conf": 0.9}
KEYS = {"bbox", "crop_path", "text", "conf", "status"}


def car_frame():
    img = np.full((480, 640, 3), 90, dtype=np.uint8)
    img[100:400, 100:540] = 60
    x, y, w, h = PLATE
    img[y:y + h, x:x + w] = 230
    for cx in range(x + 8, x + w - 8, 13):
        img[y + 4:y + h - 4, cx:cx + 5] = 20
    return img


@pytest.fixture
def fake_models(monkeypatch):
    """Replace YOLO and PaddleOCR; reads returns the next (text, conf) and counts calls."""
    state = {"reads": [("12가3456", 0.95)], "calls": 0}
    monkeypatch.setattr(detect, "detect_vehicles", lambda frame: [VEHICLE])

    def fake_recognize(crop, country="kr"):
        state["calls"] += 1
        state["country"] = country
        return state["reads"][min(state["calls"], len(state["reads"])) - 1]

    monkeypatch.setattr(detect, "recognize", fake_recognize)
    return state


def test_detect_plates_result(tmp_path, fake_models):
    plates = detect.detect_plates(car_frame(), cond="orig", frame_id="clip_100", results_dir=tmp_path)
    assert len(plates) == 1
    p = plates[0]
    assert set(p) == KEYS
    assert (p["status"], p["text"], p["conf"]) == ("readable", "12가3456", 0.95)
    assert iou(p["bbox"], PLATE) >= 0.5
    assert (tmp_path / "ocr" / "crops" / "orig" / "clip_100_0.png").exists()
    assert p["crop_path"].endswith("ocr/crops/orig/clip_100_0.png")


def test_detect_plates_stops_at_first_readable(tmp_path, fake_models):
    detect.detect_plates(car_frame(), results_dir=tmp_path)
    assert fake_models["calls"] == 1


def test_detect_plates_keeps_best_read(tmp_path, fake_models):
    fake_models["reads"] = [("", 0.0), ("1273456", 0.9), ("12가3456", 0.6)]
    p = detect.detect_plates(car_frame(), results_dir=tmp_path)[0]
    assert fake_models["calls"] == 3
    assert (p["status"], p["text"]) == ("uncertain", "12?3456")  # same rank: higher conf wins


def test_detect_plates_unreadable(tmp_path, fake_models):
    fake_models["reads"] = [("", 0.0)]
    p = detect.detect_plates(car_frame(), results_dir=tmp_path)[0]
    assert (p["status"], p["text"]) == ("unreadable", None)


def test_default_crop_name_is_stable(tmp_path, fake_models):
    a = detect.detect_plates(car_frame(), results_dir=tmp_path)[0]["crop_path"]
    b = detect.detect_plates(car_frame(), results_dir=tmp_path)[0]["crop_path"]
    assert a == b and "/crops/misc/" in a


def test_run_ocr_lists_every_frame(tmp_path, monkeypatch):
    frames = tmp_path / "frames"
    save_png(frames / "clip_100.png", car_frame())
    save_png(frames / "clip_200.png", np.zeros((48, 64, 3), np.uint8))
    plate = {"bbox": PLATE, "crop_path": "c.png", "text": None, "conf": 0.1, "status": "unreadable"}
    monkeypatch.setattr(run, "detect_plates", lambda frame, cond, frame_id, results_dir: [plate] if frame_id == "clip_100" else [])

    out = run.run_ocr("orig", frames_dir=frames, results_dir=tmp_path / "results")
    assert out == tmp_path / "results" / "ocr" / "orig.csv"
    rows = list(csv.DictReader(open(out, encoding="utf-8")))
    assert [r["frame"] for r in rows] == ["clip_100.png", "clip_200.png"]
    assert list(rows[0]) == run.COLUMNS
    assert (rows[0]["status"], rows[0]["text"], rows[0]["x"]) == ("unreadable", "", str(PLATE[0]))
    assert rows[1]["status"] == "" and rows[1]["plate"] == ""


def test_run_ocr_rejects_bad_input(tmp_path):
    with pytest.raises(ValueError):
        run.run_ocr("night", frames_dir=tmp_path)
    with pytest.raises(FileNotFoundError):
        run.run_ocr("orig", frames_dir=tmp_path)


def test_detect_plates_passes_the_country(tmp_path, fake_models):
    fake_models["reads"] = [("7ABC123", 0.95)]
    p = detect.detect_plates(car_frame(), results_dir=tmp_path, country="us")[0]
    assert fake_models["country"] == "us"
    assert (p["status"], p["text"]) == ("readable", "7ABC123")
    assert detect.detect_plates(car_frame(), results_dir=tmp_path)[0]["status"] == "unreadable"  # Korean rules
    with pytest.raises(ValueError):
        detect.detect_plates(car_frame(), results_dir=tmp_path, country="jp")


def test_run_ocr_uses_the_country_of_each_frame(tmp_path, monkeypatch):
    frames = tmp_path / "frames"
    for name in ("bdd_01_100", "fog_01_100"):
        save_png(frames / f"{name}.png", car_frame())
    seen = {}

    def fake_detect(frame, cond, frame_id, results_dir, **kw):
        seen[frame_id] = kw
        return []

    monkeypatch.setattr(run, "detect_plates", fake_detect)
    run.run_ocr("orig", frames_dir=frames, results_dir=tmp_path / "results", countries={"us": ["bdd_*"]})
    assert seen == {"bdd_01_100": {"country": "us"}, "fog_01_100": {}}  # Korean frames: same call as before


def test_run_ocr_reads_the_clear_reference(tmp_path, monkeypatch):
    frames = tmp_path / "frames" / "clear"
    save_png(frames / "fog_01_100.png", np.zeros((48, 64, 3), np.uint8))
    seen = []
    monkeypatch.setattr(run, "detect_plates", lambda frame, cond, frame_id, results_dir: seen.append(cond) or [])
    out = run.run_ocr("clear", frames_dir=frames, results_dir=tmp_path / "results")
    assert out == tmp_path / "results" / "ocr" / "clear.csv" and seen == ["clear"]
