"""Vehicle detection (pretrained YOLOv8n) and the plate pipeline entry point."""

import hashlib
from pathlib import Path

from .candidates import detect_plate_candidates, iou
from .country import check_country
from .imgutil import save_png, validate_frame
from .judge import judge
from .ocr import recognize
from .preprocess import preprocess_plate

ROOT = Path(__file__).resolve().parents[2]
RESULTS = ROOT / "results"
WEIGHTS = ROOT / "weights" / "yolov8n.pt"  # downloaded on first use, ignored by git
VEHICLE_CLASSES = {2: "car", 3: "motorcycle", 5: "bus", 7: "truck"}  # COCO class ids
VEHICLE_CONF = 0.4
OWN_CAR_WIDTH = 0.6  # share of the frame width
OWN_CAR_BOTTOM = 0.95  # share of the frame height, from the top
OWN_CAR_TOP = 0.75  # share of the frame height: a box starting below this row is on the dashboard
DUPLICATE_IOU = 0.5  # the threshold YOLO uses within one class when predicting
CROP_MARGIN = 0.1  # border added around a candidate before OCR and saving
STATUS_RANK = {"readable": 2, "uncertain": 1, "unreadable": 0}

_model = None


def _vehicle_model():
    global _model
    if _model is None:
        from ultralytics import YOLO  # heavy import, load once

        _model = YOLO(str(WEIGHTS))
    return _model


def own_car(box, width, height):
    """True for the camera car's own hood or dashboard, or a reflection on it, which YOLO calls a car.

    Either a box at least OWN_CAR_WIDTH of the frame wide whose bottom reaches the bottom 5 %
    of the frame, or a box that starts in the bottom quarter. On 11 own dashcam clips every
    wide box reaching the bottom (0.84-0.99 of the width, bottom at rows 1055-1066 of 1080,
    just above the dashcam's text strip) was the dashboard, and every box starting in the bottom
    quarter (rows 821-837) was a car reflected on it. No real vehicle started below row 700:
    a vehicle that close rises above the hood (#78).
    """
    x, y, w, h = box
    return (w >= OWN_CAR_WIDTH * width and y + h >= OWN_CAR_BOTTOM * height) or y >= OWN_CAR_TOP * height


def drop_duplicates(vehicles, threshold=DUPLICATE_IOU):
    """One box per vehicle: of boxes overlapping at IoU > threshold, keep the most confident.

    YOLO suppresses overlapping boxes within one class only, so a vehicle seen as both car and
    truck came out twice (IoU 0.92-1.0; 9 of 231 vehicles in the clear frames of the own clips,
    #88), and its plate was searched and read twice.
    """
    kept = []
    for v in sorted(vehicles, key=lambda v: v["conf"], reverse=True):
        if all(iou(v["bbox"], k["bbox"]) <= threshold for k in kept):
            kept.append(v)
    return kept


def detect_vehicles(img) -> list[dict]:
    """Detect cars, trucks, buses and motorcycles in one frame, without the camera car itself.

    Args:
        img: np.ndarray, uint8, shape (H, W, 3), BGR.

    Returns:
        List of {"bbox": (x, y, w, h), "cls": str, "conf": float}, one per vehicle
        (see drop_duplicates), largest box first (usually the closest vehicle).
    """
    validate_frame(img)
    r = _vehicle_model().predict(img, conf=VEHICLE_CONF, classes=list(VEHICLE_CLASSES), verbose=False)[0]
    h, w = img.shape[:2]
    vehicles = []
    for (x1, y1, x2, y2), c, p in zip(r.boxes.xyxy.tolist(), r.boxes.cls.tolist(), r.boxes.conf.tolist()):
        x1, y1 = max(0, round(x1)), max(0, round(y1))
        x2, y2 = min(w, round(x2)), min(h, round(y2))
        if x2 > x1 and y2 > y1 and not own_car((x1, y1, x2 - x1, y2 - y1), w, h):
            vehicles.append({"bbox": (x1, y1, x2 - x1, y2 - y1), "cls": VEHICLE_CLASSES[int(c)], "conf": round(float(p), 4)})
    return sorted(drop_duplicates(vehicles), key=lambda v: v["bbox"][2] * v["bbox"][3], reverse=True)


def padded_crop(frame, box, margin=CROP_MARGIN):
    x, y, w, h = box
    x0, y0 = max(0, round(x - margin * w)), max(0, round(y - margin * h))
    x1, y1 = min(frame.shape[1], round(x + w + margin * w)), min(frame.shape[0], round(y + h + margin * h))
    return frame[y0:y1, x0:x1]


def read_plate(crop, country="kr"):
    """preprocess -> OCR -> judge. Returns (status, text, conf)."""
    text, conf = recognize(preprocess_plate(crop), country)
    status, text = judge(text, conf, country)
    return status, text, round(conf, 4)


def relative(path):
    path = Path(path)
    try:
        return path.resolve().relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def detect_plates(frame, cond=None, frame_id=None, results_dir=None, country="kr") -> list[dict]:
    """Detect and read license plates in one frame: one result per vehicle.

    For each vehicle, its plate candidates are read in order until one is
    readable; the best read (status, then conf) is kept. Its padded crop is saved
    to <results_dir>/ocr/crops/<cond>/<frame_id>_<n>.png.

    Args:
        frame: np.ndarray, uint8, shape (H, W, 3), BGR.
        cond: condition name for the crop folder ("orig", "fixed", "adaptive").
            Defaults to "misc".
        frame_id: crop file name prefix, e.g. "<clip>_<ms>". Defaults to a hash
            of the frame, so the same frame always gets the same name.
        results_dir: defaults to <project>/results.
        country: plate country, "kr" or "us" (see src.plate.country).

    Returns:
        List of {"bbox": (x, y, w, h), "crop_path": str, "text": str | None,
        "conf": float, "status": "readable" | "uncertain" | "unreadable"}.
        Empty list if no plate candidate is found. crop_path is relative to the
        project root when it is inside it.
    """
    validate_frame(frame)
    check_country(country)
    crop_dir = Path(results_dir or RESULTS) / "ocr" / "crops" / (cond or "misc")
    frame_id = frame_id or hashlib.sha1(frame.tobytes()).hexdigest()[:12]

    vehicles = detect_vehicles(frame)
    groups = [detect_plate_candidates(frame, [v]) for v in vehicles] or [detect_plate_candidates(frame, [])]
    plates = []
    for candidates in groups:
        best = None
        for box in candidates:  # best candidate first
            crop = padded_crop(frame, box)
            status, text, conf = read_plate(crop, country)
            if best is None or (STATUS_RANK[status], conf) > (STATUS_RANK[best[1]], best[3]):
                best = (box, status, text, conf, crop)
            if status == "readable":
                break
        if best is None or any(iou(best[0], p["bbox"]) >= 0.5 for p in plates):
            continue  # no candidate, or the same plate as an overlapping vehicle
        box, status, text, conf, crop = best
        path = crop_dir / f"{frame_id}_{len(plates)}.png"
        save_png(path, crop)
        plates.append({"bbox": tuple(box), "crop_path": relative(path), "text": text, "conf": conf, "status": status})
    return plates
