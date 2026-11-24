import csv
import json

import pytest

from src.pipeline.runner import run_experiment, save_timing_csv


def test_run_experiment_saves_config(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "src.pipeline.runner.get_project_root",
        lambda: tmp_path,
    )

    result = run_experiment("orig")

    assert result["condition"] == "orig"
    assert result["status"] == "validated"

    with open(result["config_path"], encoding="utf-8") as file:
        config = json.load(file)

    assert config["condition"] == "orig"
    assert config["steps"] == ["enhance", "ocr", "vlm"]
    assert "prompt_hash" in config
    assert "model_versions" in config


def test_run_experiment_rejects_invalid_condition():
    with pytest.raises(ValueError):
        run_experiment("invalid")


def test_run_experiment_rejects_invalid_step():
    with pytest.raises(ValueError):
        run_experiment("orig", steps=["invalid"])


def test_run_experiment_rejects_mismatched_frames():
    frame_lists = {
        "orig": ["a.png", "b.png"],
        "fixed": ["a.png"],
    }

    with pytest.raises(ValueError):
        run_experiment("orig", frame_lists=frame_lists)


def test_save_timing_csv(tmp_path):
    rows = [
        {
            "frame": "frame01.png",
            "condition": "orig",
            "enhance_ms": 10,
            "ocr_ms": 20,
            "vlm_ms": 30,
            "total_ms": 60,
        }
    ]

    path = save_timing_csv(tmp_path, rows)

    assert path.is_file()

    with open(path, newline="", encoding="utf-8") as file:
        result = list(csv.DictReader(file))

    assert len(result) == 1
    assert result[0]["condition"] == "orig"
    assert result[0]["total_ms"] == "60"


def test_execute_experiment_processes_clip_and_saves_timing(
    tmp_path, monkeypatch
):
    from src.pipeline.runner import execute_experiment

    frames_dir = tmp_path / "frames"
    frames_dir.mkdir()
    (frames_dir / "clip01_001.png").write_bytes(b"frame1")
    (frames_dir / "clip01_002.png").write_bytes(b"frame2")

    def fake_analyze_frame(image_path, frame_number=1, **kwargs):
        return {
            "vehicles": ["car"],
            "events": [],
            "visibility_notes": [],
            "uncertain": [],
        }

    monkeypatch.setattr(
        "src.vlm.client.analyze_frame",
        fake_analyze_frame,
    )

    result = execute_experiment(
        "orig",
        steps=["vlm"],
        clip_ids=["clip01"],
        frames_dir=frames_dir,
        results_dir=tmp_path / "results",
    )

    output = tmp_path / "results" / "vlm" / "orig" / "clip01.json"
    timing = tmp_path / "results" / "orig" / "timing.csv"

    assert output.is_file()
    assert timing.is_file()
    assert result["processed_clips"] == ["clip01"]
    assert result["vlm"] == "completed"


def test_execute_experiment_skips_existing_vlm_output(
    tmp_path, monkeypatch
):
    from src.pipeline.runner import execute_experiment

    frames_dir = tmp_path / "frames"
    frames_dir.mkdir()
    (frames_dir / "clip01_001.png").write_bytes(b"frame1")

    results_dir = tmp_path / "results"
    vlm_dir = results_dir / "vlm" / "orig"
    vlm_dir.mkdir(parents=True)
    existing = vlm_dir / "clip01.json"
    existing.write_text('{"preserved": true}', encoding="utf-8")

    def should_not_run(*args, **kwargs):
        raise AssertionError("Existing VLM output should be skipped")

    monkeypatch.setattr(
        "src.vlm.client.analyze_frame",
        should_not_run,
    )

    result = execute_experiment(
        "orig",
        steps=["vlm"],
        frames_dir=frames_dir,
        results_dir=results_dir,
    )

    assert result["skipped_clips"] == ["clip01"]
    assert existing.read_text(encoding="utf-8") == '{"preserved": true}'
