import csv
import hashlib
import json
from pathlib import Path
import numpy as np
import pytest
from src.io import save_frame, write_video
from tools.b_status import status


def frame(v=70):
    return np.full((48,64,3),v,dtype='uint8')

def test_status_does_not_claim_empty_frames_match(tmp_path):
    result=status(tmp_path)
    assert result['all_frame_sets_match'] is False
    assert not result['eval_set_exists']


def test_b_modules_use_only_opencv_io():
    import ast
    allowed={'VideoCapture','VideoWriter','VideoWriter_fourcc','imdecode','imencode'}
    root=Path(__file__).resolve().parents[1]
    for folder in ('src/io','src/adaptive','src/package'):
        for path in (root/folder).glob('*.py'):
            for node in ast.walk(ast.parse(path.read_text(encoding='utf-8'))):
                if isinstance(node,ast.Call) and isinstance(node.func,ast.Attribute) and isinstance(node.func.value,ast.Name) and node.func.value.id=='cv2':
                    assert node.func.attr in allowed, (path,node.lineno,node.func.attr)
