"""Streaming video and lossless frame I/O. All frames are uint8 BGR."""
from pathlib import Path
import csv
import math
import os
import tempfile
import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[2]


def resolve(path, root=ROOT):
    path = Path(path)
    return path if path.is_absolute() else Path(root) / path


def validate_frame(frame):
    if not isinstance(frame, np.ndarray) or frame.dtype != np.uint8:
        raise ValueError('frame must be a uint8 numpy array')
    if frame.ndim != 3 or frame.shape[2] != 3 or min(frame.shape[:2]) < 1:
        raise ValueError('frame must have shape (H, W, 3)')
    return frame


def load_frame(path):
    path = resolve(path)
    img = cv2.imdecode(np.fromfile(path, dtype=np.uint8), cv2.IMREAD_COLOR)
    if img is None:
        raise ValueError(f'Cannot decode image: {path}')
    return validate_frame(img)


def save_frame(path, frame):
    path = resolve(path)
    validate_frame(frame)
    if path.suffix.lower() != '.png':
        raise ValueError('Frame output must be lossless PNG')
    path.parent.mkdir(parents=True, exist_ok=True)
    ok, encoded = cv2.imencode('.png', frame)
    if not ok:
        raise OSError(f'Cannot encode: {path}')
    encoded.tofile(path)
    return path


def _capture(path):
    path = resolve(path)
    cap = cv2.VideoCapture(str(path))
    if not cap.isOpened():
        cap.release()
        raise OSError(f'Cannot open video: {path}')
    return cap


def get_meta(path):
    cap = _capture(path)
    try:
        fps = float(cap.get(cv2.CAP_PROP_FPS))
        count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        if not math.isfinite(fps) or fps <= 0:
            raise ValueError('Video has invalid FPS')
        return {'fps': fps, 'frame_count': count, 'duration': count / fps,
                'width': int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)),
                'height': int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))}
    finally:
        cap.release()


def read_video(path):
    cap = _capture(path)
    try:
        while True:
            ok, frame = cap.read()
            if not ok:
                break
            yield validate_frame(frame)
    finally:
        cap.release()


def write_video(frames, fps, path, *, codec='mp4v'):
    """Publish only after successful encoding; never retain a partial output."""
    if not math.isfinite(fps) or fps <= 0 or len(codec) != 4:
        raise ValueError('Valid positive FPS and four-character codec required')
    path = resolve(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    iterator = iter(frames)
    writer = None
    temporary = None
    try:
        try:
            first = validate_frame(next(iterator))
        except StopIteration as exc:
            raise ValueError('Cannot write an empty video') from exc
        height, width = first.shape[:2]
        if width % 2 or height % 2:
            raise ValueError('Video dimensions must be even; refuse silent codec cropping')
        fd, name = tempfile.mkstemp(suffix=path.suffix, dir=path.parent)
        os.close(fd)
        temporary = Path(name)
        writer = cv2.VideoWriter(str(temporary), cv2.VideoWriter_fourcc(*codec), fps, (width, height))
        if not writer.isOpened():
            raise OSError(f'Codec unavailable: {codec}')
        writer.write(first)
        count = 1
        for frame in iterator:
            validate_frame(frame)
            if frame.shape != first.shape:
                raise ValueError('Video frame dimensions changed')
            writer.write(frame)
            count += 1
        writer.release()
        writer = None
        meta = get_meta(temporary)
        if meta['frame_count'] != count or not math.isclose(meta['fps'], fps, rel_tol=1e-3):
            raise OSError('Encoded video FPS/frame count mismatch')
        temporary.replace(path)
        return path
    finally:
        if writer is not None:
            writer.release()
        if hasattr(iterator, 'close'):
            iterator.close()
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def extract_frames(clip, timestamps, *, output_dir=None):
    """Integer milliseconds, nearest CFR frame (half-up), sequential decoding.

    CFR is required. OpenCV metadata is insufficient to validate arbitrary VFR
    timestamps. Repeated/out-of-range timestamps are rejected, never clamped.
    """
    clip = resolve(clip)
    timestamps = list(timestamps)
    if any(isinstance(t, bool) or not isinstance(t, (int, np.integer)) or t < 0 for t in timestamps):
        raise ValueError('timestamps must be nonnegative integer milliseconds')
    if len(set(timestamps)) != len(timestamps):
        raise ValueError('Duplicate timestamps would overwrite PNG files')
    meta = get_meta(clip)
    targets = {}
    for t in timestamps:
        index = int(math.floor(t * meta['fps'] / 1000 + 0.5))
        if t >= meta['duration'] * 1000 or index >= meta['frame_count']:
            raise ValueError(f'Timestamp outside video: {t}')
        targets.setdefault(index, []).append(t)
    output_dir = resolve(output_dir or 'data/frames/orig')
    results = {}
    stream = read_video(clip)
    try:
        for index, frame in enumerate(stream):
            for t in targets.get(index, []):
                results[t] = save_frame(output_dir / f'{clip.stem}_{t}.png', frame)
            if len(results) == len(timestamps):
                break
    finally:
        stream.close()
    if len(results) != len(timestamps):
        raise OSError('Video ended before requested frames; check damaged input')
    return [results[t] for t in timestamps]


def extract_eval_set(csv_path='data/eval_set.csv', *, root=ROOT):
    root = Path(root).resolve()
    with resolve(csv_path, root).open(encoding='utf-8-sig', newline='') as f:
        reader = csv.DictReader(f)
        if not {'clip', 'timestamp_ms', 'condition'} <= set(reader.fieldnames or []):
            raise ValueError('eval_set.csv requires clip,timestamp_ms,condition')
        rows = list(reader)
    groups, seen, stems = {}, set(), {}
    for row in rows:
        path = (root / 'data/clips' / row['clip']).resolve()
        if not path.is_relative_to(root / 'data/clips') or not path.is_file():
            raise ValueError(f'Invalid clip path: {row["clip"]}')
        if path.stem in stems and stems[path.stem] != path:
            raise ValueError('Clip stems must be unique')
        stems[path.stem] = path
        t = int(row['timestamp_ms'])
        key = (path, t)
        if key in seen:
            raise ValueError('Duplicate eval row')
        seen.add(key)
        groups.setdefault(path, []).append(t)
    return [p for clip, ts in groups.items() for p in
            extract_frames(clip, ts, output_dir=root / 'data/frames/orig')]
