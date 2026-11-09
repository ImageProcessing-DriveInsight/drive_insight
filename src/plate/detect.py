"""Plate detection and recognition (stub)."""


def detect_plates(frame) -> list[dict]:
    """Detect and read license plates in one frame.

    Args:
        frame: np.ndarray, uint8, shape (H, W, 3), BGR.

    Returns:
        List of dicts with keys "bbox" (x, y, w, h), "crop_path", "text",
        "conf", "status" ("readable" | "uncertain" | "unreadable").
        Empty list if no plate is found.
    """
    # TODO(C-02~C-07): vehicle detection, plate candidates, preprocess, OCR, judge
    return []
