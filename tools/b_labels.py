"""Scene annotations stay outside data/labels; export only C-compatible plate JSON."""
import argparse
import json
from pathlib import Path
from src.io.video import ROOT, load_frame


def create_templates(frames_dir, output):
    paths = sorted(Path(frames_dir).glob('*.png'))
    if not paths:
        raise FileNotFoundError('No original PNG frames')
    data = {}
    for path in paths:
        image = load_frame(path)
        h, w = image.shape[:2]
        data[path.name] = {'annotation_status': 'pending', 'width': w, 'height': h,
                           'vehicles': [], 'plates': [], 'events': [], 'visibility_notes': [],
                           'annotator': '', 'reviewer': None}
    output = Path(output)
    if output.exists():
        raise FileExistsError(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
    return output


def validate_annotations(data, *, require_review=False):
    if not isinstance(data, dict) or not data:
        raise ValueError('Expected a nonempty frame -> annotation dictionary')
    for frame, entry in data.items():
        if Path(frame).name != frame or not frame.endswith('.png'):
            raise ValueError('Frame must be a PNG basename')
        if entry.get('annotation_status') != 'complete':
            raise ValueError(f'{frame}: pending annotation cannot be used for evaluation')
        if not isinstance(entry.get('annotator'), str) or not entry['annotator'].strip():
            raise ValueError(f'{frame}: annotator required')
        if require_review and (not isinstance(entry.get('reviewer'), str) or not entry['reviewer'].strip()):
            raise ValueError(f'{frame}: reviewer required')
        w, h = entry.get('width'), entry.get('height')
        if type(w) is not int or type(h) is not int or min(w, h) <= 0:
            raise ValueError('Positive integer width/height required')
        for field in ('vehicles', 'plates', 'events', 'visibility_notes'):
            if not isinstance(entry.get(field), list):
                raise ValueError(f'{frame}: {field} must be a list')
        if any(not isinstance(s, str) for s in entry['events'] + entry['visibility_notes']):
            raise ValueError('Events/visibility notes must be strings')
        for obj in entry['vehicles'] + entry['plates']:
            box = obj.get('bbox')
            if not isinstance(box, list) or len(box) != 4 or any(type(v) is not int for v in box):
                raise ValueError('bbox must be four integers [x,y,w,h]')
            x, y, bw, bh = box
            if min(x, y) < 0 or min(bw, bh) <= 0 or x+bw > w or y+bh > h:
                raise ValueError('bbox outside frame')
        for obj in entry['vehicles']:
            if obj.get('class') not in ('car', 'truck', 'bus', 'motorcycle'):
                raise ValueError('Invalid vehicle class')
        for obj in entry['plates']:
            if obj.get('status') not in ('readable', 'unreadable') or 'text' not in obj:
                raise ValueError('Plate requires readable/unreadable status and text')
            text = obj['text']
            if obj['status'] == 'unreadable' and text is not None:
                raise ValueError('Unreadable plate text must be null')
            if obj['status'] == 'readable' and (not isinstance(text, str) or not text.strip() or '?' in text):
                raise ValueError('Readable plate requires fully observed text')
    return data


def export_plates(annotation_file, output, *, frames_dir=None, require_review=False):
    data = validate_annotations(json.loads(Path(annotation_file).read_text(encoding='utf-8')),
                                require_review=require_review)
    if frames_dir is not None:
        paths = {p.name: p for p in Path(frames_dir).glob('*.png')}
        if set(paths) != set(data):
            raise ValueError('Annotation/frame sets must match exactly')
        for name, entry in data.items():
            image = load_frame(paths[name])
            if image.shape[:2] != (entry['height'], entry['width']):
                raise ValueError('Annotation dimensions do not match PNG')
    result = {frame: [{'bbox': p['bbox'], 'text': p['text']} for p in entry['plates']]
              for frame, entry in data.items()}
    output = Path(output)
    if output.exists():
        raise FileExistsError(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    return output


def main():
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest='command', required=True)
    t = sub.add_parser('init')
    t.add_argument('--frames', type=Path, default=ROOT / 'data/frames/orig')
    t.add_argument('--out', type=Path, default=ROOT / 'data/annotations/scenes.json')
    e = sub.add_parser('export')
    e.add_argument('--annotations', type=Path, default=ROOT / 'data/annotations/scenes.json')
    e.add_argument('--out', type=Path, default=ROOT / 'data/labels/plates.json')
    e.add_argument('--frames', type=Path, default=ROOT / 'data/frames/orig')
    e.add_argument('--require-review', action='store_true')
    args = p.parse_args()
    if args.command == 'init':
        print(create_templates(args.frames, args.out))
    else:
        print(export_plates(args.annotations, args.out, frames_dir=args.frames, require_review=args.require_review))

if __name__ == '__main__':
    main()
