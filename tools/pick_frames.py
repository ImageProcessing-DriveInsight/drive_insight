"""Pick evaluation timestamps in clear-day clips by vehicle size (ALL-01, issue #77).

Plates read well from about 80 px wide in a 1920x1080 frame and lose the Hangul below that
(docs/plate_size_check.md). A Korean plate (520 mm) is about 0.29 of a car's width
(1.7-1.9 m), so a frame is worth labeling when a vehicle box is at least MIN_WIDTH px wide
(at 1920 px; scaled with the frame width). Vehicles cut by the left or right frame edge are
passing beside the camera, and boxes wider than MAX_ASPECT:1 are side views or oncoming cars;
neither counts. The pick looks only at YOLO vehicle boxes, never
at the plate search or OCR, so it does not favor frames the pipeline already reads.

scan   vehicle boxes every --step-ms of a clear clip -> <clip>.vehicles.json next to it
pick   the window of --length-ms with the most qualifying frames at least --gap-ms apart
       and not showing the same view (then the widest vehicles); prints the synth_fog.py make range and adds manifest
       rows for the foggy clip, with timestamps in the foggy clip's time

Scan files hold boxes only, no images. They stay next to the clear clips in data/clear/,
which git ignores.

Usage:
    python tools/pick_frames.py scan data/clear/day_01.mp4 [--step-ms 500]
    python tools/pick_frames.py pick data/clear/day_01.mp4 --clip fog_01.mp4 --density medium
        [--length-ms 20000] [--gap-ms 3000] [--max-frames 5] [--min-width 280] [--manifest FILE]
"""

import argparse
import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.io.video import get_meta, read_video, resolve  # noqa: E402
from tools.synth_fog import PRESETS, frame_index, sha256, shown, write_json  # noqa: E402

MIN_WIDTH = 280  # px at 1920 wide: a 520 mm plate on a 1.8 m car is then about 80 px
REF_WIDTH = 1920
EDGE = 4  # px: a box this close to the left or right edge is cut by the frame
MAX_ASPECT = 2.5  # w/h; rear three-quarter views up to about 2.4 still showed the plate
STEP_MS = 500
LENGTH_MS = 20000  # foggy clips are 10-30 s
GAP_MS = 3000  # neighboring frames of one car are nearly the same plate
SAME_VIEW = 0.7  # IoU of the widest boxes: a car standing still in a jam is the same view
MAX_FRAMES = 5  # 3-5 timestamps per clip
MANIFEST = ROOT / "data" / "manifests" / "member_c.csv"
FIELDS = ["clip", "timestamp_ms", "condition", "source", "license"]


def scan_path(source):
    return Path(source).with_suffix(".vehicles.json")


def detect(frame):
    """Vehicle boxes of the plate pipeline (classes and threshold of detect_vehicles)."""
    from src.plate.detect import detect_vehicles  # heavy, loaded only when scanning

    return detect_vehicles(frame)


def scan(source, step_ms=STEP_MS, detector=None, out=None):
    """Vehicle boxes every step_ms of source, saved as JSON next to it. Returns the record.

    The whole clip is decoded, and frame_count is the number of frames that decoded: dashcam
    files can list one or two frames more than they hold, and a window must not reach them.
    """
    if step_ms <= 0:
        raise ValueError("step_ms must be positive")
    source, detector = resolve(source), detector or detect
    meta = get_meta(source)
    wanted, ms = {}, 0
    while (index := frame_index(ms, meta["fps"])) < meta["frame_count"]:
        wanted.setdefault(index, ms)
        ms += step_ms
    frames, decoded = [], 0
    stream = read_video(source)
    try:
        for i, frame in enumerate(stream):
            decoded = i + 1
            if i in wanted:
                vehicles = [{"bbox": [int(v) for v in d["bbox"]], "cls": d["cls"], "conf": d["conf"]}
                            for d in detector(frame)]
                frames.append({"index": i, "ms": wanted[i], "vehicles": vehicles})
    finally:
        stream.close()
    if not frames:
        raise OSError(f"no frame of {source} could be decoded")
    record = {"tool": "tools/pick_frames.py", "source": shown(source), "source_sha256": sha256(source),
              "fps": meta["fps"], "frame_count": decoded, "listed_frame_count": meta["frame_count"],
              "width": meta["width"], "height": meta["height"], "step_ms": step_ms, "frames": frames}
    write_json(Path(out) if out else scan_path(source), record)
    return record


def near_box(vehicles, width, edge=EDGE, max_aspect=MAX_ASPECT):
    """The widest vehicle box seen from behind or the front, not cut by the left or right
    frame edge, or None."""
    inside = [b for b in (v["bbox"] for v in vehicles)
              if b[0] >= edge and b[0] + b[2] <= width - edge and b[2] <= max_aspect * b[3]]
    return max(inside, key=lambda b: b[2], default=None)


def near_width(vehicles, width, edge=EDGE, max_aspect=MAX_ASPECT):
    """Width of near_box (0 if none)."""
    box = near_box(vehicles, width, edge, max_aspect)
    return box[2] if box else 0


def iou(a, b):
    w = min(a[0] + a[2], b[0] + b[2]) - max(a[0], b[0])
    h = min(a[1] + a[3], b[1] + b[3]) - max(a[1], b[1])
    inter = max(0, w) * max(0, h)
    return inter / (a[2] * a[3] + b[2] * b[3] - inter)


def choose(frames, gap_frames, max_frames, same_view=SAME_VIEW):
    """Widest first, each at least gap_frames from the ones kept and with its box overlapping
    none of theirs by IoU >= same_view. Returns them in time order."""
    kept = []
    for f in sorted(frames, key=lambda f: (-f["width"], f["index"])):
        if len(kept) < max_frames and all(abs(f["index"] - k["index"]) >= gap_frames
                                          and iou(f["box"], k["box"]) < same_view for k in kept):
            kept.append(f)
    return sorted(kept, key=lambda f: f["index"])


def pick(record, length_ms=LENGTH_MS, gap_ms=GAP_MS, max_frames=MAX_FRAMES, min_width=MIN_WIDTH):
    """Best window of a scan record: {start_ms, end_ms, first_frame, frames: [{index, ms, clip_ms, width}]}.

    The window has the most qualifying frames, then the largest total vehicle width, then the
    earliest start. clip_ms is the time in the foggy clip made from start_ms, chosen so that
    the frame extractor (nearest frame) lands on the scanned frame. None if no frame qualifies.
    """
    fps, count = record["fps"], record["frame_count"]
    if length_ms <= 0 or gap_ms < 0 or max_frames < 1:
        raise ValueError("need length_ms > 0, gap_ms >= 0 and max_frames >= 1")
    limit = min_width * record["width"] / REF_WIDTH
    boxes = [(f, near_box(f["vehicles"], record["width"])) for f in record["frames"]]
    good = [{"index": f["index"], "ms": f["ms"], "width": b[2], "box": b} for f, b in boxes if b and b[2] >= limit]
    gap_frames = gap_ms * fps / 1000
    best = None
    for start in [f["ms"] for f in record["frames"]]:
        first, stop = frame_index(start, fps), frame_index(start + length_ms, fps)
        if stop > count:
            break  # the window runs past the end of the clip
        kept = choose([f for f in good if first <= f["index"] < stop], gap_frames, max_frames)
        score = (len(kept), sum(f["width"] for f in kept))
        if kept and (best is None or score > best[0]):
            best = (score, start, first, kept)
    if best is None:
        return None
    _, start, first, kept = best
    for f in kept:
        del f["box"]
        f["clip_ms"] = round((f["index"] - first) * 1000 / fps)
        assert frame_index(f["clip_ms"], fps) == f["index"] - first
    return {"start_ms": start, "end_ms": start + length_ms, "first_frame": first, "frames": kept}


def source_text(record, window, density):
    name = Path(record["source"]).name
    return (f"own dashcam {name} {window['start_ms']}-{window['end_ms']} ms, "
            f"synthetic fog (tools/synth_fog.py, {density})")


def add_rows(manifest, clip, window, record, density, license_text="own footage"):
    """Append the manifest rows of one foggy clip. Refuses a clip that is already listed."""
    manifest = Path(manifest)
    rows = []
    if manifest.exists():
        with manifest.open(encoding="utf-8-sig", newline="") as f:
            rows = list(csv.DictReader(f))
        if any(r["clip"] == clip for r in rows):
            raise ValueError(f"{clip} is already in {manifest}")
    source = source_text(record, window, density)
    new = [{"clip": clip, "timestamp_ms": str(f["clip_ms"]), "condition": "fog", "source": source,
            "license": license_text} for f in window["frames"]]
    manifest.parent.mkdir(parents=True, exist_ok=True)
    with manifest.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        w.writerows(rows + new)
    return new


def main():
    ap = argparse.ArgumentParser(description="Pick evaluation timestamps in clear-day clips by vehicle size.")
    sub = ap.add_subparsers(dest="command", required=True)
    p = sub.add_parser("scan", help="vehicle boxes every --step-ms, saved next to the clip")
    p.add_argument("source", type=Path)
    p.add_argument("--step-ms", type=int, default=STEP_MS)
    p = sub.add_parser("pick", help="best window and its timestamps; adds manifest rows")
    p.add_argument("source", type=Path, help="clear clip scanned with `scan`")
    p.add_argument("--clip", required=True, help="name of the foggy clip, e.g. fog_01.mp4")
    p.add_argument("--density", required=True, choices=PRESETS, help="fog density, fixed before any results")
    p.add_argument("--length-ms", type=int, default=LENGTH_MS)
    p.add_argument("--gap-ms", type=int, default=GAP_MS)
    p.add_argument("--max-frames", type=int, default=MAX_FRAMES)
    p.add_argument("--min-width", type=float, default=MIN_WIDTH, help=f"vehicle box px at {REF_WIDTH} wide")
    p.add_argument("--manifest", type=Path, default=MANIFEST)
    args = ap.parse_args()

    if args.command == "scan":
        record = scan(args.source, args.step_ms)
        n = sum(1 for f in record["frames"] if f["vehicles"])
        print(f"{len(record['frames'])} frames scanned, {n} with vehicles; wrote {shown(scan_path(args.source))}")
        return
    if Path(args.clip).name != args.clip or Path(args.clip).suffix.lower() != ".mp4":
        raise SystemExit("--clip must be a file name like fog_01.mp4")
    source = resolve(args.source)
    record = json.loads(scan_path(source).read_text(encoding="utf-8"))
    if record["source_sha256"] != sha256(source):
        raise SystemExit(f"{scan_path(source)} was made from another clip; scan again")
    window = pick(record, args.length_ms, args.gap_ms, args.max_frames, args.min_width)
    if window is None:
        raise SystemExit("no frame has a vehicle that wide; lower --min-width or use another clip")
    for f in window["frames"]:
        print(f"  source {f['ms']:>6} ms -> {args.clip} {f['clip_ms']:>6} ms, vehicle {f['width']} px")
    add_rows(args.manifest, args.clip, window, record, args.density)
    print(f"added {len(window['frames'])} rows to {shown(args.manifest)}\nnext:\n"
          f"  python tools/synth_fog.py make {shown(source)} data/clips/{args.clip} "
          f"--start-ms {window['start_ms']} --end-ms {window['end_ms']} --density {args.density} --horizon <row>")


if __name__ == "__main__":
    main()
