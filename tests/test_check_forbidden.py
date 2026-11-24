"""Checker fixtures are source strings and never executed or imported."""

import json
from pathlib import Path
import subprocess
import sys

import pytest

from tools.check_forbidden import ALLOWED_CV2_IO, check_source, scan_paths


@pytest.mark.parametrize("member", sorted(ALLOWED_CV2_IO))
def test_allowlisted_io(member):
    assert check_source(f"import cv2\ncv2.{member}('file')") == []


@pytest.mark.parametrize("source", [
    "import cv2\ncv2.GaussianBlur(img, (3,3), 1)",
    "import cv2 as vision\nvision.resize(img,(1,1))",
    "from cv2 import medianBlur as blur\nblur(img,3)",
    "import cv2\nf = cv2.equalizeHist\nf(img)",
    "import cv2\nv = cv2\nf = v\nf.filter2D(img,-1,k)",
    "import cv2\ngetattr(cv2,'threshold')(img,0,255,0)",
    "import cv2\ngetattr(cv2, member)(img)",
    "import cv2\ncv2.cuda.GaussianBlur(img)",
    "import cv2.cv2 as v\nv.cvtColor(img,0)",
    "def f(img):\n    return cv2.cvtColor(img,0)\nimport cv2",
])
def test_forbidden_references_and_aliases(source):
    findings = check_source(source, "example.py")
    assert findings and any(f.code == "CV2_FORBIDDEN" for f in findings)
    assert all(f.path == "example.py" and f.line > 0 and f.column > 0 for f in findings)


def test_line_and_column():
    findings = check_source("import cv2\n\ncv2.resize(img,(3,3))", "x.py")
    assert any((f.line, f.column) == (3, 1) for f in findings)


def test_constants_comments_docstrings_and_unrelated_methods():
    source = '''"""cv2.resize(x), apply_ops_stub"""
import cv2 as v
# v.GaussianBlur(x), apply_ops_stub
text = "function_stub"
img = v.imdecode(data, v.IMREAD_COLOR)
cap = v.VideoCapture(path)
ok, img = cap.read()
fps = cap.get(v.CAP_PROP_FPS)
other.resize()
'''
    assert check_source(source) == []


def test_function_parameter_shadow_and_scope_isolation():
    assert check_source("import cv2\ndef f(cv2):\n    return cv2.resize()") == []
    assert check_source("def a():\n    import cv2 as v\n    v.imread('x')\ndef b(v):\n    v.resize()") == []
    assert check_source("import cv2\nf = lambda cv2: cv2.resize()") == []


def test_class_attribute_does_not_shadow_module_in_method():
    source = "import cv2\nclass C:\n    cv2 = None\n    def f(self):\n        return cv2.resize(img,(1,1))"
    assert any(f.code == "CV2_FORBIDDEN" for f in check_source(source))


@pytest.mark.parametrize("source", [
    "def apply_ops_stub(x): return x", "async def f_stub(x): return x",
    "class Detector_stub: pass", "x_stub = 1", "obj.f_stub()", "def f(arg_stub): pass",
    "getattr(obj, 'enhance_stub')()", "from module import thing_stub as thing",
])
def test_stub_identifiers(source):
    assert any(f.code == "STUB_IDENTIFIER" for f in check_source(source))


@pytest.mark.parametrize("source", ["from cv2 import *", "__import__('cv2')",
    "import importlib as il\nv=il.import_module('cv2')",
    "from importlib import import_module as load\nv=load('cv2')"])
def test_uninspectable_import_styles_are_reported(source):
    assert check_source(source)


def test_syntax_error_is_not_clean():
    assert check_source("def broken(")[0].code == "PARSE_ERROR"


def test_scan_uses_encoding_cookie_and_deduplicates_files(tmp_path):
    file = tmp_path / "코드.py"
    file.write_bytes('# coding: cp949\n# 한글\nimport cv2\ncv2.resize(x,(1,1))\n'.encode('cp949'))
    result = scan_paths([tmp_path, file])
    assert len(result.files) == 1 and result.exit_code == 1
    assert any(f.code == "CV2_FORBIDDEN" for f in result.findings)


def test_missing_empty_and_bad_encoding_are_errors(tmp_path):
    assert scan_paths([]).exit_code == 2
    assert scan_paths([tmp_path]).exit_code == 2
    assert scan_paths([tmp_path / "missing"]).exit_code == 2
    (tmp_path / "bad.py").write_bytes(b'\xff\xfe\xff')
    assert scan_paths([tmp_path]).exit_code == 2


def test_current_submission_source_has_no_findings():
    result = scan_paths()
    assert result.files
    assert result.findings == []


@pytest.mark.parametrize("module", [False, True])
def test_cli_default_source_and_json(module, tmp_path):
    root = Path(__file__).resolve().parents[1]
    command = [sys.executable, "-m", "tools.check_forbidden"] if module else [
        sys.executable, str(root / "tools/check_forbidden.py")]
    result = subprocess.run(command + ["--json"], cwd=root if module else tmp_path,
                            capture_output=True, text=True, encoding="utf-8")
    assert result.returncode == 0 and result.stderr == ""
    report = json.loads(result.stdout)
    assert report["exit_code"] == 0 and report["findings"] == []
    assert report["files_scanned"] == len(report["files"]) > 0
    assert all(p.startswith("src/") for p in report["files"])


@pytest.mark.parametrize("source,exit_code,code", [
    ("raise RuntimeError('must never execute')", 0, None),
    ("import cv2\ncv2.resize(img,(2,2))", 1, "CV2_FORBIDDEN"),
    ("def enhance_stub(x): return x", 1, "STUB_IDENTIFIER"),
    ("def broken(", 2, "PARSE_ERROR"),
])
def test_cli_exit_codes_and_diagnostics(tmp_path, source, exit_code, code):
    root = Path(__file__).resolve().parents[1]
    file = tmp_path / "fixture.py"
    file.write_text(source, encoding="utf-8")
    command = [sys.executable, str(root / "tools/check_forbidden.py"), str(file)]
    plain = subprocess.run(command, capture_output=True, text=True, encoding="utf-8")
    report = subprocess.run(command + ["--json"], capture_output=True, text=True, encoding="utf-8")
    assert plain.returncode == report.returncode == exit_code
    assert plain.stderr == report.stderr == ""
    parsed = json.loads(report.stdout)
    assert parsed["exit_code"] == exit_code and parsed["files_scanned"] == 1
    if code:
        assert code in plain.stdout and f"{file}:" in plain.stdout
        assert any(f["code"] == code for f in parsed["findings"])
    else:
        assert parsed["findings"] == []


def test_read_error_takes_precedence_over_violations(tmp_path):
    (tmp_path / "bad.py").write_bytes(b"\xff")
    (tmp_path / "forbidden.py").write_text("x_stub = None", encoding="utf-8")
    result = scan_paths([tmp_path])
    assert result.exit_code == 2
    assert {f.code for f in result.findings} == {"READ_ERROR", "STUB_IDENTIFIER"}
