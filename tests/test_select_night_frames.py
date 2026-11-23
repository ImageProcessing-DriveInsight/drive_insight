import csv
import json
import random

import pytest

from tools.select_night_frames import choose_frames, read_metadata, write_selection


def inputs():
    frames, metadata = [], {}
    for i in range(178):
        scene = f"Clip_{i:03}"
        metadata[scene] = dict(mean_gray="5" if i < 41 else "4.9", tunnel_polygons=str(i % 2))
        for n in range(20):
            # Mark the last half as group-like nonqualifying frames; retain them if sampled.
            frames.append(dict(scene=scene, source=f"images/{scene}/374_NN_{i:03}_CF_{n:03}.jpg",
                               has_vehicle_width_ge_100=n < 10))
    return dict(summary={"issues": 0}, issues=[], frames=list(reversed(frames))), metadata


def test_confirmed_counts_sampling_split_and_positions():
    report, meta = inputs()
    result = choose_frames(report, meta)
    expected_normal = random.Random(2026).sample(sorted(list(meta)[:41]), 5)
    expected_hard = random.Random(2026).sample(sorted(list(meta)[41:]), 2)
    assert result["selected_scenes"] == dict(normal=expected_normal, hard=expected_hard)
    evaluation = [r for r in result["rows"] if r["split"] == "evaluation"]
    tuning = [r for r in result["rows"] if r["split"] == "tuning"]
    assert len(evaluation) == 30 and len(tuning) == 12
    assert not {r["scene"] for r in evaluation} & {r["scene"] for r in tuning}
    assert [r["sequence_index"] for r in result["rows"][:6]] == [0, 4, 8, 11, 15, 19]
    assert all("timestamp_ms" not in r and "fps" not in r for r in result["rows"])


def test_independent_cohorts():
    report, meta = inputs()
    before = choose_frames(report, meta)["selected_scenes"]["hard"]
    report["frames"] = [f for f in report["frames"] if f["scene"] != "Clip_000"]
    after = choose_frames(report, meta, expected_counts=(40, 137))["selected_scenes"]["hard"]
    assert before == after


@pytest.mark.parametrize("mutation", ["counts", "nan", "issues", "duplicate_index"])
def test_invalid_input_refuses_selection(mutation):
    report, meta = inputs()
    if mutation == "counts":
        report["frames"] = report["frames"][20:]
    elif mutation == "nan":
        meta["Clip_000"]["mean_gray"] = "nan"
    elif mutation == "issues":
        report["issues"].append({"message": "bad input"})
    else:
        for f in report["frames"]:
            f["source"] = f["source"].rsplit("_", 1)[0] + "_000.jpg"
    with pytest.raises(ValueError):
        choose_frames(report, meta)


def test_handoff_files_and_freeze(tmp_path):
    result = choose_frames(*inputs())
    target = tmp_path / "handoff"
    write_selection(result, target)
    complete = json.loads((target / "COMPLETE.json").read_text())
    assert len(complete["csv_sha256"]) == 4
    with (target / "evaluation_names.csv").open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        assert reader.fieldnames == ["source", "frame"]
        assert len(list(reader)) == 30
    with pytest.raises(FileExistsError):
        write_selection(result, target)


def test_duplicate_metadata(tmp_path):
    path = tmp_path / "clips.csv"
    path.write_text("clip,mean_gray\nClip_000,5\nClip_000,4\n")
    with pytest.raises(ValueError, match="Duplicate"):
        read_metadata(path)
