"""main.py end to end with synthetic frames and a stand-in VLM (no data, no model)."""
import csv

import pytest

import main


def fake_response(*args, **kwargs):
    return {
        "vehicles": ["car"],
        "events": [{"order": 1, "content": "car ahead", "frame": 1}],
        "visibility_notes": ["fog"],
        "uncertain": [],
    }


@pytest.fixture
def project(tmp_path, monkeypatch):
    for condition in main.CONDITIONS:
        folder = tmp_path / "data" / "frames" / condition
        folder.mkdir(parents=True)
        for ms in (100, 500):
            (folder / f"clip01_{ms}.png").write_bytes(b"x")

    results = tmp_path / "results"
    vlm = results / "vlm"
    monkeypatch.setattr(main, "FRAMES_DIR", tmp_path / "data" / "frames")
    monkeypatch.setattr(main, "RESULTS_DIR", results)
    monkeypatch.setattr(main, "LABELS_DIR", tmp_path / "data" / "labels")
    monkeypatch.setattr(main, "VLM_DIR", vlm)
    monkeypatch.setattr(main, "SHEETS_DIR", vlm / "verify")
    monkeypatch.setattr(main, "SHEET_KEY", vlm / "verify_key.csv")
    monkeypatch.setattr(main, "SCORE_CSV", vlm / "score.csv")
    monkeypatch.setattr("src.pipeline.runner.get_project_root", lambda: tmp_path)
    monkeypatch.setattr("src.vlm.client.analyze_frame", fake_response)
    return tmp_path


def test_full_flow_vlm_sheets_score_summary(project):
    assert main.main(["--steps", "vlm", "--make-sheets"]) == 0

    results = project / "results"
    for condition in main.CONDITIONS:
        assert (results / "vlm" / condition / "clip01.json").is_file()
        assert (results / condition / "timing.csv").is_file()
        assert (results / condition / "config_snapshot.json").is_file()
    assert (results / "summary.csv").is_file()

    with open(results / "vlm" / "verify_key.csv", newline="", encoding="utf-8") as f:
        key = list(csv.DictReader(f))
    assert sorted(row["condition"] for row in key) == sorted(main.CONDITIONS)

    # Sheets carry no condition names; fill every checkable claim.
    for row in key:
        sheet = results / "vlm" / "verify" / f"{row['sheet']}.csv"
        assert row["condition"] not in sheet.read_text(encoding="utf-8")
        with open(sheet, newline="", encoding="utf-8") as f:
            claims = list(csv.DictReader(f))
        for claim in claims:
            claim["label"] = "correct" if claim["checkability"] == "checkable" else "uncheckable"
        with open(sheet, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=["claim", "checkability", "label"])
            writer.writeheader()
            writer.writerows(claims)

    assert main.main(["--no-run", "--score"]) == 0

    with open(results / "vlm" / "score.csv", newline="", encoding="utf-8") as f:
        scores = list(csv.DictReader(f))
    assert len(scores) == 3
    assert all(row["scene_acc"] == "1.0" for row in scores)

    with open(results / "summary.csv", newline="", encoding="utf-8") as f:
        summary = {row["condition"]: row for row in csv.DictReader(f)}
    assert summary["orig"]["vlm_scene_acc"] == "1.0"


def test_offline_second_run_uses_cache(project, monkeypatch):
    assert main.main(["--steps", "vlm"]) == 0

    def must_not_run(*args, **kwargs):
        raise AssertionError("VLM called in offline mode")

    monkeypatch.setattr("src.vlm.client.analyze_frame", must_not_run)
    assert main.main(["--steps", "vlm", "--offline"]) == 0


def test_mismatched_frame_lists_stop_with_error(project):
    (project / "data" / "frames" / "fixed" / "clip01_900.png").write_bytes(b"x")

    assert main.main(["--steps", "vlm"]) == 1


def test_missing_frames_folder_is_a_clear_error(project, capsys):
    import shutil

    shutil.rmtree(project / "data" / "frames" / "adaptive")

    assert main.main(["--steps", "vlm"]) == 1
    assert "Frames folder not found" in capsys.readouterr().err
