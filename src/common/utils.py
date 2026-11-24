"""Shared utilities for the DriveInsight project."""

import logging
import time
from pathlib import Path

import cv2
import numpy as np
PROJECT_ROOT = Path(__file__).resolve().parents[2]


def get_project_root():
    """Return the absolute project root directory."""
    return PROJECT_ROOT


def get_paths():
    """Return commonly used project paths."""
    return {
        "root": PROJECT_ROOT,
        "data": PROJECT_ROOT / "data",
        "frames": PROJECT_ROOT / "data" / "frames",
        "results": PROJECT_ROOT / "results",
        "weights": PROJECT_ROOT / "weights",
        "src": PROJECT_ROOT / "src",
    }


def validate_frame(frame):
    """Check that a frame is a uint8 BGR image."""
    if not isinstance(frame, np.ndarray):
        raise ValueError("Frame must be a NumPy array.")

    if frame.dtype != np.uint8:
        raise ValueError("Frame must use uint8 data.")

    if frame.ndim != 3 or frame.shape[2] != 3:
        raise ValueError("Frame must have shape (H, W, 3).")

    return frame


def load_frame(path):
    """Load an image as a uint8 BGR frame."""
    path = Path(path)

    frame = cv2.imread(str(path), cv2.IMREAD_COLOR)

    if frame is None:
        raise FileNotFoundError(f"Cannot load image: {path}")

    return validate_frame(frame)


def save_frame(path, frame):
    """Save a uint8 BGR frame as a PNG image."""
    validate_frame(frame)

    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    success = cv2.imwrite(str(path), frame)

    if not success:
        raise ValueError(f"Cannot save image: {path}")

    return path


def get_logger(name="drive_insight"):
    """Create a logger for the project."""
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)

    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(
            logging.Formatter(
                "%(asctime)s - %(levelname)s - %(message)s"
            )
        )
        logger.addHandler(handler)

    return logger


class Timer:
    """Measure how long an operation takes."""

    def __enter__(self):
        self.start = time.perf_counter()
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.elapsed_ms = (
            time.perf_counter() - self.start
        ) * 1000