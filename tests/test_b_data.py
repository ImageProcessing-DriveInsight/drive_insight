import csv
import hashlib
import json
from pathlib import Path
import numpy as np
import pytest
from src.io import save_frame, write_video
from tools.b_labels import create_templates, validate_annotations, export_plates
from tools.prepare_data import merge_manifests
from src.eval.ocr import load_labels, eval_ocr


def frame(v=70):
    return np.full((48,64,3),v,dtype='uint8')

def test_label_workflow_and_c_evaluator(tmp_path):
    frames = tmp_path/'data/frames/orig'
    save_frame(frames/'rain_0.png',frame())
    annotation = create_templates(frames,tmp_path/'data/annotations/scenes.json')
    data = json.loads(annotation.read_text())
    with pytest.raises(ValueError,match='pending'):
        export_plates(annotation,tmp_path/'data/labels/plates.json')
    item=data['rain_0.png']
    item.update(annotation_status='complete',annotator='B',reviewer='A',
                plates=[{'bbox':[2,3,20,8],'text':'12가3456','status':'readable'}])
    annotation.write_text(json.dumps(data))
    output=export_plates(annotation,tmp_path/'data/labels/plates.json',frames_dir=frames,require_review=True)
    assert load_labels(output)['rain_0'][0]['text']=='12가3456'
    metrics=eval_ocr([dict(frame='rain_0.png',x=2,y=3,w=20,h=8,text='12가3456',status='readable')],output)
    assert metrics['exact_match']==1
    item['plates'][0]['bbox']=[60,3,20,8]
    with pytest.raises(ValueError,match='outside'):
        validate_annotations(data)

def test_review_and_frame_set_required(tmp_path):
    save_frame(tmp_path/'frames/rain_0.png',frame())
    path=create_templates(tmp_path/'frames',tmp_path/'scenes.json')
    data=json.loads(path.read_text()); data['rain_0.png'].update(annotation_status='complete',annotator='B')
    path.write_text(json.dumps(data))
    with pytest.raises(ValueError,match='reviewer'):
        export_plates(path,tmp_path/'labels.json',require_review=True)
    save_frame(tmp_path/'frames/rain_100.png',frame())
    with pytest.raises(ValueError,match='sets'):
        export_plates(path,tmp_path/'labels.json',frames_dir=tmp_path/'frames')

def test_manifest_collisions_and_empty(tmp_path):
    p=tmp_path/'b.csv'; out=tmp_path/'eval.csv'
    p.write_text('clip,timestamp_ms,condition,source,license\nrain.mp4,0,rain,self,own\n')
    assert len(merge_manifests([p],out))==1
    with pytest.raises(FileExistsError):
        merge_manifests([p],out)
    with pytest.raises(ValueError,match='Duplicate'):
        merge_manifests([p,p],tmp_path/'dup.csv')
    p.write_text('clip,timestamp_ms,condition,source,license\n')
    with pytest.raises(ValueError,match='No evaluation'):
        merge_manifests([p],tmp_path/'empty.csv')
