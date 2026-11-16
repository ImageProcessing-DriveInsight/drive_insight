import cv2
import numpy as np
import pytest

from src.plate.candidates import box_sums, detect_plate_candidates, grow_box, integral, iou
from src.plate.detect import WEIGHTS, detect_vehicles
from src.plate.imgutil import to_gray

PLATE = (250, 330, 110, 24)  # (x, y, w, h), about 4.5:1 like a long one-line plate


def car_frame():
    """Gray car body with a smooth bumper, a horizontal-line grille and a plate with dark characters."""
    img = np.full((480, 640, 3), 90, dtype=np.uint8)
    img[100:400, 100:540] = 60  # car body
    img[240:300:4, 150:490] = 160  # grille: horizontal lines only
    x, y, w, h = PLATE
    img[y:y + h, x:x + w] = 230  # plate background
    for cx in range(x + 8, x + w - 8, 13):  # characters as vertical strokes
        img[y + 4:y + h - 4, cx:cx + 5] = 20
    return img


VEHICLE = [{"bbox": (100, 100, 440, 300), "cls": "car", "conf": 0.9}]


def test_candidates_find_plate_first():
    cands = detect_plate_candidates(car_frame(), VEHICLE)
    assert cands and iou(cands[0], PLATE) >= 0.5


def test_candidates_without_vehicles_search_whole_frame():
    img = car_frame()
    cands = detect_plate_candidates(img, [])
    assert cands
    for x, y, w, h in cands:
        assert x >= 0 and y >= 0 and x + w <= img.shape[1] and y + h <= img.shape[0]
    assert any(iou(c, PLATE) >= 0.5 for c in cands)


def test_candidates_reject_bad_input():
    with pytest.raises(ValueError):
        detect_plate_candidates(np.zeros((10, 10), np.uint8), [])
    with pytest.raises(ValueError):
        detect_plate_candidates(np.zeros((10, 10, 3), np.float32), [])


def test_box_sums_match_brute_force():
    a = np.random.default_rng(0).random((12, 15))
    sums = box_sums(integral(a), 3, 4)
    assert sums.shape == (10, 12)
    assert np.isclose(sums[5, 7], a[5:8, 7:11].sum())


def test_grow_box_covers_dense_area():
    edge = np.zeros((40, 100), np.float32)
    edge[15:25, 10:60] = 1.0
    x, y, w, h = grow_box(edge, (28, 17, 24, 6))  # middle part of the dense area
    assert x <= 12 and x + w >= 58
    assert y <= 16 and y + h >= 24
    x, y, w, h = grow_box(edge, (30, 17, 10, 6))  # growth is capped at 2.5x the width
    assert w <= 25


def test_to_gray_matches_opencv():
    img = np.random.default_rng(1).integers(0, 256, (20, 30, 3), dtype=np.uint8)
    diff = np.abs(to_gray(img).astype(int) - cv2.cvtColor(img, cv2.COLOR_BGR2GRAY).astype(int))
    assert diff.max() <= 1


@pytest.mark.skipif(not WEIGHTS.exists(), reason="YOLO weights not downloaded")
def test_detect_vehicles_on_sample_image():
    from ultralytics.utils import ASSETS

    vehicles = detect_vehicles(cv2.imread(str(ASSETS / "bus.jpg")))
    assert any(v["cls"] == "bus" for v in vehicles)
    for v in vehicles:
        assert len(v["bbox"]) == 4 and all(isinstance(n, int) for n in v["bbox"])
        assert v["conf"] >= 0.4
    areas = [v["bbox"][2] * v["bbox"][3] for v in vehicles]
    assert areas == sorted(areas, reverse=True)
    with pytest.raises(ValueError):
        detect_vehicles(np.zeros((10, 10), np.uint8))
