from pathlib import Path
import numpy as np
import pytest
from src.io import extract_frames, extract_eval_set, get_meta, read_video, write_video, load_frame

def constant(value=80):
    return np.full((48, 64, 3), value, dtype=np.uint8)


@pytest.fixture
def video(tmp_path):
    path = tmp_path / 'data/clips/rain.mp4'
    write_video((constant(i*20) for i in range(10)), 10, path)
    return path


def test_video_roundtrip_and_timestamps(video, tmp_path):
    meta = get_meta(video)
    assert meta['frame_count'] == 10 and meta['fps'] == 10
    paths = extract_frames(video, [0, 201, 850], output_dir=tmp_path/'frames')
    decoded = list(read_video(video))
    for path, i in zip(paths, [0,2,9]):
        assert np.array_equal(load_frame(path), decoded[i])
    out = tmp_path/'copy.mp4'
    write_video(read_video(video), 10, out)
    assert get_meta(out) == meta
    with pytest.raises(ValueError):
        extract_frames(video,[1000], output_dir=tmp_path/'frames')
    with pytest.raises(ValueError):
        extract_frames(video,[0,0], output_dir=tmp_path/'frames')


def test_video_error_preserves_existing_output(tmp_path):
    path = tmp_path/'existing.mp4'
    path.write_bytes(b'existing')
    with pytest.raises(ValueError):
        write_video([constant(),constant()[:10]],10,path)
    assert path.read_bytes() == b'existing'
    with pytest.raises(ValueError):
        write_video([],10,tmp_path/'empty.mp4')
    assert not (tmp_path/'empty.mp4').exists()


def test_eval_set(video,tmp_path):
    path=tmp_path/'data/eval_set.csv'
    path.write_text('clip,timestamp_ms,condition\nrain.mp4,0,rain\nrain.mp4,200,rain\n')
    assert len(extract_eval_set(root=tmp_path)) == 2
    path.write_text('clip,timestamp_ms,condition\nrain.mp4,0,rain\nrain.mp4,0,rain\n')
    with pytest.raises(ValueError):
        extract_eval_set(root=tmp_path)


def test_default_paths_independent_of_working_directory(tmp_path, monkeypatch):
    from src.io.video import resolve, ROOT
    monkeypatch.chdir(tmp_path)
    assert resolve('data/frames/orig') == ROOT/'data/frames/orig'
