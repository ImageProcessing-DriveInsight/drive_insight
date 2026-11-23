"""Results per environment condition (#92), on hand-made results."""

import csv
import json

import numpy as np
import pytest

from src.eval.vehicles import load_vehicles, scenes_arg
from src.plate.imgutil import save_png
from src.plate.run import COLUMNS
from tools.env_report import combine, env_report, load_envs, result_frames

H, W = 60, 100
BOX = [20, 20, 40, 12]
CAR = [10, 10, 50, 30]
FOG1, FOG2, RAIN, NIGHT = "fog_01_100.png", "fog_01_200.png", "rain_01_100.png", "night_a.png"
FRAMES = (FOG1, FOG2, RAIN, NIGHT)
PLATES = {FOG1: "12가3456", RAIN: "34나5678"}
# orig misreads the fog plate and reads the rain plate; fixed reads both; adaptive is orig again.
# Pooled, orig would be 1 of 2 plates; per condition it is 0 of 1 (fog) and 1 of 1 (rain).
READS = {"orig": {FOG1: "12가3400", RAIN: "34나5678"}, "fixed": PLATES, "adaptive": {FOG1: "12가3400", RAIN: "34나5678"}}
OCR_MS = {FOG1: 100, FOG2: 100, RAIN: 300, NIGHT: 500}


def write_csv(path, fields, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields, restval="")
        w.writeheader()
        w.writerows(rows)


def read_csv(path):
    with open(path, encoding="utf-8") as f:
        return list(csv.DictReader(f))


@pytest.fixture
def setup(tmp_path):
    frames, results = tmp_path / "frames", tmp_path / "results"
    for cond in READS:
        for name in FRAMES:
            save_png(frames / cond / name, np.full((H, W, 3), 200, np.uint8))
        rows = []
        for name in FRAMES:
            if name in READS[cond]:
                x, y, w, h = BOX
                rows.append({"frame": name, "plate": 0, "x": x, "y": y, "w": w, "h": h, "text": READS[cond][name],
                             "conf": 0.9, "status": "readable", "ocr_ms": OCR_MS[name]})
            else:
                rows.append({"frame": name, "ocr_ms": OCR_MS[name]})
        write_csv(results / "ocr" / f"{cond}.csv", COLUMNS, rows)
        # the AI Hub night car is found by fixed only; the own fog car by nobody
        dets = {name: [] for name in FRAMES} | ({NIGHT: [CAR]} if cond == "fixed" else {})
        (results / "vehicles").mkdir(parents=True, exist_ok=True)
        (results / "vehicles" / f"{cond}.json").write_text(json.dumps(dets), encoding="utf-8")
    (results / "params").mkdir()
    (results / "params" / "fixed.json").write_text(json.dumps(
        {**{name: {"enhance_ms": 10} for name in FRAMES}, "global": {"gamma": 0.8}}), encoding="utf-8")
    write_csv(results / "vlm" / "score.csv", ["condition", "clip", "scene_acc", "hallucination_rate"], [
        {"condition": "orig", "clip": "fog_01.mp4", "scene_acc": 0.5, "hallucination_rate": 10},
        {"condition": "orig", "clip": "rain_01", "scene_acc": 0.9, "hallucination_rate": 0},
        {"condition": "orig", "clip": "", "scene_acc": 0.1, "hallucination_rate": 90},  # cannot be split
    ])
    labels = tmp_path / "plates.json"
    labels.write_text(json.dumps({FOG1: [{"bbox": BOX, "text": PLATES[FOG1]}], FOG2: [],
                                  RAIN: [{"bbox": BOX, "text": PLATES[RAIN]}]}, ensure_ascii=False), encoding="utf-8")
    eval_set = tmp_path / "eval_set.csv"
    write_csv(eval_set, ["clip", "timestamp_ms", "condition", "source", "license"], [
        {"clip": "fog_01.mp4", "timestamp_ms": 100, "condition": "fog"},
        {"clip": "fog_01.mp4", "timestamp_ms": 200, "condition": "fog"},
        {"clip": "rain_01.mp4", "timestamp_ms": 100, "condition": "rain"},
    ])
    envs = tmp_path / "envs.csv"
    write_csv(envs, ["frame", "env", "clip"], [{"frame": NIGHT, "env": "low_light", "clip": "night_clip"}])
    own = {FOG1: {"annotation_status": "complete", "vehicles": [{"bbox": CAR, "class": "car"}]}}
    aihub = {NIGHT: {"annotation_status": "complete", "vehicles": [{"bbox": CAR, "class": "car"}]}}
    return {"results": results, "frames": frames, "labels": labels, "eval_set": eval_set, "envs": envs,
            "scenes": [own, aihub]}


def run(s, **kw):
    args = dict(results_dir=s["results"], eval_set=s["eval_set"], envs=s["envs"], labels=s["labels"],
                frames_dir=s["frames"], scenes=s["scenes"], log=lambda *a: None)
    return env_report(**{**args, **kw})


def test_load_envs_rules(setup, tmp_path):
    frame_env, clip_env = load_envs(setup["eval_set"], setup["envs"])
    assert frame_env == {"fog_01_100": "fog", "fog_01_200": "fog", "rain_01_100": "rain", "night_a": "low_light"}
    assert clip_env == {"fog_01": "fog", "rain_01": "rain", "night_clip": "low_light"}
    override = tmp_path / "override.csv"
    write_csv(override, ["frame", "env"], [{"frame": "rain_01_100.png", "env": "tunnel"}])
    assert load_envs(setup["eval_set"], override)[0]["rain_01_100"] == "tunnel"  # --envs wins
    clash = tmp_path / "clash.csv"
    write_csv(clash, ["frame", "env", "clip"], [{"frame": "x.png", "env": "rain", "clip": "fog_01.mp4"}])
    with pytest.raises(ValueError, match="two conditions"):
        load_envs(setup["eval_set"], clash)
    bad = tmp_path / "bad.csv"
    write_csv(bad, ["frame", "env"], [{"frame": "x.png", "env": "../x"}])
    with pytest.raises(ValueError, match="letters"):
        load_envs(setup["eval_set"], bad)
    no_time = tmp_path / "no_time.csv"
    write_csv(no_time, ["clip", "timestamp_ms", "condition"], [{"clip": "Clip_000", "timestamp_ms": "", "condition": "low_light"}])
    assert load_envs(no_time) == ({}, {"Clip_000": "low_light"})  # a row without a timestamp names only its clip


def test_split_scores_each_condition_on_its_own_frames(setup):
    results = setup["results"]
    assert result_frames(results) == {"fog_01_100", "fog_01_200", "rain_01_100", "night_a"}
    out = run(setup)
    assert sorted(k for k in out if k != "tables") == ["fog", "low_light", "rain"]
    by_env = results / "by_env"
    assert [r["frame"] for r in read_csv(by_env / "fog" / "ocr" / "orig.csv")] == [FOG1, FOG2]
    assert set(json.loads((by_env / "rain" / "params" / "fixed.json").read_text(encoding="utf-8"))) == {RAIN, "global"}

    summary = {(r["env"], r["condition"]): r for r in read_csv(by_env / "summary.csv")}
    assert (summary["fog", "orig"]["plates"], summary["fog", "orig"]["exact_match"]) == ("1", "0.0")  # not 0 of 2
    assert summary["fog", "fixed"]["exact_match"] == "1.0"
    assert summary["rain", "orig"]["exact_match"] == "1.0"
    assert (summary["low_light", "orig"]["plates"], summary["low_light", "orig"]["exact_match"]) == ("0", "")
    assert [summary[e, "orig"]["ocr_ms"] for e in ("fog", "rain", "low_light")] == ["100.0", "300.0", "500.0"]
    assert summary["fog", "fixed"]["enhance_ms"] == "10.0"
    # VLM rows go by clip; the row without a clip is left out
    assert [summary[e, "orig"]["vlm_scene_acc"] for e in ("fog", "rain", "low_light")] == ["0.5", "0.9", ""]

    compare = {(r["env"], r["base"], r["target"]): r for r in read_csv(by_env / "compare.csv")}
    assert (compare["fog", "orig", "fixed"]["better"], compare["rain", "orig", "fixed"]["better"]) == ("1", "0")

    vehicles = {(r["env"], r["condition"], r["size"]): r for r in read_csv(by_env / "vehicles.csv")}
    assert (vehicles["low_light", "orig", "all"]["found"], vehicles["low_light", "fixed", "all"]["found"]) == ("0", "1")
    assert vehicles["fog", "orig", "all"]["labeled"] == "1"  # own labels and AI Hub labels together
    assert {p.name for p in out["tables"]} == {"summary.csv", "compare.csv", "vehicles.csv", "vehicle_compare.csv"}


def test_unknown_frame_stops_the_run(setup, tmp_path):
    with pytest.raises(ValueError, match="night_a"):
        run(setup, envs=None)
    with pytest.raises(FileNotFoundError, match="plate_report"):
        run(setup, results_dir=tmp_path / "empty")


def test_rerun_rewrites_a_condition_folder(setup):
    run(setup)
    stale = setup["results"] / "by_env" / "fog" / "stale.txt"
    stale.write_text("old", encoding="utf-8")
    run(setup)
    assert not stale.exists()


def test_combine_adds_new_columns(tmp_path):
    write_csv(tmp_path / "a" / "summary.csv", ["condition", "x"], [{"condition": "orig", "x": 1}])
    write_csv(tmp_path / "b" / "summary.csv", ["condition", "y"], [{"condition": "orig", "y": 2}])
    [path] = combine(tmp_path, ["a", "b"])
    assert read_csv(path) == [{"env": "a", "condition": "orig", "x": "1", "y": ""},
                              {"env": "b", "condition": "orig", "x": "", "y": "2"}]


def test_vehicle_label_files_merge(tmp_path):
    a = {"a.png": {"annotation_status": "complete", "vehicles": [{"bbox": [0, 0, 10, 10]}]}}
    b = {"b.png": {"annotation_status": "group", "vehicles": [{"bbox": [0, 0, 20, 20]}]},
         "c.png": {"vehicles": []}}
    assert load_vehicles([a, b]) == {"a.png": [[0, 0, 10, 10]], "c.png": []}
    with pytest.raises(ValueError, match="labeled in both"):
        load_vehicles([a, a])
    path = tmp_path / "scenes.json"
    path.write_text(json.dumps(a), encoding="utf-8")
    assert load_vehicles([path, b]) == load_vehicles([a, b])
    assert scenes_arg(None, default=tmp_path / "none.json") is None
    assert scenes_arg(None, default=path) == [path]
    assert scenes_arg([path]) == [path]
    with pytest.raises(SystemExit, match="none.json"):
        scenes_arg([path, tmp_path / "none.json"])
