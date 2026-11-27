"""C's report per environment condition: fog, low light, rain, tunnel, ... (#92).

tools/plate_report.py pools every frame under data/frames/<cond>/. After it has run, this splits
its results by the environment condition of each frame and runs the evaluation chain again on
each part, without new OCR or vehicle detection:

    results/by_env/<env>/  that condition's frames only: ocr/<cond>.csv, vehicles/<cond>.json,
                           params/<cond>.json, timing.csv and <cond>/timing.csv, vlm/score.csv rows
                           of its clips; then plate_report's chain with --skip-ocr writes summary.csv,
                           compare.csv, vehicles.csv, vehicle_compare.csv and figures/ there.
    results/by_env/summary.csv, compare.csv, vehicles.csv, vehicle_compare.csv
                           those tables of every condition, with an env column first.

The plate labels are split the same way, in memory: a label of another condition's frame would
count as a missed plate. Vehicle labels need no split, since only frames with detections count.

Environment condition of a frame:
- data/eval_set.csv: frame <clip stem>_<timestamp_ms> (B's frame names) takes the row's condition,
  and the row's clip is the clip of the VLM rows.
- --envs: a CSV with columns frame, env and optionally clip, for frames named otherwise (e.g. AI
  Hub frames without a timestamp). It wins over eval_set.csv.
A frame in the results with no condition stops the run, so no frame is left out unseen. VLM rows
without a clip cannot be split and are left out.

Each run rewrites results/by_env/<env>/ for the conditions it finds. The folders hold plate texts
and crops of real plates, so git ignores results/by_env/.

Usage:
    python tools/env_report.py [--results results] [--eval-set data/eval_set.csv] [--envs CSV]
                               [--labels data/labels] [--frames data/frames] [--scenes FILE ...] [--hide N]
"""

import argparse
import csv
import json
import re
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.eval.ocr import frame_key  # noqa: E402
from src.eval.vehicles import SCENES, scenes_arg  # noqa: E402
from src.plate.run import CONDITIONS, REFERENCE  # noqa: E402
from tools.plate_report import FRAMES, LABELS, RESULTS, report  # noqa: E402

EVAL_SET = ROOT / "data" / "eval_set.csv"
OUT = "by_env"
TABLES = ("summary.csv", "compare.csv", "vehicles.csv", "vehicle_compare.csv")
ENV_NAME = re.compile(r"^[A-Za-z0-9_-]+$")


def read_csv(path):
    """(fieldnames, rows) of a CSV; ([], []) if it is missing or empty."""
    path = Path(path)
    if not path.exists():
        return [], []
    with open(path, encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        return list(reader.fieldnames or []), list(reader)


def write_csv(path, fieldnames, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, restval="")
        writer.writeheader()
        writer.writerows(rows)
    return path


def env_of(row, column, path):
    env = (row.get(column) or "").strip()
    if not ENV_NAME.match(env):
        raise ValueError(f"{path}: condition {env!r} must be letters, digits, _ or -")
    return env


def load_envs(eval_set=EVAL_SET, envs=None):
    """({frame key: env}, {clip stem: env}) from eval_set.csv and the optional --envs CSV (which wins)."""
    frame_env, clip_env = {}, {}

    def add_clip(clip, env, path):
        stem = Path(clip.strip()).stem
        if clip_env.setdefault(stem, env) != env:
            raise ValueError(f"{path}: clip {clip} has two conditions, {clip_env[stem]} and {env}")

    for r in read_csv(eval_set)[1]:
        env = env_of(r, "condition", eval_set)
        add_clip(r["clip"], env, eval_set)
        ms = (r.get("timestamp_ms") or "").strip()
        if ms:
            frame_env[f"{Path(r['clip'].strip()).stem}_{int(float(ms))}"] = env
    if envs is not None:
        rows = read_csv(envs)[1]
        if not rows:
            raise FileNotFoundError(f"no rows in {envs}")
        for r in rows:
            env = env_of(r, "env", envs)
            frame_env[frame_key(r["frame"].strip())] = env
            if (r.get("clip") or "").strip():
                add_clip(r["clip"], env, envs)
    return frame_env, clip_env


def result_frames(results_dir):
    """Frame keys in ocr/<cond>.csv and vehicles/<cond>.json of every condition."""
    frames = set()
    for cond in (*CONDITIONS, REFERENCE):
        frames |= {frame_key(r["frame"]) for r in read_csv(Path(results_dir) / "ocr" / f"{cond}.csv")[1]}
        path = Path(results_dir) / "vehicles" / f"{cond}.json"
        if path.exists():
            frames |= {frame_key(f) for f in json.loads(path.read_text(encoding="utf-8"))}
    return frames


def raw_labels(labels):
    """Plate labels as {frame: [plate, ...]} from a dict, a JSON file or a folder of them; {} if missing."""
    if isinstance(labels, dict):
        return dict(labels)
    path, data = Path(labels), {}
    for f in sorted(path.glob("*.json")) if path.is_dir() else [path] if path.exists() else []:
        data.update(json.loads(f.read_text(encoding="utf-8")))
    return data


def split_results(results_dir, out_dir, frames, clips, all_frames):
    """Copy the results of the given frames (and VLM rows of the given clips) to out_dir."""
    results_dir, out_dir = Path(results_dir), Path(out_dir)
    keep = lambda name: frame_key(name) in frames  # noqa: E731
    for cond in (*CONDITIONS, REFERENCE):
        fields, rows = read_csv(results_dir / "ocr" / f"{cond}.csv")
        if fields:
            write_csv(out_dir / "ocr" / f"{cond}.csv", fields, [r for r in rows if keep(r["frame"])])
        for sub in ("vehicles", "params"):
            path = results_dir / sub / f"{cond}.json"
            if path.exists():
                data = json.loads(path.read_text(encoding="utf-8"))
                # params may hold non-frame keys such as "global"; drop only other conditions' frames
                kept = {k: v for k, v in data.items() if keep(k) or (sub == "params" and frame_key(k) not in all_frames)}
                (out_dir / sub).mkdir(parents=True, exist_ok=True)
                (out_dir / sub / f"{cond}.json").write_text(json.dumps(kept, indent=1), encoding="utf-8")
    timing = [results_dir / "timing.csv"] + sorted(results_dir.glob("*/timing.csv"))
    for path in timing:
        fields, rows = read_csv(path)
        if fields:
            write_csv(out_dir / path.relative_to(results_dir), fields, [r for r in rows if keep(r.get("frame") or "")])
    fields, rows = read_csv(results_dir / "vlm" / "score.csv")
    if fields:
        write_csv(out_dir / "vlm" / "score.csv", fields,
                  [r for r in rows if (r.get("clip") or "").strip() and Path(r["clip"].strip()).stem in clips])


def combine(out_root, envs):
    """results/by_env/<table> with an env column, from each condition's table. Returns the paths written."""
    paths = []
    for name in TABLES:
        fields, rows = ["env"], []
        for env in envs:
            f, rs = read_csv(Path(out_root) / env / name)
            fields += [c for c in f if c not in fields]
            rows += [{"env": env, **r} for r in rs]
        if rows:
            paths.append(write_csv(Path(out_root) / name, fields, rows))
    return paths


def env_report(results_dir=RESULTS, eval_set=EVAL_SET, envs=None, labels=LABELS, frames_dir=FRAMES, scenes=None,
               hide=0, log=print):
    """Split the results by environment condition and rerun the chain on each part.

    Returns {env: plate_report.report output} plus "tables": the combined tables written.
    """
    results_dir = Path(results_dir)
    frame_env, clip_env = load_envs(eval_set, envs)
    frames = result_frames(results_dir)
    if not frames:
        raise FileNotFoundError(f"no OCR or vehicle results in {results_dir}: run tools/plate_report.py first")
    unknown = sorted(frames - set(frame_env))
    if unknown:
        raise ValueError(f"{len(unknown)} frames have no environment condition in {eval_set} or --envs, "
                         f"e.g. {unknown[:3]}")
    gold = raw_labels(labels)
    out_root, out = results_dir / OUT, {}
    for env in sorted({frame_env[f] for f in frames}):
        env_frames = {f for f in frames if frame_env[f] == env}
        env_dir = out_root / env
        if env_dir.exists():
            shutil.rmtree(env_dir)  # generated by this tool; rewritten whole so no old file stays
        split_results(results_dir, env_dir, env_frames, {c for c, e in clip_env.items() if e == env}, frames)
        env_labels = {k: v for k, v in gold.items() if frame_key(k) in env_frames}
        log(f"{env}: {len(env_frames)} frames, {len(env_labels)} with plate labels")
        out[env] = report(frames_dir, env_dir, env_labels, skip_ocr=True, hide=hide, scenes=scenes, log=log)
    out["tables"] = combine(out_root, sorted(e for e in out))
    log("wrote " + ", ".join(str(p) for p in out["tables"]))
    return out


def main():
    ap = argparse.ArgumentParser(description="C's results per environment condition (fog, low light, rain, ...).")
    ap.add_argument("--results", type=Path, default=RESULTS, help="results of tools/plate_report.py")
    ap.add_argument("--eval-set", type=Path, default=EVAL_SET)
    ap.add_argument("--envs", type=Path, help="CSV with columns frame, env and optionally clip; wins over --eval-set")
    ap.add_argument("--labels", type=Path, default=LABELS)
    ap.add_argument("--frames", type=Path, default=FRAMES, help="folder with orig/, fixed/, adaptive/ (slide images)")
    ap.add_argument("--scenes", type=Path, nargs="+", help="vehicle label files, merged (default: "
                    "data/annotations/scenes.json); the vehicle rate is skipped without them")
    ap.add_argument("--hide", type=int, default=0, help="cover the last N characters in the slide images")
    args = ap.parse_args()
    scenes = scenes_arg(args.scenes)
    if scenes is None:
        print(f"no vehicle labels at {SCENES}: skipping the vehicle detection rate")
    env_report(args.results, args.eval_set, args.envs, args.labels, args.frames, scenes, args.hide)


if __name__ == "__main__":
    main()
