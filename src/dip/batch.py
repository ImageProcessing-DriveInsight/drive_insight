"""Generate lossless fixed frames: python -m src.dip.batch --help."""

import argparse
import json
import os
from pathlib import Path
import tempfile
import time

from src.io.video import load_frame, resolve, save_frame
from .fixed import fixed_enhance


def _png_files(directory):
    return sorted((p for p in directory.iterdir() if p.suffix.lower() == ".png"),
                  key=lambda p: p.name)


def _atomic_save(path, writer):
    """Publish one complete file; a failed encode/write leaves its old file intact."""
    handle, name = tempfile.mkstemp(prefix=".fixed-", suffix=path.suffix, dir=path.parent)
    os.close(handle)
    temporary = Path(name)
    try:
        writer(temporary)
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def enhance_fixed_frames(input_dir="data/frames/orig", output_dir="data/frames/fixed",
                         params_path="results/params/fixed.json"):
    """Return filename -> {params, enhance_ms, total_ms} and write PNGs plus JSON.

    Relative paths resolve against the project root. Frame directories must be
    disjoint and the JSON log must be outside both. Existing matching outputs may
    be replaced; stale PNG names are rejected before writing. Once work starts,
    invalidate the previous log so failures cannot leave a success-looking log.
    Frames publish individually, not as a transaction for the whole directory.
    """
    source, output, log = (resolve(p).resolve() for p in (input_dir, output_dir, params_path))
    if source == output or source.is_relative_to(output) or output.is_relative_to(source):
        raise ValueError("Input and output frame directories must not overlap")
    if log.is_relative_to(source) or log.is_relative_to(output):
        raise ValueError("Parameter log must be outside both frame directories")
    if log.suffix.lower() != ".json" or (log.exists() and not log.is_file()):
        raise ValueError("params_path must be a JSON file path")
    if not source.is_dir():
        raise ValueError(f"Input frame directory not found: {source}")
    if output.exists() and not output.is_dir():
        raise ValueError("output_dir must be a directory")
    files = _png_files(source)
    if not files:
        raise ValueError(f"No PNG frames: {source}")
    for path in files:
        if not path.is_file() or path.is_symlink():
            raise ValueError(f"Input PNG must be a regular, non-symlink file: {path}")
    names = {p.name for p in files}
    existing = _png_files(output) if output.exists() else []
    if {p.name for p in existing} - names:
        raise ValueError("Stale output PNG files; use a clean output directory")
    for path in existing:
        if path.is_symlink() or not path.is_file():
            raise ValueError(f"Output PNG must be a regular, non-symlink file: {path}")

    output.mkdir(parents=True, exist_ok=True)
    log.parent.mkdir(parents=True, exist_ok=True)
    log.unlink(missing_ok=True)
    records = {}
    for path in files:
        total_start = time.perf_counter()
        frame = load_frame(path)
        enhance_start = time.perf_counter()
        out, params = fixed_enhance(frame)
        enhance_ms = (time.perf_counter() - enhance_start) * 1000
        if out.shape != frame.shape or out.dtype != frame.dtype:
            raise ValueError(f"Fixed enhancement changed frame shape or dtype: {path.name}")
        _atomic_save(output / path.name, lambda temporary: save_frame(temporary, out))
        records[path.name] = {
            "params": params,
            "enhance_ms": enhance_ms,
            "total_ms": (time.perf_counter() - total_start) * 1000,
        }
    if {p.name for p in _png_files(source)} != names or {p.name for p in _png_files(output)} != names:
        raise ValueError("PNG file lists changed during processing; rerun without concurrent writers")
    text = json.dumps(records, ensure_ascii=False, indent=2, allow_nan=False)
    _atomic_save(log, lambda temporary: temporary.write_text(text, encoding="utf-8"))
    return records


def main(argv=None):
    parser = argparse.ArgumentParser(description="Generate fixed PNG frames and per-frame parameter/timing logs")
    parser.add_argument("--input-dir", default="data/frames/orig")
    parser.add_argument("--output-dir", default="data/frames/fixed")
    parser.add_argument("--params-path", default="results/params/fixed.json")
    args = parser.parse_args(argv)
    try:
        records = enhance_fixed_frames(args.input_dir, args.output_dir, args.params_path)
    except (ValueError, OSError) as exc:
        parser.exit(1, f"Fixed frame generation failed: {exc}\n")
    print(f"Generated {len(records)} fixed PNG frames; log: {resolve(args.params_path)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
