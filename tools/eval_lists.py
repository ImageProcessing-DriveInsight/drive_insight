"""C's frame lists for the image frames of the members' evaluation sets (#108).

The members hand over their evaluation frames as CSV lists with the columns source (the original
image) and frame (the PNG name in data/frames/orig/); A's night list also has condition, scene and
more. AI Hub frames have no timestamp, so data/eval_set.csv cannot give their condition. From all
the lists this writes:

    data/annotations/envs.csv        frame, env, clip   --envs of tools/env_report.py
    data/annotations/eval_names.csv  source, frame      --names of tools/aihub_vehicles.py

Each list comes with its condition (--list FILE CONDITION), since some lists have no condition
column; a condition column, when there is one, must agree with it. clip is the list's clip or scene
column when there is one (env_report gives the VLM rows of that clip the frame's condition), else
empty. Tuning lists are not given: they are not evaluated.

Stops on a list without source or frame, an empty list, a frame that is not a PNG name, a frame
listed twice, two sources with the same file name (aihub_vehicles matches labels by file name), a
condition column that disagrees, a condition name other than letters, digits, _ or -, or a clip
with two conditions. Prints the frames per condition and how many of them are in
data/frames/orig/ yet.

The outputs name AI Hub files: keep them in data/annotations/, which git ignores.

Usage:
    python tools/eval_lists.py --list FILE CONDITION [--list FILE CONDITION ...]
                               [--envs-out FILE] [--names-out FILE] [--orig DIR]
"""

import argparse
import csv
import sys
from collections import Counter
from pathlib import Path, PureWindowsPath

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.eval.ocr import frame_key  # noqa: E402
from tools.env_report import ENV_NAME  # noqa: E402

ANNOTATIONS = ROOT / "data" / "annotations"
ENVS_OUT = ANNOTATIONS / "envs.csv"
NAMES_OUT = ANNOTATIONS / "eval_names.csv"
ORIG = ROOT / "data" / "frames" / "orig"
ENV_FIELDS = ["frame", "env", "clip"]
NAME_FIELDS = ["source", "frame"]


def read_list(path):
    """Rows of one member's list; raises ValueError without the source and frame columns or rows."""
    with open(path, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        fields, rows = reader.fieldnames or [], list(reader)
    if not {"source", "frame"} <= set(fields):
        raise ValueError(f"{path}: needs the columns source, frame (has {', '.join(fields) or 'none'})")
    if not rows:
        raise ValueError(f"{path}: no rows")
    return rows


def build(lists):
    """(envs rows, names rows) from [(list path, condition), ...], in list order."""
    envs, names = [], []
    frame_from, source_from, clip_env = {}, {}, {}
    for path, env in lists:
        if not ENV_NAME.match(env):
            raise ValueError(f"{path}: condition {env!r} must be letters, digits, _ or -")
        for i, r in enumerate(read_list(path), start=2):  # line 1 is the header
            where = f"{path} line {i}"
            source, frame = r["source"].strip(), r["frame"].strip()
            if not source or Path(frame).suffix.lower() != ".png":
                raise ValueError(f"{where}: needs a source and a PNG frame name, got {source!r}, {frame!r}")
            given = (r.get("condition") or "").strip()
            if given and given != env:
                raise ValueError(f"{where}: condition {given} but the list was given as {env}")
            key, name = frame_key(frame), PureWindowsPath(source).name
            if key in frame_from:
                raise ValueError(f"{where}: frame {frame} is also in {frame_from[key]}")
            if name in source_from:
                raise ValueError(f"{where}: source file {name} is also in {source_from[name]}")
            clip = (r.get("clip") or r.get("scene") or "").strip()
            if clip and clip_env.setdefault(clip, env) != env:
                raise ValueError(f"{where}: clip {clip} has two conditions, {clip_env[clip]} and {env}")
            frame_from[key], source_from[name] = where, where
            envs.append({"frame": frame, "env": env, "clip": clip})
            names.append({"source": source, "frame": frame})
    return envs, names


def write_csv(path, fields, rows):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    return path


def summary(envs, orig=ORIG):
    """One line per condition: frames, and how many of them are in orig/."""
    have = {p.name for p in Path(orig).glob("*.png")}
    total = Counter(r["env"] for r in envs)
    there = Counter(r["env"] for r in envs if r["frame"] in have)
    return [f"{env}: {n} frames, {there[env]} in {orig}" for env, n in total.items()]


def main():
    ap = argparse.ArgumentParser(description="Members' evaluation frame lists -> env_report --envs and "
                                             "aihub_vehicles --names.")
    ap.add_argument("--list", nargs=2, action="append", required=True, metavar=("FILE", "CONDITION"),
                    help="a member's list (columns source, frame) and its condition, e.g. rain; repeat per list")
    ap.add_argument("--envs-out", type=Path, default=ENVS_OUT, help="default: data/annotations/envs.csv")
    ap.add_argument("--names-out", type=Path, default=NAMES_OUT, help="default: data/annotations/eval_names.csv")
    ap.add_argument("--orig", type=Path, default=ORIG, help="folder checked for the frames (default: data/frames/orig)")
    args = ap.parse_args()
    envs, names = build([(Path(f), c) for f, c in args.list])
    print(f"{write_csv(args.envs_out, ENV_FIELDS, envs)}, {write_csv(args.names_out, NAME_FIELDS, names)}: "
          f"{len(envs)} frames from {len(args.list)} lists")
    for line in summary(envs, args.orig):
        print("  " + line)


if __name__ == "__main__":
    main()
