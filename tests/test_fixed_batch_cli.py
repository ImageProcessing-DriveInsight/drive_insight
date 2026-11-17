"""CLI, root-relative paths and recovery for the real fixed PNG pipeline."""

import json
import os
from pathlib import Path
import subprocess
import sys

import numpy as np
import pytest

import src.dip.batch as batch
from src.io import save_frame


def test_defaults_resolve_against_project_root_not_cwd(tmp_path, monkeypatch):
    root = tmp_path / "project"
    save_frame(root / "data/frames/orig/clip_0.png", np.full((7, 9, 3), 40, np.uint8))
    elsewhere = tmp_path / "elsewhere"; elsewhere.mkdir()
    monkeypatch.chdir(elsewhere)
    monkeypatch.setattr(batch, "resolve", lambda p: Path(p) if Path(p).is_absolute() else root / p)
    records = batch.enhance_fixed_frames()
    assert set(records) == {"clip_0.png"}
    assert (root / "data/frames/fixed/clip_0.png").exists()
    assert json.loads((root / "results/params/fixed.json").read_text(encoding="utf-8")) == records
    assert list(elsewhere.iterdir()) == []


def _run_cli(tmp_path, source, output, log):
    env = os.environ.copy()
    env["PYTHONPATH"] = str(Path(__file__).resolve().parents[1])
    return subprocess.run(
        [sys.executable, "-m", "src.dip.batch", "--input-dir", str(source),
         "--output-dir", str(output), "--params-path", str(log)],
        cwd=tmp_path, env=env, capture_output=True, text=True, timeout=60,
    )


def test_module_cli_with_actual_png_io(tmp_path):
    source, output, log = tmp_path / "orig", tmp_path / "fixed", tmp_path / "params.json"
    save_frame(source / "clip_0.png", np.full((9, 11, 3), 60, np.uint8))
    result = _run_cli(tmp_path, source, output, log)
    assert result.returncode == 0, result.stderr
    assert "Generated 1 fixed PNG frames" in result.stdout
    assert "RuntimeWarning" not in result.stderr
    assert set(json.loads(log.read_text(encoding="utf-8"))) == {"clip_0.png"}
    assert (output / "clip_0.png").exists()


def test_cli_reports_missing_frames_without_traceback(tmp_path):
    result = _run_cli(tmp_path, tmp_path / "missing", tmp_path / "fixed", tmp_path / "params.json")
    assert result.returncode == 1
    assert "Fixed frame generation failed" in result.stderr
    assert "Traceback" not in result.stderr


def test_failed_mid_batch_can_be_rerun(tmp_path, monkeypatch):
    source, output, log = tmp_path / "orig", tmp_path / "fixed", tmp_path / "params.json"
    for name in ("clip_0.png", "clip_100.png"):
        save_frame(source / name, np.full((7, 9, 3), 70, np.uint8))
    actual = batch.fixed_enhance
    calls = 0
    def fail_second(frame):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise ValueError("second frame failed")
        return actual(frame)
    monkeypatch.setattr(batch, "fixed_enhance", fail_second)
    with pytest.raises(ValueError, match="second frame"):
        batch.enhance_fixed_frames(source, output, log)
    assert {p.name for p in output.iterdir()} == {"clip_0.png"}
    assert not log.exists()
    monkeypatch.setattr(batch, "fixed_enhance", actual)
    assert set(batch.enhance_fixed_frames(source, output, log)) == {"clip_0.png", "clip_100.png"}
    assert log.exists()


def test_exact_timing_scope(tmp_path, monkeypatch):
    source, output, log = tmp_path / "orig", tmp_path / "fixed", tmp_path / "params.json"
    save_frame(source / "clip_0.png", np.full((7, 9, 3), 70, np.uint8))
    times = iter((1.0, 2.0, 2.25, 3.0))
    monkeypatch.setattr(batch.time, "perf_counter", lambda: next(times))
    record = batch.enhance_fixed_frames(source, output, log)["clip_0.png"]
    assert record["enhance_ms"] == 250.0
    assert record["total_ms"] == 2000.0
