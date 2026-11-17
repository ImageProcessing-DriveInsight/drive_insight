"""Merge member manifests; preserve source/license and reject ambiguous filenames."""
import argparse
import csv
from pathlib import Path
from src.io.video import ROOT

CONDITIONS = {'low_light', 'rain', 'fog', 'snow', 'backlight', 'tunnel', 'mixed'}


def merge_manifests(inputs, output):
    rows, seen, stems, metadata = [], set(), {}, {}
    required = ['clip', 'timestamp_ms', 'condition', 'source', 'license']
    for path in inputs:
        with Path(path).open(encoding='utf-8-sig', newline='') as f:
            reader = csv.DictReader(f)
            if not set(required) <= set(reader.fieldnames or []):
                raise ValueError(f'{path}: required columns {required}')
            for row in reader:
                if any(not isinstance(row.get(k), str) or not row[k].strip() for k in required):
                    raise ValueError('Missing manifest field')
                clip = row['clip'].strip()
                if '/' in clip or '\\' in clip or Path(clip).suffix.lower() not in ('.mp4', '.avi', '.mov', '.mkv'):
                    raise ValueError('clip must be a video basename with extension')
                ms = int(row['timestamp_ms'])
                if ms < 0 or row['condition'] not in CONDITIONS:
                    raise ValueError('Invalid timestamp or condition')
                if Path(clip).stem in stems and stems[Path(clip).stem] != clip:
                    raise ValueError('Different videos cannot have identical filename stems')
                stems[Path(clip).stem] = clip
                info = tuple(row[k] for k in ('condition', 'source', 'license'))
                if clip in metadata and metadata[clip] != info:
                    raise ValueError('Conflicting metadata for one clip')
                metadata[clip] = info
                key = (clip, ms)
                if key in seen:
                    raise ValueError(f'Duplicate frame: {key}')
                seen.add(key)
                rows.append({**{k: row[k] for k in required}, 'clip': clip, 'timestamp_ms': str(ms)})
    if not rows:
        raise ValueError('No evaluation timestamps provided')
    rows.sort(key=lambda r: (r['clip'], int(r['timestamp_ms'])))
    output = Path(output)
    if output.exists():
        raise FileExistsError(f'Archive existing manifest before replacing: {output}')
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open('w', encoding='utf-8-sig', newline='') as f:
        w = csv.DictWriter(f, fieldnames=required)
        w.writeheader()
        w.writerows(rows)
    return rows


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('inputs', nargs='+', type=Path)
    p.add_argument('--output', type=Path, default=ROOT / 'data/eval_set.csv')
    args = p.parse_args()
    print(f'{len(merge_manifests(args.inputs, args.output))} evaluation frames')

if __name__ == '__main__':
    main()
