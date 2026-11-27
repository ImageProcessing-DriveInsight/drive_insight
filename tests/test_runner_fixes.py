import csv

from src.pipeline.runner import (
    _group_frames_by_clip,
    add_timing_rows,
    execute_experiment,
    run_experiment,
)
from src.vlm.scoring import score_vlm


def fake_response(*args, **kwargs):
    return {"vehicles": ["car"], "events": [], "visibility_notes": [], "uncertain": []}


def read_csv(path):
    with open(path, newline="", encoding="utf-8") as file:
        return list(csv.DictReader(file))


def test_frames_sorted_by_number_not_text(tmp_path):
    for ms in (100, 3500, 500):
        (tmp_path / f"bdd_01_{ms}.png").write_bytes(b"x")

    names = [p.name for p in _group_frames_by_clip(tmp_path)["bdd_01"]]

    assert names == ["bdd_01_100.png", "bdd_01_500.png", "bdd_01_3500.png"]


def test_config_snapshot_records_real_vlm_and_prompt(tmp_path, monkeypatch):
    import hashlib
    import json

    from src.vlm.client import MODEL_NAME, SYSTEM_PROMPT

    monkeypatch.setattr("src.pipeline.runner.get_project_root", lambda: tmp_path)

    config = json.loads(open(run_experiment("orig")["config_path"], encoding="utf-8").read())

    assert MODEL_NAME in config["model_versions"]["vlm"]
    assert "not_configured" not in json.dumps(config)
    assert config["prompt_hash"] == hashlib.sha256(SYSTEM_PROMPT.encode("utf-8")).hexdigest()


def test_timing_keeps_old_rows_and_adds_new_frames(tmp_path):
    row = {"frame": "a_1.png", "condition": "orig", "enhance_ms": "",
           "ocr_ms": "", "vlm_ms": 5, "total_ms": 5}
    add_timing_rows(tmp_path, [row])

    _, added = add_timing_rows(tmp_path, [dict(row, vlm_ms=99), dict(row, frame="b_1.png")])

    rows = read_csv(tmp_path / "timing.csv")
    assert added == 1
    assert [r["frame"] for r in rows] == ["a_1.png", "b_1.png"]
    assert rows[0]["vlm_ms"] == "5"


def test_second_run_adds_timing_for_new_clip(tmp_path, monkeypatch):
    frames = tmp_path / "frames"
    frames.mkdir()
    (frames / "clip01_1.png").write_bytes(b"x")
    monkeypatch.setattr("src.vlm.client.analyze_frame", fake_response)
    results = tmp_path / "results"

    execute_experiment("orig", ["vlm"], frames_dir=frames, results_dir=results)
    (frames / "clip02_1.png").write_bytes(b"x")
    execute_experiment("orig", ["vlm"], frames_dir=frames, results_dir=results)

    rows = read_csv(results / "orig" / "timing.csv")
    assert sorted(r["frame"] for r in rows) == ["clip01_1.png", "clip02_1.png"]


def test_offline_never_calls_vlm(tmp_path, monkeypatch):
    frames = tmp_path / "frames"
    frames.mkdir()
    (frames / "clip01_1.png").write_bytes(b"x")
    (frames / "clip02_1.png").write_bytes(b"x")
    results = tmp_path / "results"
    (results / "vlm" / "orig").mkdir(parents=True)
    (results / "vlm" / "orig" / "clip01.json").write_text("{}", encoding="utf-8")

    def must_not_run(*args, **kwargs):
        raise AssertionError("VLM called in offline mode")

    monkeypatch.setattr("src.vlm.client.analyze_frame", must_not_run)

    result = execute_experiment("orig", ["vlm"], frames_dir=frames,
                                results_dir=results, offline=True)

    assert result["skipped_clips"] == ["clip01"]
    assert result["missing_clips"] == ["clip02"]
    assert result["vlm"] == "offline_cache_incomplete"


def test_score_csv_keeps_one_row_per_condition_and_clip(tmp_path):
    sheet = tmp_path / "sheet.csv"
    with open(sheet, "w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=["claim", "checkability", "label"])
        writer.writeheader()
        writer.writerow({"claim": "car", "checkability": "checkable", "label": "correct"})
    out = tmp_path / "score.csv"

    score_vlm(sheet, {}, out, condition="orig", clip="c1")
    score_vlm(sheet, {}, out, condition="fixed", clip="c1")
    score_vlm(sheet, {}, out, condition="orig", clip="c1")

    rows = read_csv(out)
    assert sorted((r["condition"], r["clip"]) for r in rows) == [("fixed", "c1"), ("orig", "c1")]
