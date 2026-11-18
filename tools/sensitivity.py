"""B-09: regenerate frames, run C's real CSV pipeline, score each scale."""
import argparse
import csv
import json
import math
from pathlib import Path
from src.io.video import ROOT
from src.adaptive import Thresholds, enhance_frames
from src.adaptive.pipeline import load_callable
from src.eval.ocr import eval_ocr, load_labels
from src.plate.run import run_ocr


def run_sensitivity(*, root=ROOT, scales=(0.8, 1.2), labels=None,
                    apply_ops=None, ocr_runner=None, evaluator=None):
    root = Path(root).resolve()
    source = root / 'data/frames/orig'
    frames = sorted(source.glob('*.png'))
    if not frames:
        raise FileNotFoundError(f'No original frames: {source}')
    if labels is None:
        labels = root / 'data/labels'
    elif isinstance(labels, (str, Path)):
        labels = Path(labels)
        if not labels.is_absolute():
            labels = root / labels
    gold = load_labels(labels)
    if set(gold) != {p.stem for p in frames}:
        raise ValueError('Label/frame sets must match exactly, including zero-plate frames')
    scales = list(dict.fromkeys([1.0, *scales]))
    if any(not math.isfinite(s) or s <= 0 for s in scales):
        raise ValueError('Scales must be finite and positive')
    operation = apply_ops or load_callable('src.dip.fixed:apply_ops')
    runner, evaluate = ocr_runner or run_ocr, evaluator or eval_ocr
    base = root / 'results/sensitivity'
    if base.exists():
        raise FileExistsError('Archive/remove results/sensitivity before a new experiment')
    results = []
    for scale in scales:
        # repr avoids colliding directories for distinct close float values.
        run = base / f'scale_{scale}'
        run.mkdir(parents=True)
        enhance_frames(source, run / 'frames', run / 'params.json', apply_ops=operation,
                       thresholds=Thresholds().scaled(scale))
        csv_path = runner('adaptive', frames_dir=run / 'frames', results_dir=run / 'results')
        with Path(csv_path).open(encoding='utf-8-sig', newline='') as f:
            rows = list(csv.DictReader(f))
        if {Path(r['frame']).stem for r in rows} != set(gold):
            raise ValueError('OCR CSV must cover every evaluation frame')
        metrics = evaluate(csv_path, gold)
        if not isinstance(metrics, dict) or not metrics:
            raise ValueError('Evaluator must return a nonempty metrics dictionary')
        for key, value in metrics.items():
            if value is not None and (isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value)):
                raise ValueError(f'Non-numeric metric: {key}')
        (run / 'metrics.json').write_text(json.dumps(metrics, ensure_ascii=False, indent=2, allow_nan=False), encoding='utf-8')
        results.append((scale, metrics))
    baseline = results[0][1]
    if any(metrics.keys() != baseline.keys() for _, metrics in results):
        raise ValueError('Metric schema changed across scales')
    rows = []
    for scale, metrics in results:
        for key, value in metrics.items():
            ref = baseline[key]
            rows.append({'scale': scale, 'metric': key, 'value': value,
                         'delta_vs_1': value-ref if value is not None and ref is not None else None})
    with (base / 'summary.csv').open('w', encoding='utf-8-sig', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=['scale', 'metric', 'value', 'delta_vs_1'])
        writer.writeheader()
        writer.writerows(rows)
    return rows


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root', type=Path, default=ROOT)
    p.add_argument('--scale', type=float, nargs='+', default=[0.8, 1.2])
    p.add_argument('--apply-ops', default='src.dip.fixed:apply_ops')
    p.add_argument('--labels', type=Path, default=Path('data/labels'))
    args = p.parse_args()
    run_sensitivity(root=args.root, scales=args.scale, apply_ops=load_callable(args.apply_ops), labels=args.labels)
    print(args.root / 'results/sensitivity/summary.csv')

if __name__ == '__main__':
    main()
