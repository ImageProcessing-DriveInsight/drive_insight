"""B's fixed video path uses the real A-08 callable and preserves source media."""

import numpy as np

from src.adaptive import enhance_video
from src.adaptive.pipeline import load_callable
from src.dip import fixed_enhance
from src.io import get_meta, read_video, write_video


def test_b_dynamic_import_resolves_fixed_enhance():
    assert load_callable("src.dip.fixed:fixed_enhance") is fixed_enhance


def test_fixed_video_pipeline_without_injected_enhancement(tmp_path):
    source = tmp_path / "orig.mp4"
    target = tmp_path / "fixed.mp4"
    images = [np.full((32, 48, 3), value, np.uint8) for value in (20, 70, 130)]
    write_video(iter(images), 10, source)
    original_bytes = source.read_bytes()
    decoded_original = list(read_video(source))
    progress = []
    result = enhance_video(source, "fixed", output_path=target,
                           progress=lambda current, total: progress.append((current, total)))
    assert result == target
    assert get_meta(target) == get_meta(source)
    assert progress == [(1, 3), (2, 3), (3, 3)]
    assert source.read_bytes() == original_bytes
    decoded_fixed = list(read_video(target))
    assert len(decoded_fixed) == len(decoded_original) == 3
    for before, after in zip(decoded_original, decoded_fixed):
        expected, _ = fixed_enhance(before)
        assert after.shape == before.shape and after.dtype == np.uint8
        # MP4 is lossy; the exact pixel chain is covered by the unit test.
        assert abs(float(after.mean()) - float(expected.mean())) < 8
        assert after.mean() > before.mean()
