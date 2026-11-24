import csv
from pathlib import Path

import pytest

from src.pipeline import runner


def test_ocr_helper_saves_csv_and_crop(monkeypatch, tmp_path):
    project_root = tmp_path
    frames_dir = project_root / "data" / "frames" / "fixed"
    results_dir = project_root / "results"

    frames_dir.mkdir(parents=True)
    (frames_dir / "clip_001.png").write_bytes(b"frame")

    def fake_run_ocr(condition, frames_dir, results_dir):
        crop_dir = Path(results_dir) / "ocr" / "crops" / condition
        crop_dir.mkdir(parents=True)
        crop = crop_dir / "clip_001_0.png"
        crop.write_bytes(b"crop")

        csv_path = Path(results_dir) / "ocr" / f"{condition}.csv"
        csv_path.parent.mkdir(parents=True, exist_ok=True)
        with csv_path.open("w", newline="", encoding="utf-8") as file:
            writer = csv.DictWriter(
                file,
                fieldnames=[
                    "frame", "plate", "x", "y", "w", "h",
                    "crop_path", "text", "conf", "status", "ocr_ms",
                ],
            )
            writer.writeheader()
            writer.writerow({
                "frame": "clip_001.png",
                "plate": "plate_1",
                "x": 1,
                "y": 2,
                "w": 3,
                "h": 4,
                "crop_path": str(crop),
                "text": "ABC123",
                "conf": 0.9,
                "status": "ok",
                "ocr_ms": 12.5,
            })
        return csv_path

    monkeypatch.setattr(runner, "get_project_root", lambda: project_root)
    monkeypatch.setattr("src.plate.run.run_ocr", fake_run_ocr)

    rows = runner._run_ocr_safely("fixed", frames_dir, results_dir)

    final_csv = results_dir / "ocr" / "fixed.csv"
    final_crop = results_dir / "ocr" / "crops" / "fixed" / "clip_001_0.png"

    assert final_csv.is_file()
    assert final_crop.read_bytes() == b"crop"
    assert rows[0]["crop_path"] == (
        "results/ocr/crops/fixed/clip_001_0.png"
    )


def test_ocr_helper_refuses_existing_csv(tmp_path):
    frames_dir = tmp_path / "frames"
    results_dir = tmp_path / "results"
    frames_dir.mkdir()
    (results_dir / "ocr").mkdir(parents=True)
    (results_dir / "ocr" / "fixed.csv").write_text("existing")

    with pytest.raises(FileExistsError):
        runner._run_ocr_safely("fixed", frames_dir, results_dir)

    assert (results_dir / "ocr" / "fixed.csv").read_text() == "existing"


def test_ocr_helper_refuses_existing_crop_directory(tmp_path):
    frames_dir = tmp_path / "frames"
    results_dir = tmp_path / "results"
    frames_dir.mkdir()
    crop_dir = results_dir / "ocr" / "crops" / "fixed"
    crop_dir.mkdir(parents=True)

    with pytest.raises(FileExistsError):
        runner._run_ocr_safely("fixed", frames_dir, results_dir)

    assert crop_dir.is_dir()
