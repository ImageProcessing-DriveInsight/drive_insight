"""Read-only readiness report; missing inputs are not counted as completed work."""
import argparse
import ast
import csv
import json
from pathlib import Path
from src.io.video import ROOT


def status(root=ROOT):
    root = Path(root).resolve()
    def function_exists(relative, name):
        path = root / relative
        if not path.is_file():
            return False
        return any(isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name == name
                   for n in ast.parse(path.read_text(encoding='utf-8')).body)
    report = {'root': str(root), 'dependencies': {
        'A_apply_ops_default_path': function_exists('src/dip/fixed.py', 'apply_ops'),
        'A_fixed_enhance_default_path': function_exists('src/dip/fixed.py', 'fixed_enhance'),
        'C_run_ocr': function_exists('src/plate/run.py', 'run_ocr'),
        'C_eval_ocr': function_exists('src/eval/ocr.py', 'eval_ocr')},
        'frame_counts': {}, 'warnings': []}
    sets = {}
    for condition in ('orig', 'fixed', 'adaptive'):
        sets[condition] = {p.name for p in (root / 'data/frames' / condition).glob('*.png')}
        report['frame_counts'][condition] = len(sets[condition])
    report['all_frame_sets_match'] = bool(sets['orig']) and sets['orig'] == sets['fixed'] == sets['adaptive']
    manifest = root / 'data/eval_set.csv'
    report['eval_set_exists'] = manifest.is_file()
    if manifest.is_file():
        with manifest.open(encoding='utf-8-sig', newline='') as f:
            rows = list(csv.DictReader(f))
        try:
            expected = {f'{Path(r["clip"]).stem}_{int(r["timestamp_ms"])}.png' for r in rows}
            report['eval_rows'] = len(rows)
            report['eval_matches_originals'] = bool(rows) and len(expected) == len(rows) and expected == sets['orig']
        except (KeyError, ValueError):
            report['warnings'].append('Invalid eval_set.csv')
    report['plate_label_files'] = len(list((root / 'data/labels').glob('*.json')))
    report['vlm_cache_files'] = len(list((root / 'results/vlm').glob('*/*.json')))
    report['note'] = 'Function presence is not runtime validation. A may use a different import path.'
    return report

if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root', type=Path, default=ROOT)
    print(json.dumps(status(p.parse_args().root), ensure_ascii=False, indent=2))
