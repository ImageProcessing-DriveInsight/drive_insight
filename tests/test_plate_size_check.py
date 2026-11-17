import numpy as np
import pytest

from tools.plate_size_check import (ROW_COLUMNS, area_weights, best_read, fog, jpeg, load_rows, low_light, make_row,
                                    motion_blur, paste_center, read_labels, shrink, summarize, write_rows)


def test_area_weights_rows_are_means():
    w = area_weights(5, 2)  # output pixels cover input [0, 2.5) and [2.5, 5)
    assert w.shape == (2, 5)
    assert w.sum(1) == pytest.approx([1, 1])
    assert w[0] == pytest.approx([0.4, 0.4, 0.2, 0, 0])
    assert w[1] == pytest.approx([0, 0, 0.2, 0.4, 0.4])


def test_shrink_averages_blocks():
    img = np.arange(16, dtype=np.uint8).reshape(4, 4) * 10
    out = shrink(img, 0.5)
    assert out.tolist() == [[25, 45], [105, 125]]  # mean of each 2x2 block
    color = np.dstack([img, img, img])
    assert shrink(color, 0.5).shape == (2, 2, 3)
    assert (shrink(color, 0.5)[..., 1] == out).all()
    assert (shrink(img, 1.5) == img).all()


def test_shrink_keeps_flat_image_flat():
    img = np.full((37, 91, 3), 77, np.uint8)
    out = shrink(img, 0.31)
    assert out.shape == (11, 28, 3) and (out == 77).all()


def test_fog_and_low_light():
    img = np.array([[0, 100, 200]], np.uint8)
    assert (fog(img, t=1.0) == img).all()
    assert fog(img, t=0.0, airlight=220).tolist() == [[220, 220, 220]]
    assert fog(img, t=0.5, airlight=200).tolist() == [[100, 150, 200]]  # contrast halved
    assert low_light(img, k=0.2, noise=0.0).tolist() == [[0, 20, 40]]
    noisy = low_light(np.full((50, 50), 100, np.uint8), k=0.5, noise=3.0, rng=np.random.default_rng(1))
    assert abs(noisy.mean() - 50) < 0.5 and 2 < noisy.std() < 4


def test_motion_blur():
    img = np.zeros((1, 9), np.uint8)
    img[0, 4] = 250
    assert motion_blur(img, 5).tolist() == [[0, 0, 50, 50, 50, 50, 50, 0, 0]]
    flat = np.full((4, 6, 3), 90, np.uint8)
    assert (motion_blur(flat, 4) == 90).all()
    assert (motion_blur(img, 1) == img).all()


def test_jpeg_and_paste_center():
    img = np.full((20, 30, 3), 128, np.uint8)
    assert np.abs(jpeg(img).astype(int) - 128).max() <= 2
    frame = paste_center(img, size=(40, 50), fill=0)
    assert frame.shape == (40, 50, 3)
    assert (frame[10:30, 10:40] == 128).all() and frame.sum() == img.sum()
    big = paste_center(np.full((60, 70, 3), 5, np.uint8), size=(40, 50))
    assert (big == 5).all()


def test_best_read_and_summary():
    label = "12가3456"
    plates = [{"text": "99나9999", "status": "readable", "conf": 0.9},
              {"text": "12가3457", "status": "uncertain", "conf": 0.6}]
    assert best_read(plates, label)[:2] == ("12가3457", "uncertain")
    assert best_read([], label) == (None, "missed", 0.0, 0.0)

    def row(test, width, text, status, vehicles=None):
        return {"test": test, "variant": "clean", "width": width, "exact": text == label, "status": status,
                "char_acc": 1.0 if text == label else 0.5, "vehicles": vehicles}

    rows = [row("frame", 60, label, "readable", 1), row("frame", 60, "12가3457", "readable", 1),
            row("frame", 60, None, "missed", 0), row("frame", 30, None, "missed", 0)]
    s60, s30 = summarize(rows)
    assert (s60["width"], s60["n"], s60["exact"], s60["readable"], s60["readable_wrong"], s60["missed"]) == \
        (60, 3, 1, 2, 1, 1)
    assert s60["char_acc"] == pytest.approx(2 / 3) and s60["vehicles_found"] == 2
    assert (s30["n"], s30["exact"], s30["vehicles_found"]) == (1, 0, 0)


def test_rows_round_trip(tmp_path):
    rows = [make_row("crop", "a", "fog", 60, 58, None, "12가3456", ("12가3456", "readable", 0.91, 1.0), 300.0),
            make_row("frame", "a", "clean", 40, 41, 2, "12가3456", (None, "missed", 0.0, 0.0), 900.0)]
    path = write_rows(tmp_path / "size.csv", ROW_COLUMNS, rows)
    assert summarize(load_rows(path)) == summarize(rows)


def test_read_labels_cp949(tmp_path):
    path = tmp_path / "labels.csv"
    path.write_bytes("file,text\na.png,12가3456\n".encode("cp949"))
    assert read_labels(path) == {"a": "12가3456"}
