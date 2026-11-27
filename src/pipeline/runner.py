
"""Experiment runner for DriveInsight."""

import json
import hashlib
import csv
import time
import tempfile
import shutil
import re
from pathlib import Path

from src.common.utils import get_logger, Timer, get_project_root

logger = get_logger(__name__)

VALID_CONDITIONS = {"orig", "fixed", "adaptive"}
VALID_STEPS = {"enhance", "ocr", "vlm"}

# Models used by each step (see the README table of pretrained models).
MODEL_VERSIONS = {
    "enhancement": "own NumPy implementation (src.dip, src.adaptive)",
    "vehicle_detection": "YOLOv8n, ultralytics 8.4.208, COCO weights",
    "ocr": "PaddleOCR 3.7.0, korean PP-OCRv5",
    "vlm": "ollama qwen3-vl:4b-instruct",
}


def _vlm_model_and_prompt():
    """Return the VLM model name and the prompt the client really sends."""
    from src.vlm.client import MODEL_NAME, SYSTEM_PROMPT

    return MODEL_NAME, SYSTEM_PROMPT


def _frame_sort_key(path):
    """Sort <clip>_<number>.png by the number, so _500 comes before _3500."""
    match = re.search(r"_(\d+)$", path.stem)
    number = int(match.group(1)) if match else -1
    return (re.sub(r"_\d+$", "", path.stem), number, path.name)


def _group_frames_by_clip(frames_dir):
    """Group PNG frames by clip ID, removing the final numeric suffix."""
    frames_dir = Path(frames_dir)
    files = sorted(frames_dir.glob("*.png"))

    if not files:
        raise FileNotFoundError(f"No PNG frames found: {frames_dir}")

    groups = {}
    for path in files:
        clip_id = re.sub(r"_\d+$", "", path.stem)
        groups.setdefault(clip_id, []).append(path)

    for paths in groups.values():
        paths.sort(key=_frame_sort_key)

    return groups


def _merge_vlm_responses(responses):
    """Merge per-frame VLM responses into one clip-level summary."""
    from src.vlm.schema import validate_vlm_response

    merged = {
        "vehicles": [],
        "events": [],
        "visibility_notes": [],
        "uncertain": [],
    }

    for frame_number, response in responses:
        if not validate_vlm_response(response):
            raise ValueError(
                f"Invalid VLM response for frame {frame_number}"
            )

        for field in ("vehicles", "visibility_notes", "uncertain"):
            for item in response[field]:
                if item not in merged[field]:
                    merged[field].append(item)

        for event in response["events"]:
            event_copy = dict(event)
            event_copy.setdefault("frame", frame_number)
            if event_copy not in merged["events"]:
                merged["events"].append(event_copy)

    return merged


def _save_json_new(path, data):
    """Save JSON without overwriting an existing file."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    with path.open("x", encoding="utf-8") as file:
        json.dump(data, file, ensure_ascii=False, indent=4, allow_nan=False)
        file.write("\n")

    return path


def _run_ocr_safely(condition, frames_dir, results_dir):
    """Run OCR temporarily, then safely publish its CSV and crop images."""
    from src.plate.run import run_ocr, COLUMNS

    results_dir = Path(results_dir)
    final_csv = results_dir / "ocr" / f"{condition}.csv"
    final_crop_dir = results_dir / "ocr" / "crops" / condition

    if final_csv.exists():
        raise FileExistsError(f"OCR CSV already exists: {final_csv}")
    if final_crop_dir.exists():
        raise FileExistsError(f"OCR crop directory already exists: {final_crop_dir}")

    copied_crops = []
    csv_created = False
    crop_dir_created = False

    try:
        with tempfile.TemporaryDirectory(prefix="driveinsight_ocr_") as tmp:
            temporary_results = Path(tmp)
            csv_path = run_ocr(
                condition,
                frames_dir=frames_dir,
                results_dir=temporary_results,
            )

            with csv_path.open("r", newline="", encoding="utf-8") as file:
                rows = list(csv.DictReader(file))

            expected_frames = {
                path.name for path in Path(frames_dir).glob("*.png")
            }
            actual_frames = {row["frame"] for row in rows}

            if actual_frames != expected_frames:
                raise ValueError("OCR output frame list does not match input frames")

            temporary_crop_dir = (
                temporary_results / "ocr" / "crops" / condition
            )

            final_crop_dir.parent.mkdir(parents=True, exist_ok=True)
            final_crop_dir.mkdir()
            crop_dir_created = True

            if temporary_crop_dir.exists():
                for source in sorted(temporary_crop_dir.glob("*.png")):
                    destination = final_crop_dir / source.name
                    with source.open("rb") as src:
                        with destination.open("xb") as dst:
                            shutil.copyfileobj(src, dst)
                    copied_crops.append(destination)

            for row in rows:
                if row.get("crop_path"):
                    crop_name = Path(row["crop_path"]).name
                    destination = final_crop_dir / crop_name
                    if not destination.is_file():
                        raise FileNotFoundError(
                            f"OCR crop missing: {crop_name}"
                        )
                    row["crop_path"] = destination.relative_to(
                        get_project_root()
                    ).as_posix()

        final_csv.parent.mkdir(parents=True, exist_ok=True)
        with final_csv.open("x", newline="", encoding="utf-8") as file:
            csv_created = True
            writer = csv.DictWriter(file, fieldnames=COLUMNS, restval="")
            writer.writeheader()
            writer.writerows(rows)

        return rows

    except Exception:
        if csv_created:
            final_csv.unlink(missing_ok=True)
        for crop in copied_crops:
            crop.unlink(missing_ok=True)
        if crop_dir_created:
            shutil.rmtree(final_crop_dir, ignore_errors=True)
        raise


def run_experiment(condition, steps=None, frame_lists=None):
    """Validate an experiment and save its configuration."""

    if condition not in VALID_CONDITIONS:
        raise ValueError(
            f"Invalid condition: {condition}. "
            f"Choose from {sorted(VALID_CONDITIONS)}"
        )

    if steps is None:
        steps = ["enhance", "ocr", "vlm"]

    invalid_steps = set(steps) - VALID_STEPS

    if invalid_steps:
        raise ValueError(f"Invalid steps: {sorted(invalid_steps)}")

    if frame_lists is not None:
        lists = list(frame_lists.values())

        if lists and any(frames != lists[0] for frames in lists[1:]):
            raise ValueError(
                "Frame lists do not match across conditions."
            )

    logger.info(
        "Experiment condition: %s | Steps: %s",
        condition,
        steps,
    )

    # Create the project results directory.
    project_root = get_project_root()
    result_dir = project_root / "results" / condition
    result_dir.mkdir(parents=True, exist_ok=True)

    # Hash the prompt the VLM client really sends.
    vlm_model, prompt = _vlm_model_and_prompt()
    prompt_hash = hashlib.sha256(prompt.encode("utf-8")).hexdigest()

    model_versions = dict(MODEL_VERSIONS)
    model_versions["vlm"] = f"ollama {vlm_model}"

    # Save the experiment configuration.
    config = {
        "condition": condition,
        "steps": steps,
        "model_versions": model_versions,
        "prompt_hash": prompt_hash,
    }

    config_path = result_dir / "config_snapshot.json"

    with open(config_path, "w", encoding="utf-8") as file:
        json.dump(config, file, indent=4)

    logger.info("Configuration saved to %s", config_path)

    return {
        "condition": condition,
        "steps": steps,
        "status": "validated",
        "config_path": str(config_path),
    }


TIMING_COLUMNS = [
    "frame",
    "condition",
    "enhance_ms",
    "ocr_ms",
    "vlm_ms",
    "total_ms",
]


def save_timing_csv(result_dir, timing_rows, *, overwrite=False):
    """Save timing.csv without overwriting unless explicitly requested."""

    timing_path = Path(result_dir) / "timing.csv"
    result_dir = Path(result_dir)
    result_dir.mkdir(parents=True, exist_ok=True)
    mode = "w" if overwrite else "x"

    fieldnames = TIMING_COLUMNS

    with open(timing_path, mode, newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(timing_rows)

    logger.info("Timing CSV saved to %s", timing_path)

    return timing_path


def add_timing_rows(result_dir, timing_rows):
    """Add new frames to timing.csv and keep every row already in it.

    A frame already in the file keeps its old row, so no frame is counted twice.
    Returns (path, number of rows added).
    """
    timing_path = Path(result_dir) / "timing.csv"

    if not timing_path.exists():
        save_timing_csv(result_dir, timing_rows)
        return timing_path, len(timing_rows)

    with timing_path.open("r", newline="", encoding="utf-8") as file:
        existing = list(csv.DictReader(file))

    known = {row["frame"] for row in existing}
    new_rows = [row for row in timing_rows if row["frame"] not in known]

    if new_rows:
        save_timing_csv(result_dir, existing + new_rows, overwrite=True)

    return timing_path, len(new_rows)


def execute_experiment(
    condition,
    steps=None,
    *,
    clip_ids=None,
    frames_dir=None,
    results_dir=None,
    offline=False,
):
    """Execute selected experiment steps without overwriting existing outputs.

    With offline=True the VLM is never called: clips with a cached
    results/vlm/<condition>/<clip>.json are reused and the others are listed
    in result["missing_clips"].
    """

    if condition not in VALID_CONDITIONS:
        raise ValueError(f"Invalid condition: {condition}")

    if steps is None:
        steps = ["vlm"]

    steps = list(steps)
    invalid_steps = set(steps) - VALID_STEPS
    if invalid_steps:
        raise ValueError(f"Invalid steps: {sorted(invalid_steps)}")

    root = Path(get_project_root())
    frames_dir = Path(frames_dir) if frames_dir else (
        root / "data" / "frames" / condition
    )
    results_dir = Path(results_dir) if results_dir else root / "results"

    if not frames_dir.is_dir():
        raise FileNotFoundError(f"Frames directory not found: {frames_dir}")

    frame_paths = sorted(frames_dir.glob("*.png"))
    if not frame_paths:
        raise ValueError(f"No PNG frames found in {frames_dir}")

    result = {
        "condition": condition,
        "steps": steps,
        "frames": len(frame_paths),
        "ocr": "not_requested",
        "vlm": "not_requested",
        "processed_clips": [],
        "skipped_clips": [],
        "missing_clips": [],
    }

    timing_rows = []

    # Reuse existing enhancement frames; never regenerate them here.
    if "enhance" in steps:
        result["enhance"] = "reused_existing_frames"

    # Run OCR only when the condition output does not already exist.
    if "ocr" in steps:
        ocr_path = results_dir / "ocr" / f"{condition}.csv"
        crop_dir = results_dir / "ocr" / "crops" / condition

        if ocr_path.exists() or crop_dir.exists():
            result["ocr"] = "skipped_existing_output"
        else:
            _run_ocr_safely(condition, frames_dir, results_dir)
            result["ocr"] = "completed"

    if "vlm" in steps:
        from src.vlm.client import analyze_frame

        clips = _group_frames_by_clip(frames_dir)

        if clip_ids is not None:
            requested = set(clip_ids)
            unknown = requested - set(clips)
            if unknown:
                raise ValueError(f"Unknown clip IDs: {sorted(unknown)}")
            clips = {
                clip_id: paths
                for clip_id, paths in clips.items()
                if clip_id in requested
            }

        vlm_dir = results_dir / "vlm" / condition
        vlm_dir.mkdir(parents=True, exist_ok=True)

        for clip_id, paths in sorted(clips.items()):
            output_path = vlm_dir / f"{clip_id}.json"

            if output_path.exists():
                result["skipped_clips"].append(clip_id)
                continue

            if offline:
                result["missing_clips"].append(clip_id)
                continue

            responses = []

            for frame_number, frame_path in enumerate(paths, start=1):
                start = time.perf_counter()
                response = analyze_frame(
                    frame_path,
                    frame_number=frame_number,
                )
                elapsed_ms = round(
                    (time.perf_counter() - start) * 1000, 2
                )

                responses.append((frame_number, response))
                timing_rows.append({
                    "frame": frame_path.name,
                    "condition": condition,
                    "enhance_ms": "",
                    "ocr_ms": "",
                    "vlm_ms": elapsed_ms,
                    "total_ms": elapsed_ms,
                })

            summary = _merge_vlm_responses(responses)
            _save_json_new(output_path, summary)
            result["processed_clips"].append(clip_id)

        if offline and result["missing_clips"]:
            result["vlm"] = "offline_cache_incomplete"
        elif offline:
            result["vlm"] = "offline_cache"
        else:
            result["vlm"] = "completed"

    if timing_rows:
        _, added = add_timing_rows(results_dir / condition, timing_rows)
        result["timing"] = f"saved_{added}_rows"
    else:
        result["timing"] = "no_new_vlm_timings"

    return result
