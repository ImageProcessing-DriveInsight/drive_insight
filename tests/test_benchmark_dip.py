import json

import numpy as np
import pytest

from tools import benchmark_dip as bench


def test_measurements_count_warmups_and_statistics(monkeypatch):
    calls = []
    monkeypatch.setattr(bench, "median", lambda frame, **params: calls.append(params))
    timestamps = iter((0, .1, 1, 1.3, 2, 2.2))
    monkeypatch.setattr(bench.time, "perf_counter", lambda: next(timestamps))
    result = bench.benchmark_frame(np.zeros((1080, 1920, 3), np.uint8), warmups=2, repeats=3, cases=["median3"])["median3"]
    assert len(calls) == 5
    assert result["samples_ms"] == pytest.approx([100, 300, 200])
    assert result["median_ms"] == pytest.approx(200)
    assert result["p95_ms"] == pytest.approx(290)
    assert result["target_applicable"] and result["target_met"]


@pytest.mark.parametrize("options", [{"warmups": -1}, {"repeats": 0}, {"repeats": True},
    {"cases": []}, {"cases": ["unknown"]}, {"cases": ["median3", "median3"]}])
def test_invalid_measurement_settings(options):
    with pytest.raises(ValueError):
        bench.benchmark_frame(np.zeros((1, 1, 3), np.uint8), **options)


def test_small_cli_report_has_no_1080p_claim(tmp_path):
    out = tmp_path / "report.json"
    assert bench.main(["--width", "7", "--height", "5", "--warmups", "0", "--repeats", "1",
                       "--cases", "gaussian3", "fixed", "--output", str(out)]) == 0
    report = json.loads(out.read_text(encoding="utf-8"))
    assert report["input"]["kind"] == "synthetic_uniform_uint8"
    assert report["input"]["shape"] == [5, 7, 3]
    assert len(report["environment"]["source_sha256"]) == 3
    for row in report["results"].values():
        assert row["target_met"] is None and not row["target_applicable"]
