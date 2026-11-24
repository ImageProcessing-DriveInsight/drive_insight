
"""Experiment runner for DriveInsight."""

import json
import hashlib
import csv
from pathlib import Path

from src.common.utils import get_logger, Timer, get_project_root

logger = get_logger(__name__)

VALID_CONDITIONS = {"orig", "fixed", "adaptive"}
VALID_STEPS = {"enhance", "ocr", "vlm"}

# Temporary values until the team selects the actual models and prompt.
MODEL_VERSIONS = {
    "enhancement": "not_configured",
    "ocr": "not_configured",
    "vlm": "not_configured",
}

PROMPT_VERSION = "DriveInsight VLM prompt not configured yet"


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

    # Calculate the prompt hash.
    prompt_hash = hashlib.sha256(
        PROMPT_VERSION.encode("utf-8")
    ).hexdigest()

    # Save the experiment configuration.
    config = {
        "condition": condition,
        "steps": steps,
        "model_versions": MODEL_VERSIONS,
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


def save_timing_csv(result_dir, timing_rows):
    """Save experiment timing information to timing.csv."""

    timing_path = result_dir / "timing.csv"
    result_dir.mkdir(parents=True, exist_ok=True)

    fieldnames = [
        "frame",
        "condition",
        "enhance_ms",
        "ocr_ms",
        "vlm_ms",
        "total_ms",
    ]

    with open(timing_path, "w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(timing_rows)

    logger.info("Timing CSV saved to %s", timing_path)

    return timing_path