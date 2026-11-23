import json

import cv2
import numpy as np
import pytest

from tools.audit_night_data import audit_dataset, main


def dataset(tmp_path, *, group=False, wrong_name=False, width=120):
    root = tmp_path / "야간"
    images, labels = root / "images/Clip_000", root / "labels/Clip_000"
    images.mkdir(parents=True)
    labels.mkdir(parents=True)
    _, encoded = cv2.imencode(".jpg", np.full((20, width, 3), 40, np.uint8))
    encoded.tofile(images / "frame.jpg")
    label = {"imagePath": "other.jpg" if wrong_name else "frame.jpg", "imageWidth": width,
             "imageHeight": 20, "shapes": [{"label": "car", "points": [[0, 0], [width, 20]]}]}
    if group:
        label["shapes"].append({"label": "cargroup", "points": [[1, 1], [5, 5]]})
    (labels / "frame.json").write_text(json.dumps(label), encoding="utf-8")
    return root


def test_complete_decode_and_no_mutation(tmp_path):
    root = dataset(tmp_path)
    before = {str(p): p.read_bytes() for p in root.rglob("*") if p.is_file()}
    report = audit_dataset(root, decode_images=True)
    assert report["summary"] == dict(images=1, labels=1, paired_valid=1, scenes=1,
                                      group_frames=0, complete_frames=1, issues=0)
    assert report["frames"][0]["has_vehicle_width_ge_100"] is True
    assert report["capture_timing"] == "unknown" and report["selection_status"] == "not_selected"
    assert before == {str(p): p.read_bytes() for p in root.rglob("*") if p.is_file()}


@pytest.mark.parametrize("group,width,expected", [(True, 120, False), (False, 99, False), (False, 100, True)])
def test_c_group_and_width_rules(tmp_path, group, width, expected):
    report = audit_dataset(dataset(tmp_path, group=group, width=width))
    assert report["frames"][0]["has_vehicle_width_ge_100"] is expected


def test_missing_orphan_and_wrong_name(tmp_path):
    root = dataset(tmp_path, wrong_name=True)
    (root / "labels/Clip_000/orphan.json").write_text("{}")
    (root / "images/Clip_000/unpaired.jpg").write_bytes(b"bad")
    report = audit_dataset(root)
    assert report["summary"]["issues"] == 3


def test_bad_label_and_optional_decode(tmp_path):
    root = dataset(tmp_path)
    image = root / "images/Clip_000/frame.jpg"
    image.write_bytes(b"corrupt")
    assert audit_dataset(root)["summary"]["issues"] == 0
    assert audit_dataset(root, decode_images=True)["summary"]["issues"] == 1
    (root / "labels/Clip_000/frame.json").write_text("{broken")
    assert audit_dataset(root)["summary"]["issues"] == 1


def test_cli_report_refuses_overwrite_and_source_output(tmp_path):
    root, out = dataset(tmp_path), tmp_path / "audit.json"
    assert main(["--root", str(root), "--output", str(out)]) == 0
    assert json.loads(out.read_text(encoding="utf-8"))["summary"]["paired_valid"] == 1
    with pytest.raises(SystemExit) as exc:
        main(["--root", str(root), "--output", str(out)])
    assert exc.value.code == 2
    with pytest.raises(SystemExit):
        main(["--root", str(root), "--output", str(root / "audit.json")])


def test_missing_root(tmp_path):
    with pytest.raises(ValueError, match="Missing dataset"):
        audit_dataset(tmp_path)
