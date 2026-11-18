import csv
import hashlib
import json
from pathlib import Path
import numpy as np
import pytest
from src.io import save_frame, write_video
from tools.sensitivity import run_sensitivity


def frame(v=70):
    return np.full((48,64,3),v,dtype='uint8')

def test_sensitivity_uses_c_runner_and_evaluator(tmp_path,monkeypatch):
    import src.plate.run as plate_run
    save_frame(tmp_path/'data/frames/orig/rain_0.png',frame())
    calls=[]
    # Stub only the model-facing detector; real C CSV writer and evaluator run.
    def detect(img,cond,frame_id,results_dir):
        calls.append(str(results_dir))
        crop=save_frame(Path(results_dir)/'ocr/crops'/cond/(frame_id+'_0.png'),img)
        return [dict(bbox=(2,3,20,8),text='12가3456',status='readable',conf=.95,crop_path=str(crop))]
    monkeypatch.setattr(plate_run,'detect_plates',detect)
    rows=run_sensitivity(root=tmp_path, labels={'rain_0.png':[{'bbox':[2,3,20,8],'text':'12가3456'}]},
                         apply_ops=lambda f,p:f.copy())
    assert len(calls)==3 and len(set(calls))==3
    accuracy=[r for r in rows if r['metric']=='exact_match']
    assert len(accuracy)==3 and all(r['value']==1 and r['delta_vs_1']==0 for r in accuracy)
    assert len(list((tmp_path/'results/sensitivity').glob('*/results/ocr/adaptive.csv')))==3

def test_sensitivity_refuses_unlabeled_frames(tmp_path):
    save_frame(tmp_path/'data/frames/orig/rain_0.png',frame())
    with pytest.raises(ValueError,match='sets'):
        run_sensitivity(root=tmp_path,labels={},apply_ops=lambda f,p:f)
    assert not (tmp_path/'results/sensitivity').exists()
