"""OCR evaluation (stub)."""

OCR_METRICS = ["detection_rate", "exact_match", "char_accuracy", "overconfident"]


def eval_ocr(results, labels) -> dict:
    """Score OCR results of one condition against ground-truth labels.

    Args:
        results: detect_plates outputs per frame.
        labels: ground-truth plates per frame.

    Returns:
        Dict with keys in OCR_METRICS.
    """
    # TODO(C-09): IoU matching, exact match, 1 - edit distance / length
    return {
        "detection_rate": 0.0,
        "exact_match": 0.0,
        "char_accuracy": 0.0,
        "overconfident": 0,
    }
