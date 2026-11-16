"""Vehicle detection (pretrained YOLOv8n) and the plate pipeline entry point."""

from pathlib import Path

from .imgutil import validate_frame

ROOT = Path(__file__).resolve().parents[2]
WEIGHTS = ROOT / "weights" / "yolov8n.pt"  # downloaded on first use, ignored by git
VEHICLE_CLASSES = {2: "car", 3: "motorcycle", 5: "bus", 7: "truck"}  # COCO class ids
VEHICLE_CONF = 0.4

_model = None


def _vehicle_model():
    global _model
    if _model is None:
        from ultralytics import YOLO  # heavy import, load once

        _model = YOLO(str(WEIGHTS))
    return _model


def detect_vehicles(img) -> list[dict]:
    """Detect cars, trucks, buses and motorcycles in one frame.

    Args:
        img: np.ndarray, uint8, shape (H, W, 3), BGR.

    Returns:
        List of {"bbox": (x, y, w, h), "cls": str, "conf": float},
        largest box first (usually the closest vehicle).
    """
    validate_frame(img)
    r = _vehicle_model().predict(img, conf=VEHICLE_CONF, classes=list(VEHICLE_CLASSES), verbose=False)[0]
    h, w = img.shape[:2]
    vehicles = []
    for (x1, y1, x2, y2), c, p in zip(r.boxes.xyxy.tolist(), r.boxes.cls.tolist(), r.boxes.conf.tolist()):
        x1, y1 = max(0, round(x1)), max(0, round(y1))
        x2, y2 = min(w, round(x2)), min(h, round(y2))
        if x2 > x1 and y2 > y1:
            vehicles.append({"bbox": (x1, y1, x2 - x1, y2 - y1), "cls": VEHICLE_CLASSES[int(c)], "conf": round(float(p), 4)})
    return sorted(vehicles, key=lambda v: v["bbox"][2] * v["bbox"][3], reverse=True)


def detect_plates(frame) -> list[dict]:
    """Detect and read license plates in one frame.

    Args:
        frame: np.ndarray, uint8, shape (H, W, 3), BGR.

    Returns:
        List of dicts with keys "bbox" (x, y, w, h), "crop_path", "text",
        "conf", "status" ("readable" | "uncertain" | "unreadable").
        Empty list if no plate is found.
    """
    # TODO(C-04~C-07): preprocess, OCR, judge
    return []
