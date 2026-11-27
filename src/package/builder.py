"""Portable review package. Missing upstream artifacts are explicit, never fatal."""
from pathlib import Path
import csv
import hashlib
import html
import json
import re
import shutil
import tempfile
from urllib.parse import quote
from src.io.video import ROOT

CONDITIONS = ('orig', 'fixed', 'adaptive')


def build_package(clip_id, *, root=ROOT):
    if not re.fullmatch(r'[\w-]+', clip_id):
        raise ValueError('clip_id must contain only letters, digits, underscore or hyphen')
    root = Path(root).resolve()
    base = root / 'package'
    base.mkdir(parents=True, exist_ok=True)
    destination = base / clip_id
    if destination.exists():
        raise FileExistsError(f'Package already exists; archive/remove it explicitly: {destination}')
    temporary = Path(tempfile.mkdtemp(prefix=f'.{clip_id}-', dir=base))
    manifest = {'clip_id': clip_id, 'files': [], 'missing': [], 'warnings': [], 'ocr_status': {}}
    def copy(path, relative):
        path = path.resolve()
        if not path.is_relative_to(root):
            manifest['warnings'].append(f'외부 경로 제외: {relative}')
            return None
        if not path.is_file():
            manifest['missing'].append(str(relative))
            return None
        target = temporary / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, target)
        def digest(p):
            h = hashlib.sha256()
            with p.open('rb') as f:
                for chunk in iter(lambda: f.read(1024*1024), b''):
                    h.update(chunk)
            return h.hexdigest()
        sha = digest(path)
        if digest(target) != sha:
            raise OSError(f'Copy hash mismatch: {path}')
        manifest['files'].append({'path': str(relative), 'sha256': sha})
        return str(relative)
    def json_read(path):
        if not path.is_file():
            return None
        try:
            return json.loads(path.read_text(encoding='utf-8'))
        except (ValueError, OSError) as exc:
            manifest['warnings'].append(f'{path.relative_to(root)}: {exc}')
            return None
    def belongs(name):
        return re.fullmatch(re.escape(clip_id) + r'_\d+\.png', Path(name).name) is not None
    try:
        originals = [p for p in (root / 'data/clips').glob('*')
                     if p.stem == clip_id and p.suffix.lower() in ('.mp4', '.avi', '.mov', '.mkv')]
        if len(originals) > 1:
            raise ValueError('Ambiguous original clip: duplicate stems')
        if originals:
            copy(originals[0], Path('videos') / originals[0].name)
        else:
            manifest['missing'].append('원본 영상')
        params, vlm, plates = {}, {}, []
        for condition in CONDITIONS:
            if condition != 'orig':
                copy(root / 'results/videos' / condition / f'{clip_id}.mp4', Path('videos') / f'{condition}.mp4')
            frames = [p for p in (root / 'data/frames' / condition).glob('*.png') if belongs(p.name)]
            if not frames:
                manifest['missing'].append(f'{condition} 키프레임')
            for frame in frames:
                copy(frame, Path('frames') / condition / frame.name)
            raw = json_read(root / 'results/params' / f'{condition}.json')
            # Contract: per-frame mapping, or {"global": {...}} for fixed settings.
            selected = ({k: v for k, v in raw.items() if belongs(k) or k == 'global'}
                        if isinstance(raw, dict) else {})
            params[condition] = selected or {'status': '없음'}
            if not selected:
                manifest['missing'].append(f'{condition} params')
            vlm[condition] = json_read(root / 'results/vlm' / condition / f'{clip_id}.json')
            if vlm[condition] is None:
                vlm[condition] = {'status': '없음'}
                manifest['missing'].append(f'{condition} VLM')
            csv_path = root / 'results/ocr' / f'{condition}.csv'
            matched = 0
            processed_frames = set()
            zero_frames = set()
            if csv_path.is_file():
                with csv_path.open(encoding='utf-8-sig', newline='') as f:
                    reader = csv.DictReader(f)
                    if 'frame' not in (reader.fieldnames or []):
                        manifest['warnings'].append(f'{condition} OCR: frame 컬럼 없음')
                    else:
                        for row in reader:
                            if not belongs(row['frame']):
                                continue
                            processed_frames.add(Path(row['frame']).name)
                            if not row.get('status'):
                                zero_frames.add(Path(row['frame']).name)
                                continue
                            matched += 1
                            try:
                                bbox = [int(row[k]) for k in ('x', 'y', 'w', 'h')]
                            except (KeyError, TypeError, ValueError):
                                manifest['warnings'].append(f'{condition} {row["frame"]}: 잘못된 좌표')
                                bbox = None
                            crop = row.get('crop_path', '')
                            copied = None
                            if crop:
                                copied = copy(root / crop, Path('crops') / condition / f'{matched}_{Path(crop).name}')
                            plates.append({'condition': condition, 'frame': row['frame'],
                                           'bbox': json.dumps(bbox) if bbox is not None else '없음', 'text': row.get('text', ''),
                                           'conf': row.get('conf', ''), 'status': row.get('status', ''),
                                           'crop_path': copied or '없음'})
            manifest['ocr_status'][condition] = {
                'file_exists': csv_path.is_file(), 'processed_frames': sorted(processed_frames),
                'zero_detection_frames': sorted(zero_frames), 'plate_count': matched}
            if not processed_frames:
                manifest['missing'].append(f'{condition} OCR 결과 없음')
            expected = {p.name for p in frames}
            missing_frames = sorted(expected - processed_frames)
            if missing_frames:
                manifest['missing'].append(f'{condition} OCR 미처리 프레임: {", ".join(missing_frames)}')
        for name, data in [('params.json', params), ('vlm_summary.json', vlm), ('manifest.json', manifest)]:
            (temporary / name).write_text(json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False), encoding='utf-8')
        with (temporary / 'plates.csv').open('w', encoding='utf-8-sig', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=['condition', 'frame', 'bbox', 'text', 'conf', 'status', 'crop_path'])
            writer.writeheader()
            writer.writerows(plates)
        esc = html.escape
        links = ''.join(f'<li><a href="{quote(x["path"])}">{esc(x["path"])}</a></li>' for x in manifest['files'])
        images = ''.join(f'<figure><img loading="lazy" src="{quote(x["path"])}"><figcaption>{esc(x["path"])}</figcaption></figure>'
                         for x in manifest['files'] if x['path'].startswith('frames/'))
        rows = ''.join('<tr>' + ''.join(f'<td>{esc(str(row[k]))}</td>' for k in ('condition', 'frame', 'text', 'conf', 'status')) + '</tr>' for row in plates)
        page = f'''<!doctype html><html lang="ko"><meta charset="utf-8"><title>{esc(clip_id)} 리뷰</title>
<style>body{{font-family:system-ui;max-width:1100px;margin:32px auto;padding:20px}}img{{max-width:420px}}figure{{display:inline-block;margin:8px}}td,th{{border:1px solid #ccc;padding:8px}}pre{{white-space:pre-wrap}}table{{border-collapse:collapse}}</style>
<h1>{esc(clip_id)} 리뷰 패키지</h1><p>보정 영상은 무음입니다. 원본 영상은 그대로 보존합니다.</p>
<h2>누락 결과</h2><pre>{esc(chr(10).join(manifest['missing']) or '없음')}</pre>
<h2>주의 사항</h2><pre>{esc(chr(10).join(manifest['warnings']) or '없음')}</pre>
<h2>키프레임</h2>{images}<h2>OCR 처리 현황</h2><pre>{esc(json.dumps(manifest["ocr_status"], ensure_ascii=False, indent=2))}</pre><h2>번호판</h2><table><tr><th>조건</th><th>프레임</th><th>문자</th><th>신뢰도</th><th>상태</th></tr>{rows}</table>
<h2>VLM 요약</h2><pre>{esc(json.dumps(vlm, ensure_ascii=False, indent=2))}</pre>
<h2>파일</h2><ul>{links}<li><a href="plates.csv">plates.csv</a></li><li><a href="params.json">params.json</a></li><li><a href="vlm_summary.json">vlm_summary.json</a></li><li><a href="manifest.json">manifest.json</a></li></ul></html>'''
        (temporary / 'summary.html').write_text(page, encoding='utf-8')
        temporary.rename(destination)
        return destination
    finally:
        if temporary.exists():
            shutil.rmtree(temporary)
