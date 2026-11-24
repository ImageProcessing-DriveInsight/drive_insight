import csv
import hashlib
import json
from pathlib import Path

import cv2
import numpy as np
import pytest

from src.dip import FIXED_PARAMS, fixed_enhance
from src.io.video import load_frame
from tools.review_night_tuning import candidates, load_tuning_rows, run_review


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


@pytest.fixture
def inputs(tmp_path):
    root, manifests = tmp_path / "dataset", tmp_path / "manifests"
    manifests.mkdir()
    selected = dict(normal=[f"Clip_{i:03}" for i in range(5)], hard=["Clip_005", "Clip_006"])
    fields = ["split", "condition", "scene", "difficulty", "source", "frame"]
    hashes, label_hashes, csv_hashes = {}, {}, {}
    for split, scenes in (("evaluation", selected["normal"][:4] + selected["hard"][:1]),
                          ("tuning", selected["normal"][4:] + selected["hard"][1:])):
        rows = []
        for scene in scenes:
            for i in range(6):
                name = f"{scene}_{i:03}"
                relative = f"images/{scene}/{name}.jpg"
                rows.append(dict(split=split, condition="low_light", scene=scene,
                                 difficulty="normal" if scene in selected["normal"] else "hard",
                                 source=relative, frame=name + ".png"))
                if split == "tuning":
                    image = root / relative
                    image.parent.mkdir(parents=True, exist_ok=True)
                    source = np.random.default_rng(i).integers(0, 60, (16, 20, 3), dtype=np.uint8)
                    _, encoded = cv2.imencode(".jpg", source)
                    encoded.tofile(image)
                    label = root / "labels" / scene / (name + ".json")
                    label.parent.mkdir(parents=True, exist_ok=True)
                    label.write_text(json.dumps({"imageWidth": 20, "imageHeight": 16,
                        "shapes": [{"label": "car", "points": [[2, 3], [17, 14]]}]}))
                    hashes[relative], label_hashes[relative] = digest(image), digest(label)
        path = manifests / f"{split}_frames.csv"
        with path.open("w", encoding="utf-8-sig", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=fields)
            writer.writeheader()
            writer.writerows(rows)
        csv_hashes[path.name] = digest(path)
    frozen = dict(selected_scenes=selected, csv_sha256=csv_hashes,
                  source_image_sha256=hashes, source_label_sha256=label_hashes)
    (manifests / "COMPLETE.json").write_text(json.dumps(frozen))
    # Deliberately no evaluation images: any evaluation pixel access would fail.
    return root, manifests, tmp_path / "review"


def test_run_preserves_sources_baseline_and_artifact_contract(inputs):
    root, manifests, output = inputs
    before = {str(p): digest(p) for p in root.rglob("*") if p.is_file()}
    params = dict(FIXED_PARAMS)
    report = run_review(*inputs, warmups=0)
    assert report["status"] == "awaiting_human_review" and len(report["frames"]) == 12
    assert dict(FIXED_PARAMS) == params
    assert before == {str(p): digest(p) for p in root.rglob("*") if p.is_file()}
    ready = json.loads((output / "REVIEW_READY.json").read_text())
    assert ready["evaluation_images_processed"] == 0
    assert ready["report_sha256"] == digest(output / "report.json")
    assert ready["html_sha256"] == digest(output / "index.html")
    assert len(list(output.rglob("*.png"))) == 120
    frame = report["frames"][0]
    baseline, _ = fixed_enhance(load_frame(root / frame["source"]))
    np.testing.assert_array_equal(load_frame(output / "A" / frame["frame"]), baseline)
    for item in report["frames"]:
        for key, result in item["outputs"].items():
            assert result["sha256"] == digest(output / key / item["frame"])
            assert result["crop_sha256"] == digest(output / "crops" / key / item["frame"])
            assert result["enhance_ms"] >= 0
    page = (output / "index.html").read_text(encoding="utf-8")
    assert "connect-src 'none'" in page and "https://" not in page
    assert "1:1 픽셀 보기" in page
    with pytest.raises(FileExistsError):
        run_review(*inputs, warmups=0)


@pytest.mark.parametrize("kind", ["csv", "image", "label"])
def test_tampering_is_rejected_before_outputs(inputs, kind):
    root, manifests, output = inputs
    if kind == "csv":
        path = manifests / "tuning_frames.csv"
    else:
        path = next((root / ("images" if kind == "image" else "labels")).rglob("*.*"))
    path.write_bytes(path.read_bytes() + b" ")
    with pytest.raises(ValueError, match="changed"):
        run_review(*inputs, warmups=0)
    assert not output.exists()


def test_split_rejection_even_if_csv_hash_was_updated(inputs):
    root, manifests, _ = inputs
    path = manifests / "tuning_frames.csv"
    text = path.read_text(encoding="utf-8-sig").replace("tuning,", "evaluation,", 1)
    path.write_text(text, encoding="utf-8-sig")
    frozen_path = manifests / "COMPLETE.json"
    frozen = json.loads(frozen_path.read_text())
    frozen["csv_sha256"][path.name] = digest(path)
    frozen_path.write_text(json.dumps(frozen))
    with pytest.raises(ValueError, match="Wrong split"):
        load_tuning_rows(root, manifests)


def test_candidate_ablations_and_source_overlap(inputs):
    options = candidates()
    assert options["A"]["params"] == dict(FIXED_PARAMS)
    assert options["B"]["params"] == {**dict(FIXED_PARAMS), "unsharp": 0.0}
    assert options["C"]["params"] == {**options["B"]["params"], "gamma": 0.6}
    root, manifests, _ = inputs
    with pytest.raises(ValueError, match="overlap"):
        run_review(root, manifests, root / "review", warmups=0)
