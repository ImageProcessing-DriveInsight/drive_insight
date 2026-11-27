import json

import pytest

from src.vlm.cache import (
    get_cache_path,
    load_cache,
    load_vlm_cache,
    save_cache,
    save_vlm_cache,
)


def test_get_cache_path():
    path = get_cache_path("orig", "clip01.jpg", root="tmp")
    assert str(path) == "tmp/orig/clip01.json"


def test_rejects_invalid_condition():
    with pytest.raises(ValueError):
        get_cache_path("invalid", "clip01.jpg")


def test_rejects_clip_path():
    with pytest.raises(ValueError):
        get_cache_path("orig", "folder/clip01.jpg")


def test_save_and_load_cache(tmp_path):
    data = {
        "vehicles": ["A white car"],
        "events": [],
        "visibility_notes": [],
        "uncertain": [],
    }

    path = tmp_path / "orig" / "clip01.json"

    saved_path = save_cache(data, path)
    loaded_data = load_cache(path)

    assert saved_path == path
    assert loaded_data == data


def test_load_missing_cache_returns_none(tmp_path):
    path = tmp_path / "missing.json"
    assert load_cache(path) is None


def test_save_and_load_vlm_cache(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    data = {
        "vehicles": ["A bus"],
        "events": [],
        "visibility_notes": [],
        "uncertain": [],
    }

    save_vlm_cache(data, "fixed", "clip02.jpg")
    loaded_data = load_vlm_cache("fixed", "clip02.jpg")

    expected_path = tmp_path / "results" / "vlm" / "fixed" / "clip02.json"

    assert expected_path.is_file()
    assert loaded_data == data
