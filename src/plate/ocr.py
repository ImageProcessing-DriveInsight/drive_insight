"""Plate text reading with pretrained PaddleOCR (C-05).

The Korean model also reads Latin letters, so the same engine reads US plates (country "us").
"""

import re

import numpy as np

from .country import check_country

# Korean plates hold only digits and Hangul, so these Latin letters are digits misread
DIGIT_FIX = str.maketrans({"O": "0", "o": "0", "I": "1", "l": "1"})
MAIN_LINE = 0.7  # US: boxes at least this share of the tallest box height form the plate number line

_engine = None


def _ocr():
    global _engine
    if _engine is None:
        from paddleocr import PaddleOCR  # heavy import, load once

        _engine = PaddleOCR(
            lang="korean",
            use_doc_orientation_classify=False,
            use_doc_unwarping=False,
            use_textline_orientation=False,
            enable_mkldnn=False,  # paddlepaddle 3.3 CPU + oneDNN fails with NotImplementedError
        )
    return _engine


def normalize_text(text, country="kr"):
    """Korean: fix O/I misread as digits, then keep only digits and Hangul.
    US: upper case, then keep only letters and digits (O and I are plate letters there).
    """
    if check_country(country) == "us":
        return re.sub(r"[^0-9A-Z]", "", text.upper())
    return re.sub(r"[^0-9가-힣]", "", text.translate(DIGIT_FIX))


def join_lines(polys, texts, scores, country="kr"):
    """Join OCR boxes top-to-bottom, then left-to-right (two-line Korean plates).

    Boxes whose text is empty after normalize_text are dropped. For US plates only the line of
    the tallest box is kept, and in it only boxes at least MAIN_LINE as tall: the state name,
    slogans and stickers are smaller than the plate number.
    Returns (text, conf) where conf is the lowest score of the kept boxes, or ("", 0.0).
    """
    boxes = []
    for poly, text, score in zip(polys, texts, scores):
        text = normalize_text(text, country)
        if text:
            pts = np.asarray(poly, dtype=float).reshape(-1, 2)
            boxes.append((pts[:, 1].mean(), pts[:, 0].min(), np.ptp(pts[:, 1]), text, float(score)))
    if not boxes:
        return "", 0.0
    if country == "us":
        top = max(boxes, key=lambda b: b[2])
        boxes = [b for b in boxes if b[2] >= MAIN_LINE * top[2] and abs(b[0] - top[0]) < 0.5 * top[2]]
    boxes.sort()
    lines, line = [], [boxes[0]]
    for b in boxes[1:]:
        if abs(b[0] - line[-1][0]) < 0.5 * max(b[2], line[-1][2]):  # same line
            line.append(b)
        else:
            lines.append(line)
            line = [b]
    lines.append(line)
    text = "".join(b[3] for ln in lines for b in sorted(ln, key=lambda b: b[1]))
    return text, min(b[4] for b in boxes)


def recognize(crop, country="kr") -> tuple[str, float]:
    """Read plate text from a crop.

    Args:
        crop: uint8 BGR (H, W, 3) or gray (H, W), e.g. preprocess_plate output.
        country: "kr" or "us" (see src.plate.country).

    Returns:
        (text, conf): text holds only digits and Hangul ("kr") or digits and upper-case
        letters ("us"), conf is in [0, 1]. ("", 0.0) if nothing is read.
    """
    check_country(country)
    if not isinstance(crop, np.ndarray) or crop.dtype != np.uint8 or crop.ndim not in (2, 3):
        raise ValueError("crop must be a uint8 image")
    img = np.repeat(crop[..., None], 3, axis=2) if crop.ndim == 2 else crop
    res = _ocr().predict(img)[0]
    return join_lines(res["rec_polys"], res["rec_texts"], res["rec_scores"], country)
