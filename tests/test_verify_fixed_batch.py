import json

import numpy as np
import pytest

from src.dip.batch import enhance_fixed_frames
from src.io.video import save_frame
from tools.verify_fixed_batch import main, snapshot_inputs, verify_outputs


@pytest.fixture
def batch(tmp_path):
    orig, fixed, log = tmp_path / "orig", tmp_path / "fixed", tmp_path / "params.json"
    save_frame(orig / "night.png", np.full((9, 13, 3), 30, np.uint8))
    baseline = snapshot_inputs(orig)
    enhance_fixed_frames(orig, fixed, log)
    return orig, fixed, log, baseline


def test_valid_real_batch_contract(batch):
    report = verify_outputs(*batch)
    assert report["frames_verified"] == 1 and report["originals_unchanged"]


@pytest.mark.parametrize("change", ["original", "extra", "missing", "shape", "params", "nan", "negative", "missing_log", "total"])
def test_reject_invalid_handoff(batch, change):
    orig, fixed, log, baseline = batch
    records = json.loads(log.read_text())
    if change == "original":
        save_frame(orig / "night.png", np.full((9, 13, 3), 50, np.uint8))
    elif change == "extra":
        save_frame(fixed / "stale.png", np.zeros((9, 13, 3), np.uint8))
    elif change == "missing":
        (fixed / "night.png").unlink()
    elif change == "shape":
        save_frame(fixed / "night.png", np.zeros((10, 13, 3), np.uint8))
    elif change == "params":
        records["night.png"]["params"]["gamma"] = 1.1
    elif change == "nan":
        records["night.png"]["enhance_ms"] = float("nan")
    elif change == "negative":
        records["night.png"]["total_ms"] = -1
    elif change == "total":
        records["night.png"]["total_ms"] = 0
    else:
        records = {}
    log.write_text(json.dumps(records))
    with pytest.raises(ValueError):
        verify_outputs(orig, fixed, log, baseline)


def test_cli_snapshot_and_verify(batch, tmp_path):
    orig, fixed, log, _ = batch
    snap = tmp_path / "snapshot.json"
    args = ["--orig", str(orig), "--fixed", str(fixed), "--params", str(log), "--snapshot", str(snap)]
    assert main(["snapshot", *args]) == 0
    assert main(["verify", *args]) == 0
    with pytest.raises(SystemExit):
        main(["snapshot", *args])
