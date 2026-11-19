import csv
import json

import numpy as np
import pytest

from src.io.video import write_video
from tools.pick_frames import add_rows, choose, near_width, pick, scan, scan_path
from tools.synth_fog import frame_index

H, W = 48, 64


def record(widths, fps=10.0, width=1920, step_ms=1000, count=None):
    """Scan record with one vehicle of the given width per sampled frame (0 = none), placed
    differently in each frame so that no two frames show the same view."""
    frames = []
    for k, w in enumerate(widths):
        ms = k * step_ms
        x, y = 4 + (k * 160) % 1200 * width // 1920, 10 + (k * 50) % 400
        vehicles = [{"bbox": [x, y, w, w // 2], "cls": "car", "conf": 0.9}] if w else []
        frames.append({"index": frame_index(ms, fps), "ms": ms, "vehicles": vehicles})
    return {"source": "data/clear/day.mp4", "fps": fps, "width": width, "height": width * 9 // 16,
            "frame_count": count or frame_index(len(widths) * step_ms, fps), "step_ms": step_ms, "frames": frames}


def test_near_width_skips_side_edges_and_side_views():
    vehicles = [{"bbox": [0, 0, 900, 400]}, {"bbox": [1100, 0, 820, 400]}, {"bbox": [500, 300, 300, 200]},
                {"bbox": [600, 300, 700, 200]}]
    # the first starts at the left edge, the second ends at the right, the last is 3.5:1 (side view)
    assert near_width(vehicles, 1920) == 300
    assert near_width([], 1920) == 0


def test_choose_keeps_widest_frames_apart():
    frames = [{"index": i, "width": w, "box": [100 * i, 0, w, w]} for i, w in [(0, 300), (5, 500), (9, 400), (20, 350)]]
    assert [f["index"] for f in choose(frames, gap_frames=10, max_frames=5)] == [5, 20]
    assert [f["index"] for f in choose(frames, gap_frames=4, max_frames=2)] == [5, 9]


def test_choose_skips_the_same_view():
    # a car standing still in a jam: the same box seconds later is the same plate again
    frames = [{"index": 0, "width": 500, "box": [700, 500, 500, 400]},
              {"index": 30, "width": 490, "box": [705, 502, 490, 395]},
              {"index": 60, "width": 300, "box": [300, 520, 300, 250]}]
    assert [f["index"] for f in choose(frames, gap_frames=10, max_frames=5)] == [0, 60]


def test_pick_finds_the_window_with_most_near_vehicles():
    # 1 s samples; near vehicles (>= 280 px at 1920) only at 6-9 s
    widths = [0, 100, 0, 300, 0, 0, 400, 290, 500, 350, 0, 0]
    window = pick(record(widths), length_ms=4000, gap_ms=1000, max_frames=5)
    assert (window["start_ms"], window["end_ms"]) == (6000, 10000)
    assert [f["ms"] for f in window["frames"]] == [6000, 7000, 8000, 9000]
    assert [f["clip_ms"] for f in window["frames"]] == [0, 1000, 2000, 3000]


def test_pick_ties_go_to_the_wider_vehicles_then_the_earlier_window():
    widths = [300, 0, 0, 0, 600, 0, 300, 0]
    assert pick(record(widths), length_ms=2000, gap_ms=0)["start_ms"] == 3000  # 600 px beats 300 px
    assert pick(record([300, 0, 300, 0]), length_ms=2000, gap_ms=0)["start_ms"] == 0


def test_pick_scales_the_width_and_returns_none_without_near_vehicles():
    small = record([150, 150, 0, 0], width=960)  # 150 px at 960 wide is 300 px at 1920
    assert pick(small, length_ms=2000, gap_ms=0)["start_ms"] == 0
    assert pick(record([100, 200, 0, 0]), length_ms=2000) is None
    assert pick(record([300] * 3), length_ms=5000) is None  # no window fits in the clip


def test_clip_time_lands_on_the_scanned_frame():
    # 30.3 fps, 500 ms steps, wider vehicles later: the last window that fits wins, and it
    # starts on a frame that is not a whole number of ms
    rec = record([300 + k for k in range(40)], fps=30.3, step_ms=500)
    window = pick(rec, length_ms=6000, gap_ms=1000, max_frames=5)
    first = window["first_frame"]
    assert (window["start_ms"], first) == (14000, 424) and len(window["frames"]) == 5
    for f in window["frames"]:
        assert first + frame_index(f["clip_ms"], 30.3) == f["index"]


def test_add_rows_writes_the_manifest_and_refuses_a_listed_clip(tmp_path):
    rec = record([0, 300, 0, 400, 0, 0])
    window = pick(rec, length_ms=3000, gap_ms=1000)
    manifest = tmp_path / "member_c.csv"
    add_rows(manifest, "fog_01.mp4", window, rec, "medium")
    add_rows(manifest, "fog_02.mp4", window, rec, "heavy")
    with manifest.open(encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    assert [(r["clip"], r["timestamp_ms"]) for r in rows] == [
        ("fog_01.mp4", "0"), ("fog_01.mp4", "2000"), ("fog_02.mp4", "0"), ("fog_02.mp4", "2000")]
    assert rows[0]["condition"] == "fog" and rows[0]["license"] == "own footage"
    assert rows[0]["source"] == "own dashcam day.mp4 1000-4000 ms, synthetic fog (tools/synth_fog.py, medium)"
    with pytest.raises(ValueError, match="already"):
        add_rows(manifest, "fog_01.mp4", window, rec, "medium")


def test_scan_samples_every_step_and_saves_boxes(tmp_path):
    source = tmp_path / "day.mp4"
    write_video((np.full((H, W, 3), 10 * i, np.uint8) for i in range(25)), 10, source)
    seen = []

    def detector(frame):
        seen.append(int(frame[0, 0, 0]))
        return [{"bbox": (1, 2, 30, 20), "cls": "car", "conf": 0.8}]

    rec = scan(source, step_ms=500, detector=detector)
    assert [f["index"] for f in rec["frames"]] == [0, 5, 10, 15, 20]
    assert [f["ms"] for f in rec["frames"]] == [0, 500, 1000, 1500, 2000]
    assert len(seen) == 5 and seen[1] > seen[0]  # only the sampled frames were detected
    saved = json.loads(scan_path(source).read_text(encoding="utf-8"))
    assert saved["frames"][0]["vehicles"] == [{"bbox": [1, 2, 30, 20], "cls": "car", "conf": 0.8}]
    assert saved["frame_count"] == 25 and saved["width"] == W and len(saved["source_sha256"]) == 64


def test_scan_counts_the_frames_that_decode(tmp_path, monkeypatch):
    # dashcam files can list more frames than they hold; windows must stay within the decoded ones
    import tools.pick_frames as pf

    source = tmp_path / "day.mp4"
    write_video((np.full((H, W, 3), 100, np.uint8) for _ in range(20)), 10, source)
    listed = pf.get_meta(source)
    monkeypatch.setattr(pf, "get_meta", lambda path: {**listed, "frame_count": 22})
    rec = scan(source, step_ms=500, detector=lambda frame: [])
    assert [f["index"] for f in rec["frames"]] == [0, 5, 10, 15]  # no sample at frame 20
    assert (rec["frame_count"], rec["listed_frame_count"]) == (20, 22)
