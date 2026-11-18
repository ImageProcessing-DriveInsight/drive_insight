import csv
import json
import math

import numpy as np
import pytest

from src.dip.ops import hist_eq
from src.io.video import get_meta, load_frame, read_video, write_video
from tools.synth_fog import (HORIZON_COLOR, Fog, add_fog, distance, make, preview, reference, settings_path,
                             shrink, transmission, transmission_map)

H, W = 48, 64
CODECS = ("mp4v",)  # written the same way on every machine
NO_VEHICLES = lambda frame: []  # noqa: E731  keeps YOLO out of the tests


def gray_texture(seed=0):
    values = np.random.default_rng(seed).integers(40, 216, (H, W), dtype=np.uint8)
    return np.repeat(values[..., None], 3, axis=2)


def clip(path, values, fps=10):
    write_video((np.full((H, W, 3), v, np.uint8) for v in values), fps, path)
    return path


@pytest.fixture
def clear_clip(tmp_path):
    return clip(tmp_path / "clear" / "day_01.mp4", [10 * i for i in range(10)])


def test_distance_and_transmission():
    fog = Fog(visibility=150, horizon=0.5, near=4, far=300)
    d = distance(H, fog)
    assert d[-1] == pytest.approx(4) and (d[:24] == 300).all()
    assert (np.diff(d) <= 0).all()  # nearer toward the bottom
    t = transmission(H, fog)
    assert t[-1] == pytest.approx(math.exp(-fog.beta * 4))
    assert math.exp(-fog.beta * fog.visibility) == pytest.approx(0.02)  # Koschmieder


def mask(y0, y1, x0, x1):
    m = np.zeros((H, W), bool)
    m[y0:y1, x0:x1] = True
    return m


def test_vehicle_mask_takes_the_distance_of_its_bottom():
    fog = Fog()
    road = transmission(H, fog)
    t = transmission_map((H, W), fog, [mask(5, 35, 10, 40)])  # bottom row 34
    assert (t[5:35, 10:40] == road[34]).all()  # also above the horizon
    assert t[20, 5] == road[20] and t[40, 25] == road[40]  # beside and below the vehicle
    nearer_inside = mask(20, 45, 20, 30)  # bottom row 44, overlapping the first
    t = transmission_map((H, W), fog, [mask(5, 35, 10, 40), nearer_inside])
    assert t[25, 25] == road[44] and t[10, 15] == road[34]
    assert np.array_equal(transmission_map((H, W), fog, [np.zeros((H, W), bool)]),
                          np.repeat(road[:, None], W, axis=1))


def test_fog_follows_the_model_without_blur_and_noise():
    frame = gray_texture()
    before = frame.copy()
    fog = Fog(blur=0, noise=0, airlight=0.8)
    out = add_fog(frame, fog, np.random.default_rng())
    t = transmission(H, fog)[:, None, None]
    expected = np.rint(frame * t + 204 * (1 - t))
    assert np.abs(out - expected).max() <= 1 and (out[0] == 204).all()  # top row is all fog
    assert np.array_equal(frame, before)


def test_fog_thickens_with_distance_so_hist_eq_cannot_undo_it():
    frame = gray_texture()
    out = add_fog(frame, Fog(blur=0, noise=0), np.random.default_rng())
    assert out[24:26].std() < 0.5 * out[-4:].std()  # just below the horizon vs the bottom rows
    uniform = np.rint(frame * 0.5 + 204 * 0.5).astype(np.uint8)
    restored = np.abs(hist_eq(uniform).astype(int) - hist_eq(frame)).mean()
    assert restored < 2  # a uniform fog is undone almost exactly
    assert np.abs(hist_eq(out).astype(int) - hist_eq(frame)).mean() > 10 * restored


def test_noise_follows_the_seed():
    frame = gray_texture()

    def run(seed, noise=2.0):
        return add_fog(frame, Fog(noise=noise, seed=seed), np.random.default_rng(seed))

    assert np.array_equal(run(1), run(1)) and not np.array_equal(run(1), run(2))
    assert np.array_equal(run(1, noise=0), run(2, noise=0))


def test_shrink_mask():
    m = mask(5, 35, 10, 40)
    assert np.array_equal(shrink(m, 2), mask(7, 33, 12, 38)) and np.array_equal(shrink(m, 0), m)


def test_masks_ignored_without_vehicles():
    frame, masks = gray_texture(), [mask(5, 35, 10, 40)]
    with_mask = add_fog(frame, Fog(noise=0), np.random.default_rng(), masks)
    assert not np.array_equal(with_mask, add_fog(frame, Fog(noise=0), np.random.default_rng()))
    assert np.array_equal(add_fog(frame, Fog(noise=0, vehicles=False), np.random.default_rng(), masks),
                          add_fog(frame, Fog(noise=0), np.random.default_rng()))


@pytest.mark.parametrize("bad", [dict(horizon=1), dict(near=400), dict(airlight=1.5), dict(visibility=0),
                                 dict(noise=-1), dict(blur=float("nan")), dict(seed=1.5), dict(vehicles=1)])
def test_fog_settings_are_checked(bad):
    with pytest.raises(ValueError):
        Fog(**bad)


def test_make_writes_clip_and_settings(clear_clip, tmp_path):
    out = tmp_path / "data" / "clips" / "fog_01.mp4"
    seen = []

    def detector(frame):  # gets every clear frame that is fogged
        seen.append(int(frame.mean()))
        return []

    record = make(clear_clip, out, Fog(seed=3), start_ms=200, end_ms=800, codecs=CODECS, detector=detector)
    meta = get_meta(out)
    assert meta["frame_count"] == 6 and meta["fps"] == 10  # frames 2..7 of the source
    assert len(seen) == 6 and seen[0] == pytest.approx(20, abs=3)
    assert json.loads(settings_path(out).read_text(encoding="utf-8")) == record
    assert (record["first_frame"], record["frames"], record["codec"]) == (2, 6, "mp4v")
    assert record["settings"]["seed"] == 3 and len(record["source_sha256"]) == 64
    assert next(read_video(out))[0].mean() > 150  # source frame is 20 everywhere, the top row is fog
    with pytest.raises(FileExistsError):
        make(clear_clip, out, Fog(), codecs=CODECS, detector=NO_VEHICLES)
    with pytest.raises(ValueError):
        make(clear_clip, tmp_path / "late.mp4", Fog(), start_ms=5000, codecs=CODECS, detector=NO_VEHICLES)
    with pytest.raises(ValueError):
        make(clear_clip, tmp_path / "frame.png", Fog(), codecs=CODECS, detector=NO_VEHICLES)


def test_reference_saves_clear_frames_with_foggy_names(clear_clip, tmp_path):
    out = tmp_path / "data" / "clips" / "fog_01.mp4"
    make(clear_clip, out, Fog(), start_ms=200, end_ms=800, codecs=CODECS, detector=NO_VEHICLES)
    clear = tmp_path / "frames" / "clear"
    paths = reference(out, [0, 300], out_dir=clear)
    assert [p.name for p in paths] == ["fog_01_0.png", "fog_01_300.png"]
    decoded = list(read_video(clear_clip))
    assert np.array_equal(load_frame(paths[0]), decoded[2]) and np.array_equal(load_frame(paths[1]), decoded[5])

    eval_set = tmp_path / "eval_set.csv"
    with eval_set.open("w", encoding="utf-8", newline="") as f:
        csv.writer(f).writerows([["clip", "timestamp_ms", "condition"], ["fog_01.mp4", 100, "fog"],
                                 ["rain_01.mp4", 200, "rain"]])
    assert [p.name for p in reference(out, eval_set=eval_set, out_dir=clear)] == ["fog_01_100.png"]

    with pytest.raises(ValueError, match="outside"):
        reference(out, [700], out_dir=clear)  # the foggy clip has 6 frames
    other = clip(tmp_path / "other.mp4", [50] * 10)
    with pytest.raises(ValueError, match="made from"):
        reference(out, [0], out_dir=clear, source=other)


def test_preview_marks_the_horizon(clear_clip, tmp_path):
    path = preview(clear_clip, 300, Fog(), out=tmp_path / "preview.png", detector=NO_VEHICLES)
    image = load_frame(path)
    assert image.shape == (H, 2 * W, 3)
    assert tuple(image[24, 5]) == HORIZON_COLOR and tuple(image[24, W + 5]) == HORIZON_COLOR
