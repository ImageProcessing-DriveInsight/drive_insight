import json

import numpy as np
import pytest

from src.plate.imgutil import load_png, save_png
from tools.b_labels import create_templates, export_plates, validate_annotations
from tools.label_draft import COLORS, check_images, draft, draw, fit, untouched

H, W = 60, 100


def fake_detector(frame):
    return ([{"bbox": (10, 5, 70, 50), "class": "car"}],
            [{"bbox": (30, 40, 30, 30), "status": None, "text": None}])  # runs past the bottom edge


@pytest.fixture
def labeling(tmp_path):
    frames = tmp_path / "frames"
    for name in ("a.png", "b.png"):
        save_png(frames / name, np.full((H, W, 3), 128, np.uint8))
    annotations = create_templates(frames, tmp_path / "scenes.json")
    return frames, annotations, tmp_path / "check"


def test_fit_clips_to_frame():
    assert fit((30, 40, 30, 30), W, H) == [30, 40, 30, 20]
    assert fit((-5, 2, 10, 10), W, H) == [0, 2, 5, 10]
    assert fit((120, 2, 10, 10), W, H) is None


def test_draft_fills_template_and_needs_a_person(labeling):
    frames, annotations, check = labeling
    assert draft(annotations, frames, check, detector=fake_detector) == ["a.png", "b.png"]
    data = json.loads(annotations.read_text(encoding="utf-8"))
    a = data["a.png"]
    assert a["vehicles"] == [{"bbox": [10, 5, 70, 50], "class": "car"}]
    assert a["plates"] == [{"bbox": [30, 40, 30, 20], "status": None, "text": None}]
    assert a["annotation_status"] == "pending" and not untouched(a)
    assert (check / "a.png").exists()
    with pytest.raises(ValueError):  # still pending, plate status empty
        validate_annotations(data)

    for entry in data.values():  # what the labeler does
        entry["plates"][0].update(status="readable", text="12가3456")
        entry.update(annotation_status="complete", annotator="C")
    validate_annotations(data)
    annotations.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    plates = json.loads(export_plates(annotations, annotations.parent / "plates.json", frames_dir=frames)
                        .read_text(encoding="utf-8"))
    assert plates["a.png"] == [{"bbox": [30, 40, 30, 20], "text": "12가3456"}]


def test_draft_never_changes_edited_entries(labeling):
    frames, annotations, check = labeling
    data = json.loads(annotations.read_text(encoding="utf-8"))
    data["a.png"]["plates"] = [{"bbox": [1, 1, 20, 8], "status": "unreadable", "text": None}]
    data["b.png"]["annotation_status"] = "complete"
    annotations.write_text(json.dumps(data), encoding="utf-8")
    assert draft(annotations, frames, check, detector=fake_detector) == []
    assert json.loads(annotations.read_text(encoding="utf-8")) == data
    assert draft(annotations, frames, check, detector=fake_detector) == []  # running again is safe


def test_draft_keeps_edits_made_while_it_runs(labeling):
    frames, annotations, check = labeling

    def detector_while_labeler_edits_b(frame):
        data = json.loads(annotations.read_text(encoding="utf-8"))
        data["b.png"]["annotator"] = "C"
        data["b.png"]["vehicles"] = [{"bbox": [0, 0, 5, 5], "class": "bus"}]
        annotations.write_text(json.dumps(data), encoding="utf-8")
        return fake_detector(frame)

    draft(annotations, frames, check, detector=detector_while_labeler_edits_b)
    b = json.loads(annotations.read_text(encoding="utf-8"))["b.png"]
    assert b["vehicles"] == [{"bbox": [0, 0, 5, 5], "class": "bus"}] and b["plates"] == []


def test_draft_rejects_wrong_frame_size(labeling):
    frames, annotations, check = labeling
    save_png(frames / "a.png", np.zeros((H + 1, W, 3), np.uint8))
    with pytest.raises(ValueError, match="a.png"):
        draft(annotations, frames, check, detector=fake_detector)


def test_draw_colors_boxes_by_status():
    frame = np.full((H, W, 3), 128, np.uint8)
    entry = {"vehicles": [{"bbox": [5, 30, 40, 25], "class": "car"}],
             "plates": [{"bbox": [60, 30, 30, 20], "status": None, "text": None}]}
    out = draw(frame, entry)
    assert out.shape == frame.shape and (frame == 128).all()  # the frame itself is not changed
    assert tuple(out[54, 20][::-1]) == COLORS["vehicle"]  # bottom edge of V0 (BGR -> RGB)
    assert tuple(out[49, 75][::-1]) == COLORS[None]  # bottom edge of P0, status still empty
    entry["plates"][0]["status"] = "unreadable"
    assert tuple(draw(frame, entry)[49, 75][::-1]) == COLORS["unreadable"]


def test_check_images(labeling):
    frames, annotations, check = labeling
    paths = check_images(annotations, frames, check, only=["b.png"])
    assert paths == [check / "b.png"] and load_png(paths[0]).shape == (H, W, 3)
