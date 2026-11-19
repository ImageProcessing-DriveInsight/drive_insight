from types import SimpleNamespace

import cv2
import numpy as np
import pytest

from src.plate.candidates import TOP_K, box_sums, detect_plate_candidates, grow_box, integral, iou
from src.plate.detect import WEIGHTS, detect_vehicles, own_car
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


def test_candidates_keep_four_per_vehicle():
    """Five plate-like patches on one car: four candidates are kept (#71). In fog a headlight and
    grille can outscore the plate, and in the rehearsal the plate was the 4th candidate."""
    img = np.full((480, 640, 3), 90, dtype=np.uint8)
    img[100:400, 100:540] = 60
    for x, y in ((120, 230), (330, 230), (120, 300), (330, 300), (225, 360)):
        img[y:y + 20, x:x + 90] = 230
        for cx in range(x + 6, x + 84, 11):
            img[y + 3:y + 17, cx:cx + 4] = 20
    assert TOP_K == 4
    assert len(detect_plate_candidates(img, VEHICLE)) == TOP_K


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


class FakeYolo:
    """Stands in for YOLO: predict returns the given xyxy boxes as cars, with optional masks."""

    def __init__(self, boxes, masks=None):
        self.boxes, self.masks = np.array(boxes, float), masks

    def predict(self, img, **kwargs):
        n = len(self.boxes)
        boxes = SimpleNamespace(xyxy=self.boxes, cls=np.full(n, 2.0), conf=np.full(n, 0.5))
        masks = None if self.masks is None else SimpleNamespace(
            data=SimpleNamespace(cpu=lambda: SimpleNamespace(numpy=lambda: self.masks)))
        return [SimpleNamespace(boxes=boxes, masks=masks)]


def test_own_car():
    assert own_car((3, 681, 1735, 382), 1920, 1080)  # a dashboard box from an own clip
    assert not own_car((500, 681, 900, 382), 1920, 1080)  # not wide enough
    assert not own_car((3, 400, 1735, 400), 1920, 1080)  # wide, but ends above the bottom band
    assert own_car((928, 824, 192, 74), 1920, 1080)  # a car reflected on the dashboard
    assert not own_car((700, 690, 300, 260), 1920, 1080)  # a near car: starts above the bottom quarter


def test_detect_vehicles_drops_the_camera_car(monkeypatch):
    import src.plate.detect as detect

    model = FakeYolo([[3, 681, 1738, 1063], [700, 500, 1000, 760], [928, 824, 1120, 898]])  # dashboard, car, reflection
    monkeypatch.setattr(detect, "_vehicle_model", lambda: model)
    assert [v["bbox"] for v in detect_vehicles(np.zeros((1080, 1920, 3), np.uint8))] == [(700, 500, 300, 260)]


def test_fog_masks_drop_the_camera_car(monkeypatch):
    import tools.synth_fog as synth_fog

    masks = np.zeros((2, 108, 192), np.float32)
    masks[0, 68:106, 0:174] = 1  # dashboard
    masks[1, 50:76, 70:100] = 1  # car ahead
    monkeypatch.setattr(synth_fog, "_seg_model", FakeYolo([[0, 68, 174, 106], [70, 50, 100, 76]], masks))
    kept = synth_fog.vehicle_masks(np.zeros((108, 192, 3), np.uint8))
    assert len(kept) == 1 and kept[0][60, 85] and not kept[0][90, 50]
