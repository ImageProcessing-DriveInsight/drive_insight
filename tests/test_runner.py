import csv
import json

import pytest

from src.pipeline.runner import run_experiment, save_timing_csv


def test_run_experiment_saves_config():
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
