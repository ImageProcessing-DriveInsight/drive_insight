import csv
import hashlib
import json
from pathlib import Path
import numpy as np
import pytest
from src.io import save_frame, write_video
from src.package import build_package


def frame(v=70):
    return np.full((48,64,3),v,dtype='uint8')

def test_package_c_csv_zero_and_missing(tmp_path):
    clip=tmp_path/'data/clips/rain.mp4'
    write_video([frame(),frame()],10,clip)
    save_frame(tmp_path/'data/frames/orig/rain_0.png',frame())
    save_frame(tmp_path/'data/frames/orig/rain_100.png',frame())
    crop=save_frame(tmp_path/'results/ocr/crops/orig/rain_0_0.png',frame())
    from src.plate.run import COLUMNS
    with (tmp_path/'results/ocr/orig.csv').open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=COLUMNS); w.writeheader()
        w.writerow(dict(frame='rain_0.png',plate=0,x=2,y=3,w=20,h=8,text='<script>',status='uncertain',crop_path=str(crop)))
        w.writerow(dict(frame='rain_100.png'))
    out=build_package('rain',root=tmp_path)
    manifest=json.loads((out/'manifest.json').read_text())
    assert manifest['ocr_status']['orig']['zero_detection_frames']==['rain_100.png']
    assert manifest['ocr_status']['orig']['plate_count']==1
    assert 'orig OCR 결과 없음' not in manifest['missing']
    assert 'adaptive OCR 결과 없음' in manifest['missing']
    with (out/'plates.csv').open(encoding='utf-8-sig') as f:
        rows=list(csv.DictReader(f))
    assert len(rows)==1 and json.loads(rows[0]['bbox'])==[2,3,20,8]
    assert '<script>' not in (out/'summary.html').read_text()
    assert hashlib.sha256(clip.read_bytes()).digest()==hashlib.sha256((out/'videos/rain.mp4').read_bytes()).digest()

def test_package_missing_and_paths(tmp_path):
    out=build_package('absent',root=tmp_path)
    assert json.loads((out/'manifest.json').read_text())['missing']
    with pytest.raises(ValueError): build_package('../x',root=tmp_path)
    with pytest.raises(FileExistsError): build_package('absent',root=tmp_path)
