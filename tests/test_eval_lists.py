"""Frame condition and name lists from the members' frame lists (#108), on hand-made lists."""

import csv
import sys

import pytest

from tools.aihub_vehicles import load_names
from tools.env_report import load_envs
from tools.eval_lists import build, main, summary

NIGHT_FIELDS = ["split", "condition", "scene", "difficulty", "source", "frame", "tags", "sequence_index", "mean_gray"]


def write_csv(path, fields, rows, bom=False):
    with open(path, "w", newline="", encoding="utf-8-sig" if bom else "utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields, restval="")
        w.writeheader()
        w.writerows(rows)
    return path


def night_list(tmp_path, condition="low_light", name="night.csv"):
    rows = [{"split": "evaluation", "condition": condition, "scene": f"Clip_{s}", "difficulty": "normal",
             "source": f"images/Clip_{s}/374_CN_{s}_CF_{k:03d}.jpg", "frame": f"374_CN_{s}_CF_{k:03d}.png"}
            for s in ("186", "076") for k in (17, 68)]
    return write_csv(tmp_path / name, NIGHT_FIELDS, rows, bom=True)  # A's lists start with a BOM


def rain_list(tmp_path, frames=("85CF_RD_20210801_008550", "85CF_RN_20220214_074586"), name="rain.csv"):
    rows = [{"source": f"{'night' if '_RN_' in f else 'day'}/{f}.jpg", "frame": f"{f}.png"} for f in frames]
    return write_csv(tmp_path / name, ["source", "frame"], rows)


def test_build_both_list_kinds(tmp_path):
    envs, names = build([(night_list(tmp_path), "low_light"), (rain_list(tmp_path), "rain")])
    assert [r["env"] for r in envs] == ["low_light"] * 4 + ["rain"] * 2
    assert envs[0] == {"frame": "374_CN_186_CF_017.png", "env": "low_light", "clip": "Clip_186"}  # scene -> clip
    assert envs[-1] == {"frame": "85CF_RN_20220214_074586.png", "env": "rain", "clip": ""}  # no clip column
    assert names[-1] == {"source": "night/85CF_RN_20220214_074586.jpg", "frame": "85CF_RN_20220214_074586.png"}


def test_outputs_feed_env_report_and_aihub_vehicles(tmp_path, monkeypatch):
    envs_out, names_out, orig = tmp_path / "out" / "envs.csv", tmp_path / "out" / "names.csv", tmp_path / "orig"
    orig.mkdir()
    (orig / "85CF_RD_20210801_008550.png").write_bytes(b"")
    monkeypatch.setattr(sys, "argv", ["eval_lists.py", "--list", str(night_list(tmp_path)), "low_light",
                                      "--list", str(rain_list(tmp_path)), "rain", "--envs-out", str(envs_out),
                                      "--names-out", str(names_out), "--orig", str(orig)])
    main()
    frame_env, clip_env = load_envs(tmp_path / "no_eval_set.csv", envs_out)
    assert frame_env["374_CN_076_CF_068"] == "low_light" and frame_env["85CF_RD_20210801_008550"] == "rain"
    assert clip_env == {"Clip_186": "low_light", "Clip_076": "low_light"}
    assert load_names(names_out)["374_CN_186_CF_017.jpg"] == "374_CN_186_CF_017.png"  # matched by file name
    envs, _ = build([(rain_list(tmp_path), "rain")])
    assert summary(envs, orig) == [f"rain: 2 frames, 1 in {orig}"]


@pytest.mark.parametrize("case, message", [
    ("condition column disagrees", "condition low_light but the list was given as rain"),
    ("frame twice", "is also in"),
    ("same source file name", "source file 85CF_RD_20210801_008550.jpg is also in"),
    ("bad condition name", "must be letters"),
    ("no frame column", "needs the columns source, frame"),
    ("no rows", "no rows"),
    ("not a PNG", "PNG frame name"),
    ("clip with two conditions", "has two conditions"),
])
def test_stops(tmp_path, case, message):
    if case == "condition column disagrees":
        lists = [(night_list(tmp_path), "rain")]
    elif case == "frame twice":
        lists = [(rain_list(tmp_path), "rain"), (rain_list(tmp_path, name="again.csv"), "rain")]
    elif case == "same source file name":
        other = write_csv(tmp_path / "other.csv", ["source", "frame"],
                          [{"source": "elsewhere/85CF_RD_20210801_008550.jpg", "frame": "other_name.png"}])
        lists = [(rain_list(tmp_path), "rain"), (other, "rain")]
    elif case == "bad condition name":
        lists = [(rain_list(tmp_path), "rain/day")]
    elif case == "no frame column":
        lists = [(write_csv(tmp_path / "bad.csv", ["source", "name"], [{"source": "a.jpg", "name": "a.png"}]), "rain")]
    elif case == "no rows":
        lists = [(write_csv(tmp_path / "empty.csv", ["source", "frame"], []), "rain")]
    elif case == "not a PNG":
        lists = [(write_csv(tmp_path / "jpg.csv", ["source", "frame"], [{"source": "a.jpg", "frame": "a.jpg"}]), "rain")]
    else:
        tunnel = write_csv(tmp_path / "tunnel.csv", ["source", "frame", "scene"],
                           [{"source": "t/x.jpg", "frame": "x.png", "scene": "Clip_186"}])
        lists = [(night_list(tmp_path), "low_light"), (tunnel, "tunnel")]
    with pytest.raises(ValueError, match=message):
        build(lists)
