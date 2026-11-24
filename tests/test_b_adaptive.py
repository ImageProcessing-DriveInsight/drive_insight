from pathlib import Path
import numpy as np
import pytest
from src.io import save_frame, load_frame, write_video, get_meta
from src.adaptive import measure_quality, select_params, Thresholds, adaptive_enhance, enhance_frames, enhance_video

def constant(value=80):
    return np.full((48, 64, 3), value, dtype=np.uint8)

def synthetic_ops(frame, params):
    # Test double only. A owns the production implementation.
    return np.clip(255 * (frame.astype(float)/255)**params['gamma'], 0, 255).astype(np.uint8)

@pytest.fixture
def video(tmp_path):
    path = tmp_path / 'data/clips/rain.mp4'
    write_video((constant(i*20) for i in range(10)), 10, path)
    return path

def test_quality_constant_and_color():
    q = measure_quality(constant(80))
    assert q == pytest.approx({'brightness': 80, 'contrast': 0, 'noise': 0, 'sharpness': 0})
    blue = constant(0)
    blue[..., 0] = 255
    assert measure_quality(blue)['brightness'] == pytest.approx(255*.114)

def test_quality_noise_and_sharpness_direction():
    rng = np.random.default_rng(42)
    y = rng.normal(128, 10, (256, 256)).clip(0,255).astype('uint8')
    noisy = np.repeat(y[..., None], 3, axis=2)
    q = measure_quality(noisy)
    assert 8 < q['noise'] < 12
    assert q['sharpness'] > measure_quality(constant(128))['sharpness']
    edge = np.full((100, 100, 3), 30, dtype='uint8')
    edge[:, 50:] = 220
    smooth = edge.copy()
    smooth[:, 40:60] = np.linspace(30, 220, 20).astype('uint8')[None, :, None]
    assert measure_quality(edge)['sharpness'] > measure_quality(smooth)['sharpness']

@pytest.mark.parametrize('frame',[np.zeros((4,4)), np.zeros((4,4,3)), np.zeros((0,4,3),dtype='uint8')])
def test_quality_invalid(frame):
    with pytest.raises(ValueError):
        measure_quality(frame)

@pytest.mark.parametrize('brightness,gamma', [(59.99,.5),(60,.75),(99.99,.75),(100,1),(190,1),(190.01,1.3)])
def test_brightness_boundaries(brightness, gamma):
    q = dict(brightness=brightness, contrast=50, noise=0, sharpness=200)
    assert select_params(q)['gamma'] == gamma

@pytest.mark.parametrize('noise,denoise,ksize', [(7.99,'none',3),(8,'gaussian',3),(17.99,'gaussian',3),(18,'median',5)])
def test_noise_boundaries(noise, denoise, ksize):
    p = select_params(dict(brightness=120, contrast=20, noise=noise, sharpness=50))
    assert (p['denoise'],p['ksize']) == (denoise,ksize)
    assert p['hist_eq'] == (noise < 8)
    assert (p['unsharp'] > 0) == (noise < 8)

def test_rules_validation_and_repeatability():
    q = dict(brightness=70, contrast=30, noise=1, sharpness=50)
    assert select_params(q) == select_params(q)
    assert select_params(q, thresholds=Thresholds().scaled(1.2))['gamma'] == .5
    with pytest.raises(ValueError):
        select_params({**q, 'noise': float('nan')})
    with pytest.raises(ValueError):
        Thresholds().scaled(-1)

def test_pipeline_contract_and_no_mutation():
    frame = constant(30)
    out,p,q = adaptive_enhance(frame,apply_ops=synthetic_ops)
    assert out.mean() > frame.mean()
    assert frame.mean() == 30
    assert p['rules'] and q['brightness'] == pytest.approx(30)
    with pytest.raises(ValueError):
        adaptive_enhance(frame, apply_ops=lambda f,p: f[:10])

def test_missing_a_is_not_silently_faked(monkeypatch):
    import src.adaptive.pipeline as pipeline
    def missing(spec):
        raise ModuleNotFoundError(spec)
    monkeypatch.setattr(pipeline, 'load_callable', missing)
    with pytest.raises(ModuleNotFoundError):
        adaptive_enhance(constant())

def test_video_enhance(video, tmp_path):
    progress=[]
    for mode in ['fixed','adaptive']:
        output=tmp_path/f'{mode}.mp4'
        enhance_video(video, mode, output_path=output, apply_ops=synthetic_ops,
                      fixed_enhance=lambda f:(f.copy(),{}), progress=lambda n,t:progress.append((n,t)))
        assert get_meta(output) == get_meta(video)
    assert progress[-1] == (10,10)
    with pytest.raises(ValueError):
        enhance_video(video,'adaptive',output_path=video)

def test_batch(tmp_path):
    src,dst=tmp_path/'orig',tmp_path/'adaptive'
    save_frame(src/'rain_0.png',constant(30))
    save_frame(src/'rain_200.png',constant(130))
    records=enhance_frames(src,dst,tmp_path/'params.json',apply_ops=synthetic_ops)
    assert sorted(records) == sorted(p.name for p in dst.glob('*.png'))
    assert records['rain_0.png']['quality']['brightness'] == pytest.approx(30)
    assert records['rain_0.png']['enhance_ms'] >= 0
    save_frame(dst/'stale.png',constant())
    with pytest.raises(ValueError):
        enhance_frames(src,dst,tmp_path/'params.json',apply_ops=synthetic_ops)

def test_contrast_and_sharpness_boundaries():
    q=dict(brightness=120,contrast=35,noise=0,sharpness=100)
    assert select_params(q)['rules']==[]
    assert select_params({**q,'contrast':34.9})['rules']==['CT_LOW']
    assert select_params({**q,'sharpness':99.9})['rules']==['SH_LOW']

def test_rule_document_matches_code():
    import re

    root = Path(__file__).resolve().parents[1]
    doc = (root / 'docs/rules.md').read_text(encoding='utf-8')
    code = (root / 'src/adaptive/rules.py').read_text(encoding='utf-8')

    expected = set(re.findall(r"append\('([A-Z_]+)'\)", code))
    documented = set(re.findall(r'\| ([A-Z]+_[A-Z]+) \|', doc))

    assert documented == expected
