"""AI Hub vehicle labels -> scenes file (#90). Synthetic label files only, no AI Hub data."""

import json
import subprocess
import sys

import pytest

from src.eval.vehicles import load_vehicles, rate_rows
from tools.aihub_vehicles import ROOT, bbox, convert, load_names, scene_entry, summary


def labelme(shapes, width="1920", height="1080", image="..\\images\\Clip_000\\a.jpg"):
    """71588 / 630 style. 630 writes the image size as strings."""
    return {"imagePath": image, "imageWidth": width, "imageHeight": height, "imageData": None,
            "shapes": [{"label": cls, "points": points, "shape_type": "polygon"} for cls, points in shapes]}


def polygon(annotations, image="s_01.jpg", resolution=(1920, 1080)):
    """71570 / 71930 style: flat [x1, y1, x2, y2, ...]."""
    return {"information": {"filename": image, "resolution": list(resolution)},
            "annotations": [{"class": cls, "polygon": flat} for cls, flat in annotations]}


def write(folder, name, label):
    folder.mkdir(parents=True, exist_ok=True)
    (folder / name).write_text(json.dumps(label), encoding="utf-8")


def test_labelme_keeps_vehicles_only():
    entry = scene_entry(labelme([
        ("car", [[100, 200], [300, 200], [300, 350], [100, 350]]),
        ("truck", [[500, 100], [800, 120], [700, 400]]),
        ("ego vehicle", [[0, 900], [1920, 900], [1920, 1080]]),
        ("pedestrian", [[10, 10], [20, 10], [20, 40]]),
        ("road", [[0, 600], [1920, 600], [1920, 1080]]),
    ]), "a.json")
    assert entry == {"annotation_status": "complete", "vehicles": [
        {"bbox": [100, 200, 200, 150], "class": "car"}, {"bbox": [500, 100, 300, 300], "class": "truck"}]}


def test_polygon_format_flat_coordinates():
    entry = scene_entry(polygon([
        ("vehicle", [10, 20, 110, 20, 110, 80, 10, 80]),
        ("policeCar", [200, 200, 260, 210, 250, 260]),
        ("whiteLane", [0, 500, 900, 520, 900, 530]),
        ("background", [0, 0, 1920, 0, 1920, 400]),
    ]), "s_01.json")
    assert entry["vehicles"] == [{"bbox": [10, 20, 100, 60], "class": "vehicle"},
                                 {"bbox": [200, 200, 60, 60], "class": "policeCar"}]


def test_boxes_are_clipped_and_empty_boxes_dropped():
    assert bbox([(1900, 1000), (2000, 1000), (2000, 1100), (1900, 1100)], (1920, 1080)) == [1900, 1000, 20, 80]
    assert bbox([(-5, 10), (40, 10), (40, 30)], (1920, 1080)) == [0, 10, 40, 20]
    assert bbox([(50, 50), (50, 50), (50, 50)], (1920, 1080)) is None
    assert bbox([(2000, 10), (2100, 10), (2100, 30)], (1920, 1080)) is None  # wholly outside
    entry = scene_entry(labelme([("car", [[5, 5], [5, 5], [5, 5]])]), "a.json")
    assert entry["vehicles"] == []


def test_group_label_leaves_the_frame_out():
    entry = scene_entry(labelme([("car", [[0, 0], [50, 0], [50, 40]]),
                                 ("cargroup", [[100, 0], [400, 0], [400, 100]])]), "a.json")
    assert entry["annotation_status"] == "group"
    assert load_vehicles({"a.png": entry}) == {}


def test_frame_without_vehicles_counts_its_detections_as_unmatched():
    entry = scene_entry(labelme([("road", [[0, 600], [1920, 600], [1920, 1080]])]), "a.json")
    assert entry == {"annotation_status": "complete", "vehicles": []}
    rows = rate_rows("orig", {"a.png": [[10, 10, 120, 80]]}, load_vehicles({"a.png": entry}))
    assert (rows[0]["labeled"], rows[0]["found"], rows[0]["unmatched"], rows[0]["rate"]) == (0, 0, 1, None)


def test_convert_names_frames_by_image_stem(tmp_path):
    write(tmp_path / "night" / "Clip_000", "x.json", labelme([("car", [[0, 0], [50, 0], [50, 40]])], image="..\\img\\a.jpg"))
    write(tmp_path / "day", "y.json", polygon([("bus", [0, 0, 300, 0, 300, 200])], image="s_01.jpg"))
    write(tmp_path / "day", "z.json", {k: v for k, v in polygon([]).items() if k != "information"})
    scenes, skipped = convert([tmp_path / "night", tmp_path / "day"])
    assert sorted(scenes) == ["a.png", "s_01.png", "z.png"]  # no file name in the label: the JSON's stem
    assert scenes["a.png"]["vehicles"] == [{"bbox": [0, 0, 50, 40], "class": "car"}]
    assert skipped == 0


def test_convert_with_a_names_csv(tmp_path):
    write(tmp_path / "labels", "a.json", labelme([("car", [[0, 0], [50, 0], [50, 40]])], image="a.jpg"))
    write(tmp_path / "labels", "b.json", labelme([], image="b.jpg"))
    names = tmp_path / "names.csv"
    names.write_text("source,frame\nC:\\data\\a.jpg,night_0001.png\n", encoding="utf-8")
    scenes, skipped = convert([tmp_path / "labels"], load_names(names))
    assert list(scenes) == ["night_0001.png"] and skipped == 1
    bad = tmp_path / "bad.csv"
    bad.write_text("image,png\na.jpg,a.png\n", encoding="utf-8")
    with pytest.raises(ValueError, match="source, frame"):
        load_names(bad)


def test_convert_refuses_two_labels_for_one_frame(tmp_path):
    write(tmp_path / "one", "a.json", labelme([], image="a.jpg"))
    write(tmp_path / "two", "a.json", labelme([], image="a.jpg"))
    with pytest.raises(ValueError, match="comes from both"):
        convert([tmp_path / "one", tmp_path / "two"])


def test_bad_labels_raise(tmp_path):
    with pytest.raises(ValueError, match="odd number"):
        scene_entry(polygon([("vehicle", [0, 0, 10, 0, 10])]), "s.json")
    with pytest.raises(ValueError, match="neither"):
        scene_entry({"objects": []}, "s.json")
    with pytest.raises(FileNotFoundError):
        convert([tmp_path])


def test_summary_by_hand():
    scenes = {
        "a.png": {"annotation_status": "complete", "vehicles": [{"bbox": [0, 0, 50, 40], "class": "car"},
                                                                {"bbox": [0, 0, 250, 150], "class": "truck"}]},
        "b.png": {"annotation_status": "complete", "vehicles": [{"bbox": [0, 0, 120, 80], "class": "car"}]},
        "c.png": {"annotation_status": "group", "vehicles": [{"bbox": [0, 0, 60, 40], "class": "car"}]},
    }
    assert summary(scenes) == ("3 frames (2 complete, 1 with a group label left out); 3 vehicles in complete frames "
                               "{'car': 2, 'truck': 1}; width <100 px 1, 100-199 px 1, >=200 px 1")


def test_command_line(tmp_path):
    write(tmp_path / "labels", "a.json", labelme([("car", [[0, 0], [150, 0], [150, 90]])], image="a.jpg"))
    out = tmp_path / "scenes.json"
    done = subprocess.run([sys.executable, str(ROOT / "tools" / "aihub_vehicles.py"), str(tmp_path / "labels"),
                           "--out", str(out)], capture_output=True, text=True, check=True)
    assert "1 frames (1 complete" in done.stdout
    assert load_vehicles(out) == {"a.png": [[0, 0, 150, 90]]}
