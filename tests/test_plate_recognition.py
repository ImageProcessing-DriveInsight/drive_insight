from pathlib import Path

import cv2
import numpy as np
import pytest

from src.plate.judge import REGIONS, USE_CHARS, fit_with_one_fix, judge
from src.plate.ocr import join_lines, normalize_text
from src.plate.preprocess import (TARGET_H, contrast_stretch, estimate_skew, otsu, preprocess_plate,
                                  resize_bilinear, rotate_bilinear)


def text_line(h=64, w=240):
    """Light background with dark vertical strokes, like a row of characters."""
    img = np.full((h, w), 230, np.uint8)
    for x in range(20, w - 20, 22):
        img[22:44, x:x + 8] = 20
    return img


@pytest.mark.parametrize("size", [(64, 150), (20, 40), (100, 300)])
def test_resize_matches_opencv(size):
    img = np.random.default_rng(0).integers(0, 256, (37, 91, 3), dtype=np.uint8)
    oh, ow = size
    ref = cv2.resize(img, (ow, oh), interpolation=cv2.INTER_LINEAR)
    assert np.abs(resize_bilinear(img, oh, ow).astype(int) - ref.astype(int)).max() <= 1


def test_otsu_matches_opencv():
    g = np.random.default_rng(1).integers(0, 256, (50, 80), dtype=np.uint8)
    t_ref, b_ref = cv2.threshold(g, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    b, t = otsu(g)
    assert t == t_ref and np.array_equal(b, b_ref)


def test_contrast_stretch():
    g = np.random.default_rng(2).integers(100, 140, (30, 30), dtype=np.uint8)
    out = contrast_stretch(g)
    assert out.min() == 0 and out.max() == 255
    flat = np.full((5, 5), 77, np.uint8)
    assert np.array_equal(contrast_stretch(flat), flat)


@pytest.mark.parametrize("angle", [-8, -3, 0, 5, 9])
def test_deskew_recovers_rotation(angle):
    rotated = rotate_bilinear(text_line(), angle)
    assert abs(estimate_skew(rotated) + angle) <= 0.5


def test_preprocess_output():
    crop = cv2.cvtColor(255 - text_line(32, 120), cv2.COLOR_GRAY2BGR)  # light text on dark, like green plates
    out = preprocess_plate(crop)
    assert out.dtype == np.uint8 and out.shape == (TARGET_H, 240)
    assert np.median(out) > 128  # background turned light
    assert set(np.unique(preprocess_plate(crop, binarize=True))) <= {0, 255}
    with pytest.raises(ValueError):
        preprocess_plate(np.zeros((10, 10, 3), np.float32))


def test_normalize_text():
    assert normalize_text("12가 34-56") == "12가3456"
    assert normalize_text("I2가 345O") == "12가3450"


def test_join_lines_orders_two_line_plate():
    polys = [[[10, 60], [90, 60], [90, 90], [10, 90]],  # lower line
             [[40, 10], [80, 10], [80, 40], [40, 40]],  # upper line, right part
             [[5, 12], [38, 12], [38, 38], [5, 38]]]  # upper line, left part
    assert join_lines(polys, ["가3456", "12", "서울"], [0.9, 0.95, 0.7]) == ("서울12가3456", 0.7)
    assert join_lines([[[0, 0], [1, 0], [1, 1], [0, 1]]], ["-"], [0.9]) == ("", 0.0)


@pytest.mark.parametrize("text, conf, expected", [
    ("12가3456", 0.95, ("readable", "12가3456")),
    ("123가4567", 0.80, ("readable", "123가4567")),
    ("서울12가3456", 0.90, ("readable", "서울12가3456")),
    ("12가3456", 0.70, ("uncertain", "12가3456")),
    ("1273456", 0.99, ("uncertain", "12?3456")),
    ("12345678", 0.99, ("uncertain", "123?5678")),
    ("123456", 0.90, ("uncertain", "12?3456")),
    ("12가34567", 0.90, ("unreadable", None)),
    ("12가3456", 0.40, ("unreadable", None)),
    ("", 0.90, ("unreadable", None)),
    ("가나다", 0.90, ("unreadable", None)),
    ("12바3456", 0.90, ("readable", "12바3456")),  # commercial
    ("12배3456", 0.90, ("readable", "12배3456")),  # parcel delivery
    ("123허4567", 0.90, ("readable", "123허4567")),  # rental
    ("부산12아3456", 0.90, ("readable", "부산12아3456")),
    ("12에3456", 0.95, ("uncertain", "12?3456")),  # not a plate character: an OCR misread
    ("123케4567", 0.95, ("uncertain", "123?4567")),  # carmaker advertising plate
    ("서올12바3456", 0.90, ("uncertain", "서?12바3456")),  # misread region
    ("가나12가3456", 0.90, ("unreadable", None)),  # not a region, no single fix
])
def test_judge(text, conf, expected):
    assert judge(text, conf) == expected


def test_plate_characters():
    assert len(USE_CHARS) == len(set(USE_CHARS)) == 32 + 4 + 1 + 3
    assert len(REGIONS) == len(set(REGIONS)) == 17
    for ch in "에년시지케차":
        assert ch not in USE_CHARS


def test_fit_with_one_fix_never_fills_characters():
    fitted = fit_with_one_fix("1273456")
    assert fitted == "12?3456" and "가" not in fitted


FONT = Path(r"C:\Windows\Fonts\malgun.ttf")


@pytest.mark.skipif(not FONT.exists(), reason="Korean font not available")
def test_recognize_rendered_plate():
    pytest.importorskip("paddleocr")
    from PIL import Image, ImageDraw, ImageFont

    from src.plate.ocr import recognize

    img = Image.new("RGB", (520, 110), "white")
    draw = ImageDraw.Draw(img)
    draw.rectangle([2, 2, 517, 107], outline="black", width=4)
    draw.text((260, 55), "12가3456", font=ImageFont.truetype(str(FONT), 80), fill="black", anchor="mm")
    crop = cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)
    text, conf = recognize(preprocess_plate(crop))
    assert judge(text, conf) == ("readable", "12가3456")


def test_normalize_text_us():
    assert normalize_text("7abc-123", "us") == "7ABC123"
    assert normalize_text("KDE 482O", "us") == "KDE482O"  # O and I are plate letters in the US
    assert normalize_text("12가3456", "us") == "123456"
    with pytest.raises(ValueError):
        normalize_text("7ABC123", "jp")


def test_join_lines_us_keeps_the_plate_number_line():
    """State name above and slogan below are smaller than the number; a split number is joined."""
    polys = [[[40, 5], [160, 5], [160, 25], [40, 25]],  # "California", 20 px tall
             [[100, 35], [190, 35], [190, 95], [100, 95]],  # "C123", right part of the number
             [[10, 38], [95, 38], [95, 92], [10, 92]],  # "7AB", left part, 54 px tall
             [[50, 100], [150, 100], [150, 115], [50, 115]]]  # "dmv.ca.gov"
    texts, scores = ["California", "C123", "7AB", "dmv.ca.gov"], [0.6, 0.97, 0.9, 0.5]
    assert join_lines(polys, texts, scores, "us") == ("7ABC123", 0.9)
    assert join_lines(polys, ["", "", "", ""], scores, "us") == ("", 0.0)
    assert join_lines(polys, texts, scores)[0] == "1071230"  # Korean rules: l/o become digits, letters dropped


@pytest.mark.parametrize("text, conf, expected", [
    ("7ABC123", 0.95, ("readable", "7ABC123")),  # California
    ("KDE4821", 0.80, ("readable", "KDE4821")),  # New York
    ("A12BCD", 0.90, ("readable", "A12BCD")),  # New Jersey
    ("123456", 0.90, ("readable", "123456")),  # Delaware: digits only
    ("7ABC123", 0.70, ("uncertain", "7ABC123")),
    ("GOBEARS", 0.95, ("unreadable", None)),  # vanity plate: no digit
    ("7ABC1234", 0.95, ("unreadable", None)),  # 8 characters, no position can be marked
    ("AB12", 0.95, ("unreadable", None)),
    ("7ABC123", 0.40, ("unreadable", None)),
    ("12가3456", 0.95, ("unreadable", None)),
])
def test_judge_us(text, conf, expected):
    assert judge(text, conf, "us") == expected


ARIAL = Path(r"C:\Windows\Fonts\arialbd.ttf")


@pytest.mark.skipif(not ARIAL.exists(), reason="Arial font not available")
def test_recognize_rendered_us_plate():
    pytest.importorskip("paddleocr")
    from PIL import Image, ImageDraw, ImageFont

    from src.plate.ocr import recognize

    img = Image.new("RGB", (600, 300), "white")
    draw = ImageDraw.Draw(img)
    draw.rectangle([3, 3, 596, 296], outline="black", width=5)
    draw.text((300, 55), "California", font=ImageFont.truetype(str(ARIAL), 48), fill=(180, 20, 20), anchor="mm")
    draw.text((300, 160), "7ABC123", font=ImageFont.truetype(str(ARIAL), 140), fill=(20, 40, 140), anchor="mm")
    draw.text((300, 260), "dmv.ca.gov", font=ImageFont.truetype(str(ARIAL), 30), fill=(20, 40, 140), anchor="mm")
    crop = cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)
    text, conf = recognize(preprocess_plate(crop), "us")
    assert judge(text, conf, "us") == ("readable", "7ABC123")
