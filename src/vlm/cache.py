
from __future__ import annotations

import json
from pathlib import Path
from typing import Any


VALID_CONDITIONS = {"orig", "fixed", "adaptive"}


def get_cache_path(
    condition: str,
    clip: str,
    root: str | Path = "results/vlm",
) -> Path:
    """Build the cache path for a condition and clip."""

    if condition not in VALID_CONDITIONS:
        raise ValueError(f"Invalid condition: {condition}")

    clip_name = Path(clip).stem

    if not clip_name or Path(clip).name != clip:
        raise ValueError("Clip must be a filename, not a path.")

    return Path(root) / condition / f"{clip_name}.json"


def save_cache(data: dict[str, Any], path: str | Path) -> Path:
    """Save a VLM response as a JSON cache file."""

    cache_path = Path(path)
    cache_path.parent.mkdir(parents=True, exist_ok=True)

    with open(cache_path, "w", encoding="utf-8") as file:
        json.dump(data, file, ensure_ascii=False, indent=4)

    return cache_path


def load_cache(path: str | Path) -> dict[str, Any] | None:
    """Load a cached VLM response."""

    cache_path = Path(path)

    if not cache_path.exists():
        return None

    with open(cache_path, "r", encoding="utf-8") as file:
        return json.load(file)


def save_vlm_cache(
    data: dict[str, Any],
    condition: str,
    clip: str,
) -> Path:
    """Save a VLM response using the project cache structure."""

    path = get_cache_path(condition, clip)
    return save_cache(data, path)


def load_vlm_cache(
    condition: str,
    clip: str,
) -> dict[str, Any] | None:
    """Load a VLM response using the project cache structure."""

    path = get_cache_path(condition, clip)
    return load_cache(path)
