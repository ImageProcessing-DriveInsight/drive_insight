"""A-09 lossless PNG batch generation and fail-safe output handling."""

import json

import numpy as np
import pytest

from src.dip import FIXED_PARAMS, fixed_enhance
from src.dip.batch import enhance_fixed_frames
import src.dip.batch as batch
from src.io import load_frame, save_frame


@pytest.fixture
def paths(tmp_path):
    source, output, log = tmp_path / "orig", tmp_path / "fixed", tmp_path / "params/fixed.json"
    save_frame(source / "야간_200.PNG", np.full((9, 13, 3), 60, np.uint8))
    save_frame(source / "night_0.png", np.random.default_rng(48).integers(0, 256, (13, 17, 3), dtype=np.uint8))
    return source, output, log


def test_exact_outputs_params_times_and_source_bytes(paths):
    source, output, log = paths
    originals = {p.name: p.read_bytes() for p in source.iterdir()}
    records = enhance_fixed_frames(*paths)
    assert list(records) == sorted(originals)
    assert set(records) == {p.name for p in output.iterdir()}
    assert json.loads(log.read_text(encoding="utf-8")) == records
    for name, record in records.items():
        assert record["params"] == dict(FIXED_PARAMS)
        assert 0 <= record["enhance_ms"] <= record["total_ms"]
        np.testing.assert_array_equal(load_frame(output / name), fixed_enhance(load_frame(source / name))[0])
        assert (source / name).read_bytes() == originals[name]


def test_rerun_replaces_only_matching_outputs(paths):
    source, output, log = paths
    enhance_fixed_frames(*paths)
    save_frame(source / "night_0.png", np.full((5, 7, 3), 90, np.uint8))
    records = enhance_fixed_frames(*paths)
    assert set(records) == {p.name for p in source.iterdir()}
    np.testing.assert_array_equal(load_frame(output / "night_0.png"), fixed_enhance(load_frame(source / "night_0.png"))[0])


def test_stale_outputs_fail_without_changes(paths):
    source, output, log = paths
    save_frame(output / "stale.png", np.full((3, 5, 3), 1, np.uint8))
    log.parent.mkdir(); log.write_text('old', encoding="utf-8")
    before = (output / "stale.png").read_bytes()
    with pytest.raises(ValueError, match="Stale"):
        enhance_fixed_frames(*paths)
    assert (output / "stale.png").read_bytes() == before
    assert log.read_text(encoding="utf-8") == "old"


@pytest.mark.parametrize("overlap", ["same", "child", "parent", "log-source", "log-output"])
def test_path_overlap_rejected(paths, overlap):
    source, output, log = paths
    output = {"same": source, "child": source / "fixed", "parent": source.parent}.get(overlap, output)
    log = source / "params.json" if overlap == "log-source" else output / "params.json" if overlap == "log-output" else log
    before = {p.name: p.read_bytes() for p in source.iterdir()}
    with pytest.raises(ValueError):
        enhance_fixed_frames(source, output, log)
    assert before == {p.name: p.read_bytes() for p in source.iterdir()}


def test_missing_empty_input_and_invalid_paths(paths, tmp_path):
    source, output, log = paths
    empty = tmp_path / "empty"; empty.mkdir()
    for input_dir in (tmp_path / "missing", empty):
        with pytest.raises(ValueError):
            enhance_fixed_frames(input_dir, output, log)
    for target in (source / "params.json", tmp_path / "bad.txt", source):
        with pytest.raises(ValueError):
            enhance_fixed_frames(source, output, target)
    assert not output.exists()


def test_bad_png_invalidates_old_log_and_leaves_no_partial_file(paths):
    source, output, log = paths
    log.parent.mkdir(); log.write_text("old", encoding="utf-8")
    (source / "000_bad.png").write_bytes(b"not an image")
    with pytest.raises(ValueError):
        enhance_fixed_frames(*paths)
    assert not log.exists()
    assert list(output.iterdir()) == []


def test_failed_save_preserves_old_image_and_removes_temporary(paths, monkeypatch):
    source, output, log = paths
    enhance_fixed_frames(*paths)
    before = (output / "night_0.png").read_bytes()
    def broken_save(path, img):
        path.write_bytes(b"incomplete")
        raise OSError("disk full")
    monkeypatch.setattr(batch, "save_frame", broken_save)
    with pytest.raises(OSError, match="disk full"):
        enhance_fixed_frames(*paths)
    assert (output / "night_0.png").read_bytes() == before
    assert not log.exists()
    assert not list(output.glob(".fixed-*"))


def test_log_write_failure_does_not_publish_success(paths, monkeypatch):
    def broken_dumps(*args, **kwargs):
        raise ValueError("serialization failed")
    monkeypatch.setattr(batch.json, "dumps", broken_dumps)
    with pytest.raises(ValueError, match="serialization"):
        enhance_fixed_frames(*paths)
    assert not paths[2].exists()
    assert not list(paths[1].glob(".fixed-*"))
