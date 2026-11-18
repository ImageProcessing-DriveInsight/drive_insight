"""Synthetic fog for clear-day clips (ALL-01, issue #61).

No public Korean fog footage with readable plates was found, so the fog clips are made
from clear-day clips with the atmospheric scattering model

    I = J * t + A * (1 - t),   t = exp(-beta * d),   beta = 3.912 / visibility

J is the clear frame, A the fog brightness (airlight), d the distance in meters and
visibility the distance at which contrast falls to 2 % (Koschmieder). d assumes a flat
road seen by a level camera: d = near * (H - 1 - horizon) / (y - horizon) below the
horizon row, and `far` from the horizon up. A vehicle stands upright, so inside each
vehicle mask (YOLOv8n-seg on the clear frame) d is the road distance of the mask bottom,
where the vehicle meets the road; otherwise the top of a near car would vanish like the
sky. So the fog thickens with distance, which a global histogram equalization cannot
undo. A uniform fog is a global linear map and would be undone almost exactly. Far parts
are also blurred a little (forward scattering), and every frame gets sensor noise. All
frames of a clip share the same settings; only the noise and the masks change.

preview    one frame, clear and foggy side by side with the horizon row marked
make       clear clip -> foggy clip, plus its settings in <clip>.fog.json
reference  clear frames named like the foggy eval frames, for labeling

Previews and clear frames show real plates. They go to data/frames/preview/ and
data/frames/clear/, which git ignores.

Usage:
    python tools/synth_fog.py preview SOURCE --at MS [fog options]
    python tools/synth_fog.py make SOURCE OUT [--start-ms MS] [--end-ms MS] [fog options]
    python tools/synth_fog.py reference CLIP [--timestamps MS ...] [--source SOURCE]
"""

import argparse
import csv
import hashlib
import json
import math
import os
import sys
import tempfile
import time
from dataclasses import asdict, dataclass
from datetime import date
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.dip.ops import gaussian  # noqa: E402
from src.io.video import get_meta, read_video, resolve, save_frame, write_video  # noqa: E402

PRESETS = {"light": 300.0, "medium": 150.0, "heavy": 75.0}  # visibility in meters
KOSCHMIEDER = math.log(50)  # 3.912: contrast threshold of 2 %
MODEL = ("I = J*t + A*(1-t), t = exp(-beta*d), beta = 3.912/visibility; d from the horizon row "
         "(flat road), inside vehicle masks the road distance of the mask bottom")
SEG_WEIGHTS = ROOT / "weights" / "yolov8n-seg.pt"  # downloaded on first use, ignored by git
VIDEO_TYPES = (".mp4", ".avi", ".mov", ".mkv")  # what tools.prepare_data accepts
CODECS = ("avc1", "mp4v")  # H.264 where the OpenCV build can write it, else MPEG-4
EVAL_SET = ROOT / "data" / "eval_set.csv"
CLEAR = ROOT / "data" / "frames" / "clear"
PREVIEW = ROOT / "data" / "frames" / "preview"
HORIZON_COLOR = (0, 0, 255)  # BGR red
SHOW_AT = (10, 20, 40)  # m, distances whose transmission is printed


@dataclass(frozen=True)
class Fog:
    visibility: float = PRESETS["medium"]  # m
    horizon: float = 0.5  # horizon row as a share of the frame height, from the top
    near: float = 4.0  # m, distance of the bottom row
    far: float = 300.0  # m, distance from the horizon up
    airlight: float = 0.8  # fog brightness, 0..1 of white
    blur: float = 1.5  # Gaussian sigma in px on a 1080-row frame, applied by (1 - t)
    noise: float = 2.0  # sensor noise sigma in 8-bit levels
    seed: int = 0
    vehicles: bool = True  # vehicle masks get the distance of their bottom row

    def __post_init__(self):
        numbers = (self.visibility, self.horizon, self.near, self.far, self.airlight, self.blur, self.noise)
        if any(isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) for v in numbers):
            raise ValueError("fog settings must be finite numbers")
        if self.visibility <= 0 or not 0 < self.horizon < 1 or not 0 < self.near < self.far:
            raise ValueError("need visibility > 0, 0 < horizon < 1 and 0 < near < far")
        if not 0 <= self.airlight <= 1 or self.blur < 0 or self.noise < 0:
            raise ValueError("need 0 <= airlight <= 1, blur >= 0 and noise >= 0")
        if isinstance(self.seed, bool) or not isinstance(self.seed, int) or not isinstance(self.vehicles, bool):
            raise ValueError("seed must be an integer and vehicles true or false")

    @property
    def beta(self):
        return KOSCHMIEDER / self.visibility


def distance(height, fog):
    """Distance in meters of every row of a frame (shape (height,))."""
    y_h = fog.horizon * (height - 1)
    rows = np.arange(height, dtype=np.float64)
    below = rows > y_h
    d = np.full(height, fog.far)
    d[below] = fog.near * (height - 1 - y_h) / (rows[below] - y_h)
    return np.minimum(d, fog.far)


def transmission(height, fog):
    """Share of the scene light that reaches the camera, per row of the road (shape (height,))."""
    return np.exp(-fog.beta * distance(height, fog))


def transmission_map(shape, fog, masks=()):
    """Transmission of every pixel (shape (H, W)).

    The road model per row; inside each vehicle mask (bool, H x W) the value at the mask's
    bottom row, where the vehicle meets the road. Where masks overlap, the nearer one wins.
    """
    h, w = shape[:2]
    road = transmission(h, fog)
    t = np.repeat(road[:, None], w, axis=1)
    for mask in masks:
        rows = np.flatnonzero(mask.any(axis=1))
        if rows.size:
            t[mask] = np.maximum(t[mask], road[rows[-1]])
    return t


def shrink(mask, n):
    """Mask eroded by n pixels (4-neighbour), so its edge does not carry the background along."""
    for _ in range(n):
        inner = mask.copy()
        inner[1:] &= mask[:-1]
        inner[:-1] &= mask[1:]
        inner[:, 1:] &= mask[:, :-1]
        inner[:, :-1] &= mask[:, 1:]
        mask = inner
    return mask


_seg_model = None


def vehicle_masks(frame):
    """Vehicle masks (bool, H x W) from YOLOv8n-seg, with the pipeline's classes and threshold.

    Masks run a little past the vehicle, so they are shrunk by 2 px per 1080 rows.
    """
    global _seg_model
    from src.plate.detect import VEHICLE_CLASSES, VEHICLE_CONF

    if _seg_model is None:
        from ultralytics import YOLO  # heavy import, load once

        _seg_model = YOLO(str(SEG_WEIGHTS))
    r = _seg_model.predict(frame, conf=VEHICLE_CONF, classes=list(VEHICLE_CLASSES), retina_masks=True,
                           verbose=False)[0]
    n = max(1, round(2 * frame.shape[0] / 1080))
    return [] if r.masks is None else [shrink(m > 0.5, n) for m in r.masks.data.cpu().numpy()]


def add_fog(frame, fog, rng, masks=()):
    """Foggy copy of a uint8 BGR frame. rng draws the sensor noise; masks are its vehicles."""
    h = frame.shape[0]
    t = transmission_map(frame.shape, fog, masks if fog.vehicles else ()).astype(np.float32)[..., None]
    clear = frame.astype(np.float32)
    sigma = fog.blur * h / 1080
    if sigma > 0:
        ksize = min(9, max(3, 2 * math.ceil(3 * sigma) + 1))  # gaussian takes 3..9
        clear = t * clear + (1 - t) * gaussian(frame, ksize, sigma).astype(np.float32)
    out = clear * t + np.float32(255 * fog.airlight) * (1 - t)
    if fog.noise > 0:
        out += np.float32(fog.noise) * rng.standard_normal(frame.shape, dtype=np.float32)
    return np.clip(np.rint(out), 0, 255).astype(np.uint8)


def frame_index(ms, fps):
    """Nearest frame, rounding half up, the same as src.io.video.extract_frames."""
    return int(math.floor(ms * fps / 1000 + 0.5))


def sha256(path):
    digest = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def shown(path):
    """Path relative to the repository when inside it, so records do not hold home folders."""
    path = Path(path).resolve()
    return path.relative_to(ROOT).as_posix() if path.is_relative_to(ROOT) else str(path)


def write_json(path, data):
    path = Path(path)
    handle, tmp = tempfile.mkstemp(prefix=".fog-", suffix=".json", dir=path.parent)
    try:
        with os.fdopen(handle, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        os.replace(tmp, path)
    finally:
        Path(tmp).unlink(missing_ok=True)


def settings_path(clip):
    return Path(clip).with_suffix(".fog.json")


def pick_codec(path, size, codecs=CODECS):
    """First codec this OpenCV build can write for the file type."""
    for codec in codecs:
        with tempfile.TemporaryDirectory() as tmp:
            writer = cv2.VideoWriter(str(Path(tmp) / f"probe{path.suffix}"), cv2.VideoWriter_fourcc(*codec),
                                     30, size)
            ok = writer.isOpened()
            writer.release()
        if ok:
            return codec
    raise OSError(f"none of {codecs} can write {path.suffix} here")


def read_frame(path, index):
    stream = read_video(path)
    try:
        for i, frame in enumerate(stream):
            if i == index:
                return frame
    finally:
        stream.close()
    raise ValueError(f"{path} has no frame {index}")


def masks_of(frame, fog, detector):
    return (detector or vehicle_masks)(frame) if fog.vehicles else ()


def fog_frames(source, fog, first, stop, detector=None):
    rng = np.random.default_rng(fog.seed)
    stream = read_video(source)
    try:
        for i, frame in enumerate(stream):
            if i >= stop:
                break
            if i >= first:
                yield add_fog(frame, fog, rng, masks_of(frame, fog, detector))
    finally:
        stream.close()


def preview(source, at_ms, fog, out=None, detector=None):
    """Clear and foggy frame side by side, the horizon row in red on both. Returns the PNG path."""
    source = resolve(source)
    meta = get_meta(source)
    frame = read_frame(source, frame_index(at_ms, meta["fps"]))
    foggy = add_fog(frame, fog, np.random.default_rng(fog.seed), masks_of(frame, fog, detector))
    row = round(fog.horizon * (frame.shape[0] - 1))
    pair = np.hstack([frame, foggy])
    pair[max(0, row - 1):row + 1] = HORIZON_COLOR
    out = resolve(out) if out else PREVIEW / f"{source.stem}_{at_ms}_{fog.visibility:g}m.png"
    return save_frame(out, pair)


def make(source, out, fog, start_ms=0, end_ms=None, codecs=CODECS, detector=None):
    """Write the foggy clip and its settings file. Returns the settings record.

    detector(frame) -> vehicle masks; the default runs YOLOv8n-seg on every clear frame.
    """
    source, out = resolve(source), resolve(out)
    if out.suffix.lower() not in VIDEO_TYPES:
        raise ValueError(f"output must be one of {VIDEO_TYPES}")
    if out.exists() or settings_path(out).exists():
        raise FileExistsError(f"{out} or its settings already exist; move them away first")
    if out.resolve() == source.resolve():
        raise ValueError("output must not replace the source clip")
    meta = get_meta(source)
    first = frame_index(start_ms, meta["fps"])
    stop = meta["frame_count"] if end_ms is None else min(frame_index(end_ms, meta["fps"]), meta["frame_count"])
    if start_ms < 0 or first >= stop:
        raise ValueError(f"no frames between {start_ms} ms and {end_ms} ms")
    out.parent.mkdir(parents=True, exist_ok=True)
    codec = pick_codec(out, (meta["width"], meta["height"]), codecs)
    write_video(fog_frames(source, fog, first, stop, detector), meta["fps"], out, codec=codec)
    frames = get_meta(out)["frame_count"]  # write_video checked it against the frames written
    record = {"tool": "tools/synth_fog.py", "model": MODEL, "created": date.today().isoformat(),
              "source": shown(source), "source_sha256": sha256(source),
              "start_ms": start_ms, "end_ms": end_ms, "first_frame": first, "frames": frames,
              "fps": meta["fps"], "width": meta["width"], "height": meta["height"], "codec": codec,
              "settings": asdict(fog), "beta": fog.beta}
    write_json(settings_path(out), record)
    return record


def eval_timestamps(clip, eval_set=EVAL_SET):
    with Path(eval_set).open(encoding="utf-8-sig", newline="") as f:
        return [int(row["timestamp_ms"]) for row in csv.DictReader(f) if row["clip"] == clip.name]


def reference(clip, timestamps=None, eval_set=EVAL_SET, out_dir=CLEAR, source=None):
    """Clear source frames saved as <clip stem>_<ms>.png, the names of the foggy eval frames."""
    clip = resolve(clip)
    record = json.loads(settings_path(clip).read_text(encoding="utf-8"))
    source = resolve(source or record["source"])
    if sha256(source) != record["source_sha256"]:
        raise ValueError(f"{source} is not the clip {clip.name} was made from")
    timestamps = list(timestamps) if timestamps else eval_timestamps(clip, eval_set)
    if not timestamps:
        raise ValueError(f"no timestamps for {clip.name}; pass --timestamps or add rows to {eval_set}")
    if len(set(timestamps)) != len(timestamps):
        raise ValueError("duplicate timestamps")
    meta = get_meta(clip)
    wanted = {}
    for ms in timestamps:
        index = frame_index(ms, meta["fps"])
        if ms < 0 or index >= min(meta["frame_count"], record["frames"]):
            raise ValueError(f"{ms} ms is outside {clip.name}")
        wanted.setdefault(record["first_frame"] + index, []).append(ms)
    out_dir, saved = resolve(out_dir), {}
    stream = read_video(source)
    try:
        for i, frame in enumerate(stream):
            for ms in wanted.get(i, []):
                saved[ms] = save_frame(out_dir / f"{clip.stem}_{ms}.png", frame)
            if len(saved) == len(timestamps):
                break
    finally:
        stream.close()
    if len(saved) != len(timestamps):
        raise OSError(f"{source} ended before all frames were found")
    return [saved[ms] for ms in timestamps]


def describe(fog):
    kept = ", ".join(f"{d} m: {math.exp(-fog.beta * d):.2f}" for d in SHOW_AT)
    return f"visibility {fog.visibility:g} m; share of light kept at {kept}"


def add_fog_options(p):
    p.add_argument("--density", choices=PRESETS, default="medium",
                   help="visibility preset: " + ", ".join(f"{k} {v:g} m" for k, v in PRESETS.items()))
    p.add_argument("--visibility", type=float, help="visibility in meters (overrides --density)")
    for name, help_text in (("horizon", "horizon row as a share of the height, from the top"),
                            ("near", "distance of the bottom row in meters"),
                            ("far", "distance from the horizon up in meters"),
                            ("airlight", "fog brightness, 0..1"),
                            ("blur", "forward-scatter blur sigma in px at 1080 rows"),
                            ("noise", "sensor noise sigma in 8-bit levels")):
        p.add_argument(f"--{name}", type=float, default=getattr(Fog, name), help=help_text)
    p.add_argument("--seed", type=int, default=Fog.seed)
    p.add_argument("--no-vehicles", action="store_true",
                   help="road model only, without vehicle masks (no YOLO)")


def fog_from(args):
    visibility = PRESETS[args.density] if args.visibility is None else args.visibility
    return Fog(visibility=visibility, horizon=args.horizon, near=args.near, far=args.far,
               airlight=args.airlight, blur=args.blur, noise=args.noise, seed=args.seed,
               vehicles=not args.no_vehicles)


def main():
    ap = argparse.ArgumentParser(description="Synthetic fog for clear-day clips.")
    sub = ap.add_subparsers(dest="command", required=True)
    p = sub.add_parser("preview", help="one frame, clear and foggy, with the horizon row")
    p.add_argument("source", type=Path)
    p.add_argument("--at", type=int, default=0, help="timestamp in ms")
    p.add_argument("--out", type=Path, help=f"PNG path (default: {shown(PREVIEW)}/...)")
    add_fog_options(p)
    p = sub.add_parser("make", help="foggy clip and its settings file")
    p.add_argument("source", type=Path)
    p.add_argument("out", type=Path, help="foggy clip, e.g. data/clips/fog_01.mp4")
    p.add_argument("--start-ms", type=int, default=0)
    p.add_argument("--end-ms", type=int, help="default: end of the source")
    add_fog_options(p)
    p = sub.add_parser("reference", help="clear frames named like the foggy eval frames")
    p.add_argument("clip", type=Path, help="foggy clip made by `make`")
    p.add_argument("--timestamps", type=int, nargs="+", help=f"default: rows of {shown(EVAL_SET)}")
    p.add_argument("--eval-set", type=Path, default=EVAL_SET)
    p.add_argument("--source", type=Path, help="clear clip, if it moved since `make`")
    p.add_argument("--out-dir", type=Path, default=CLEAR)
    args = ap.parse_args()

    if args.command == "preview":
        fog = fog_from(args)
        print(f"{describe(fog)}\nwrote {preview(args.source, args.at, fog, args.out)}")
    elif args.command == "make":
        fog, start = fog_from(args), time.perf_counter()
        record = make(args.source, args.out, fog, args.start_ms, args.end_ms)
        print(f"{describe(fog)}\nwrote {record['frames']} frames ({record['codec']}) to {args.out} in "
              f"{time.perf_counter() - start:.0f} s; settings in {settings_path(args.out)}")
    else:
        paths = reference(args.clip, args.timestamps, args.eval_set, args.out_dir, args.source)
        print(f"wrote {len(paths)} clear frames to {args.out_dir}")


if __name__ == "__main__":
    main()
