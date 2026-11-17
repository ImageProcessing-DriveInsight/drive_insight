from pathlib import Path
import importlib
import json
import time
from src.io.video import ROOT, resolve, load_frame, save_frame, validate_frame, read_video, write_video, get_meta
from .quality import measure_quality
from .rules import select_params


def load_callable(spec):
    """Resolve an explicit module:function contract; never silently use a mock."""
    module, name = spec.split(':', 1)
    fn = getattr(importlib.import_module(module), name)
    if not callable(fn):
        raise TypeError(f'Not callable: {spec}')
    return fn


def adaptive_enhance(frame, *, apply_ops=None, thresholds=None):
    quality = measure_quality(frame)
    params = select_params(quality, thresholds=thresholds)
    operation = apply_ops or load_callable('src.dip.fixed:apply_ops')
    out = operation(frame.copy(), params)
    validate_frame(out)
    if out.shape != frame.shape:
        raise ValueError('apply_ops changed frame dimensions')
    return out, params, quality


def enhance_frames(input_dir='data/frames/orig', output_dir='data/frames/adaptive',
                   params_path='results/params/adaptive.json', *, apply_ops=None, thresholds=None):
    source, output = resolve(input_dir), resolve(output_dir)
    if source.resolve() == output.resolve():
        raise ValueError('Original frames must not be overwritten')
    files = sorted(source.glob('*.png'))
    if not files:
        raise ValueError(f'No PNG frames: {source}')
    extras = {p.name for p in output.glob('*.png')} - {p.name for p in files}
    if extras:
        raise ValueError(f'Stale output frames; use a clean output folder: {sorted(extras)}')
    records = {}
    for path in files:
        start = time.perf_counter()
        out, params, quality = adaptive_enhance(load_frame(path), apply_ops=apply_ops, thresholds=thresholds)
        save_frame(output / path.name, out)
        records[path.name] = {'quality': quality, 'params': params, 'rules': params['rules'],
                              'enhance_ms': (time.perf_counter()-start)*1000}
    target = resolve(params_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(records, ensure_ascii=False, indent=2, allow_nan=False), encoding='utf-8')
    return records


def enhance_video(clip, mode, *, output_path=None, apply_ops=None, fixed_enhance=None,
                  thresholds=None, progress=None):
    if mode not in ('fixed', 'adaptive'):
        raise ValueError('mode must be fixed or adaptive')
    clip = resolve(clip)
    target = resolve(output_path or ROOT / 'results/videos' / mode / (clip.stem + '.mp4'))
    if target.resolve() == clip.resolve():
        raise ValueError('Original video must not be overwritten')
    meta = get_meta(clip)
    if mode == 'fixed':
        fixed_enhance = fixed_enhance or load_callable('src.dip.fixed:fixed_enhance')
    else:
        apply_ops = apply_ops or load_callable('src.dip.fixed:apply_ops')
    def frames():
        stream = read_video(clip)
        count = 0
        try:
            for count, frame in enumerate(stream, 1):
                out = (fixed_enhance(frame)[0] if mode == 'fixed' else
                       adaptive_enhance(frame, apply_ops=apply_ops, thresholds=thresholds)[0])
                validate_frame(out)
                if out.shape != frame.shape:
                    raise ValueError('Enhancement changed frame dimensions')
                yield out
                if progress:
                    progress(count, meta['frame_count'])
                elif count == 1 or count % 30 == 0 or count == meta['frame_count']:
                    print(f'{mode}: {count}/{meta["frame_count"]}')
            if count != meta['frame_count']:
                raise OSError('Decoded frame count differs from metadata')
        finally:
            stream.close()
    return write_video(frames(), meta['fps'], target)
