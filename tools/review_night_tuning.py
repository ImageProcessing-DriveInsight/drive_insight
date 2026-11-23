"""Local, tuning-only DIP comparisons. No evaluation pixels, uploads or automatic winner."""

import argparse
from collections import Counter
import csv
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import statistics
import sys
import time

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from src.dip import FIXED_PARAMS, apply_ops
from src.dip.color import bgr_to_ycrcb
from src.io.video import load_frame, resolve, save_frame
from tools.aihub_vehicles import scene_entry
from tools.audit_night_data import DEFAULT_ROOT
from tools.benchmark_dip import environment


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def candidates():
    """Predeclared ablations, not optimized values or changes to global FIXED_PARAMS."""
    base = dict(FIXED_PARAMS)
    return {
        "A": {"label": "Current fixed baseline", "params": base},
        "B": {"label": "Baseline without sharpening", "params": {**base, "unsharp": 0.0}},
        "C": {"label": "Brighter, without sharpening", "params": {**base, "gamma": 0.60, "unsharp": 0.0}},
        "D": {"label": "Brighter, stronger Gaussian", "params": {**base, "gamma": 0.60,
               "unsharp": 0.0, "ksize": 5, "sigma": 1.2}},
    }


def _safe_source(root, value):
    relative = PurePosixPath(value)
    if relative.is_absolute() or ".." in relative.parts or not relative.parts or relative.parts[0] != "images":
        raise ValueError("Source must be a relative path under images/")
    path = root.joinpath(*relative.parts)
    if not path.resolve().is_relative_to(root.resolve()) or path.is_symlink():
        raise ValueError("Source escapes dataset root or is a symlink")
    return path


def load_tuning_rows(root, manifest_dir):
    """Read evaluation metadata only to reject overlap; never open evaluation images."""
    root, manifest_dir = Path(root), Path(manifest_dir)
    frozen = json.loads((manifest_dir / "COMPLETE.json").read_text(encoding="utf-8"))
    rows = {}
    for split in ("tuning", "evaluation"):
        name = f"{split}_frames.csv"
        if sha256(manifest_dir / name) != frozen["csv_sha256"][name]:
            raise ValueError(f"Frozen manifest changed: {name}")
        with (manifest_dir / name).open(encoding="utf-8-sig", newline="") as stream:
            rows[split] = list(csv.DictReader(stream))
        if any(row["split"] != split for row in rows[split]):
            raise ValueError("Wrong split in frozen manifest")
    tuning, evaluation = rows["tuning"], rows["evaluation"]
    expected_scenes = {frozen["selected_scenes"]["normal"][4], frozen["selected_scenes"]["hard"][1]}
    if len(tuning) != 12 or Counter(row["scene"] for row in tuning) != Counter({s: 6 for s in expected_scenes}):
        raise ValueError("Expected six tuning frames in each of two scenes")
    if ({r["scene"] for r in tuning} & {r["scene"] for r in evaluation}
            or {r["source"] for r in tuning} & {r["source"] for r in evaluation}
            or {r["frame"] for r in tuning} & {r["frame"] for r in evaluation}):
        raise ValueError("Evaluation/tuning overlap")
    if len({r["frame"].casefold() for r in tuning}) != 12:
        raise ValueError("Duplicate tuning output frame")
    for row in tuning:
        name = row["frame"]
        if not re.fullmatch(r"[A-Za-z0-9_.-]+\.png", name) or row["condition"] != "low_light":
            raise ValueError("Invalid tuning filename or condition")
        source = _safe_source(root, row["source"])
        if source.parent.name != row["scene"] or source.stem + ".png" != name:
            raise ValueError("Source scene/name differs from the frozen frame")
        if sha256(source) != frozen["source_image_sha256"][row["source"]]:
            raise ValueError("Tuning original image hash changed")
        relative = source.relative_to(root / "images").with_suffix(".json")
        label = root / "labels" / relative
        if not label.resolve().is_relative_to(root.resolve()) or label.is_symlink():
            raise ValueError("Label escapes dataset root or is a symlink")
        if sha256(label) != frozen["source_label_sha256"][row["source"]]:
            raise ValueError("Tuning label hash changed")
    return tuning, frozen


def diagnostics(image):
    """Descriptive proxies only: neither noise nor recognition quality ground truth."""
    y = bgr_to_ycrcb(image)[..., 0]
    horizontal = np.abs(np.diff(y.astype(np.float32), axis=1)).mean() if y.shape[1] > 1 else 0
    vertical = np.abs(np.diff(y.astype(np.float32), axis=0)).mean() if y.shape[0] > 1 else 0
    return {"mean_y": float(y.mean()), "std_y": float(y.std()),
            "dark_y_le_5_share": float(np.mean(y <= 5)), "bright_y_ge_250_share": float(np.mean(y >= 250)),
            "adjacent_difference": float((horizontal + vertical) / 2)}


def common_crop(image, label):
    """One original-label vehicle ROI shared by every variant; no OCR or adaptive crop."""
    h, w = image.shape[:2]
    vehicles = scene_entry(label, "tuning label")["vehicles"]
    if vehicles:
        x, y, bw, bh = max(vehicles, key=lambda v: v["bbox"][2])["bbox"]
        pad_x, pad_y = round(bw * 0.15), round(bh * 0.15)
        box = [max(0, x - pad_x), max(0, y - pad_y), min(w, x + bw + pad_x), min(h, y + bh + pad_y)]
        if box[2] > box[0] and box[3] > box[1]:
            return box, "widest labeled vehicle, 15% context"
    return [w // 4, h // 4, max(w // 4 + 1, 3 * w // 4), max(h // 4 + 1, 3 * h // 4)], "center fallback"


def review_html(report):
    """Offline page with local relative images, no fetch, CDN, telemetry or submission."""
    data = json.dumps({"frames": report["frames"], "variants": report["variants"]}, ensure_ascii=False).replace("<", "\\u003c")
    return r"""<!doctype html><html lang="ko"><meta charset="utf-8">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; img-src 'self' file:; style-src 'unsafe-inline'; script-src 'unsafe-inline'; connect-src 'none'; form-action 'none'; base-uri 'none'">
<title>A 야간 튜닝 검토 — 평가 자료 아님</title>
<style>body{margin:20px;background:#181b20;color:#eee;font:16px system-ui}button,select{font:inherit;padding:8px;margin:4px}
header{max-width:1100px}small,p{line-height:1.6}.bar{position:sticky;top:0;background:#252a32;padding:8px;z-index:2}
.pair{display:grid;grid-template-columns:1fr 1fr;gap:14px}.pane{min-width:0;background:#101216;padding:8px}.viewport{overflow:auto;max-height:72vh}
.viewport img{display:block;width:100%;height:auto;image-rendering:auto}.native .viewport img{width:auto;max-width:none}
textarea{width:98%;min-height:250px;background:#252a32;color:#eee;font:14px monospace}a{color:#9cceff}#metrics{white-space:pre-wrap;font:13px monospace}
@media(max-width:800px){.pair{grid-template-columns:1fr}}</style>
<header><h1>야간 튜닝 12장 — 시각 검토</h1><p>원본과 A/B/C/D는 같은 해상도·같은 크롭입니다. 평가용 30장은 처리하지 않았고,
전역 FIXED_PARAMS도 바꾸지 않았습니다. A=기존값, B=샤프닝 제거, C=B에서 감마 0.60, D=C에서 Gaussian 5×5·σ1.2입니다.</p>
<p>밝아진 정도만으로 고르지 말고 차량·차선 식별, 어두운 면의 얼룩/입자, 색감, 밝은 테두리(halo), 흐림을 함께 보세요.
지표의 밝기·인접 차이는 설명용이며 화질 점수나 노이즈 정답이 아닙니다. 화면 밝기는 비교 중 고정해주세요.</p></header>
<div class="bar"><button id="prev">이전</button><select id="frame" aria-label="검토 프레임"></select><button id="next">다음</button><br>
왼쪽 <select id="left" aria-label="왼쪽 후보"></select> 오른쪽 <select id="right" aria-label="오른쪽 후보"></select>
<button id="crop">공통 차량 크롭 보기</button><button id="zoom">1:1 픽셀 보기</button></div>
<h2 id="name"></h2><p id="context"></p><div class="pair" id="pair">
<section class="pane"><h3 id="lt"></h3><div class="viewport"><img id="li" alt="왼쪽 비교 이미지"></div><a id="ll" target="_blank" rel="noopener">PNG 원본 크기로 열기</a></section>
<section class="pane"><h3 id="rt"></h3><div class="viewport"><img id="ri" alt="오른쪽 비교 이미지"></div><a id="rl" target="_blank" rel="noopener">PNG 원본 크기로 열기</a></section></div>
<p id="metrics"></p><h2>피드백</h2><p>장면별 선호 후보와 문제 프레임만 적어도 됩니다. D가 가장 밝다고 반드시 좋은 것은 아닙니다.
모두 부적합/차이 없음도 유효한 답입니다. 아래 내용을 복사해 채팅으로 보내주세요. 이 페이지는 입력을 전송·자동 저장하지 않습니다.</p>
<textarea id="feedback" aria-label="피드백 초안"></textarea>
<script>const DATA=__DATA__;let crop=false,zoom=false;const $=id=>document.getElementById(id);
const options={original:'Original / 보정 전',...Object.fromEntries(Object.entries(DATA.variants).map(([k,v])=>[k,k+' / '+v.label]))};
for(const id of ['left','right'])for(const [v,label] of Object.entries(options)){const o=document.createElement('option');o.value=v;o.textContent=label;$(id).appendChild(o)}
DATA.frames.forEach((f,i)=>{const o=document.createElement('option');o.value=i;o.textContent=(i+1)+' / '+f.scene+' / '+f.frame;$('frame').appendChild(o)});
$('left').value='original';$('right').value='A';function render(){const f=DATA.frames[+$('frame').value];$('name').textContent=f.scene+' — '+f.frame;
$('context').textContent='tuning only | '+f.difficulty+' | '+f.shape[1]+'×'+f.shape[0]+' | ROI: '+f.crop_reason;
let metric=[];for(const [side,v] of [['l',$('left').value],['r',$('right').value]]){const path=(crop?'crops/':'')+v+'/'+f.frame;
$(side+'i').src=path;$(side+'l').href=path;$(side+'t').textContent=options[v];const d=f.outputs[v].diagnostics;
metric.push(v+': mean Y='+d.mean_y.toFixed(2)+', dark≤5='+(100*d.dark_y_le_5_share).toFixed(1)+'%, Y≥250='+(100*d.bright_y_ge_250_share).toFixed(2)+'%, adjacent diff='+d.adjacent_difference.toFixed(2))}
$('metrics').textContent=metric.join('\n');$('pair').classList.toggle('native',zoom);$('crop').textContent=crop?'전체 프레임 보기':'공통 차량 크롭 보기';$('zoom').textContent=zoom?'화면에 맞추기':'1:1 픽셀 보기'}
for(const id of ['frame','left','right'])$(id).onchange=render;
$('prev').onclick=()=>{$('frame').value=Math.max(0,+$('frame').value-1);render()};$('next').onclick=()=>{$('frame').value=Math.min(DATA.frames.length-1,+$('frame').value+1);render()};
$('crop').onclick=()=>{crop=!crop;render()};$('zoom').onclick=()=>{zoom=!zoom;render()};
$('feedback').value='Clip_437 (일반): 선호 후보= / 밝기= / 노이즈= / 색감= / halo·흐림=\nClip_230 (어려움): 선호 후보= / 개선 여부= / 가장 큰 문제=\n문제 프레임: 파일명 또는 순번 / 후보 / 문제\n다른 조건 확인 전 최종 고정값은 미확정';render();</script></html>""".replace("__DATA__", data)


def run_review(root=DEFAULT_ROOT, manifest_dir="data/manifests/a_night",
               output="data/frames/tuning/night/review_v1", *, warmups=2):
    root, manifest_dir, output = (resolve(p).resolve() for p in (root, manifest_dir, output))
    if type(warmups) is not int or warmups < 0:
        raise ValueError("warmups must be a nonnegative integer")
    if any(output == p or output.is_relative_to(p) or p.is_relative_to(output) for p in (root, manifest_dir)):
        raise ValueError("Review output must not overlap dataset or frozen manifests")
    if output.exists():
        raise FileExistsError("Review output already exists; use a new experiment directory")
    rows, frozen = load_tuning_rows(root, manifest_dir)
    variants = candidates()
    report = {"schema_version": 1, "created_utc": datetime.now(timezone.utc).isoformat(),
              "environment": environment(), "tool_sha256": sha256(Path(__file__)),
              "status": "awaiting_human_review", "global_fixed_params_changed": False,
              "variants": variants, "warmups_per_variant": warmups,
              "timing_scope": "one operation call per tuning frame; excludes diagnostics and IO; not a repeated benchmark",
              "metrics_scope": "descriptive proxies, not quality/noise/OCR ground truth",
              "input_manifest_sha256": sha256(manifest_dir / "tuning_frames.csv"), "frames": []}
    output.mkdir(parents=True, exist_ok=False)
    first = load_frame(_safe_source(root, rows[0]["source"]))
    for variant in variants.values():
        for _ in range(warmups):
            apply_ops(first, variant["params"])
    for row in rows:
        source = _safe_source(root, row["source"])
        frame = load_frame(source)
        original_pixels = hashlib.sha256(frame.tobytes()).hexdigest()
        label_path = root / "labels" / source.relative_to(root / "images").with_suffix(".json")
        label = json.loads(label_path.read_text(encoding="utf-8-sig"))
        box, reason = common_crop(frame, label)
        record = {**row, "shape": list(frame.shape), "source_sha256": frozen["source_image_sha256"][row["source"]],
                  "crop_bbox_xyxy": box, "crop_reason": reason, "outputs": {}}
        x0, y0, x1, y1 = box
        for key in ("original", *variants):
            start = time.perf_counter()
            image = frame if key == "original" else apply_ops(frame, variants[key]["params"])
            elapsed = 0.0 if key == "original" else (time.perf_counter() - start) * 1000
            if image.shape != frame.shape or image.dtype != frame.dtype:
                raise ValueError("Candidate changed image shape or dtype")
            target = output / key / row["frame"]
            save_frame(target, image)
            crop_path = output / "crops" / key / row["frame"]
            save_frame(crop_path, image[y0:y1, x0:x1])
            record["outputs"][key] = {"params": None if key == "original" else variants[key]["params"].copy(),
                "enhance_ms": elapsed, "sha256": sha256(target), "crop_sha256": sha256(crop_path),
                "diagnostics": diagnostics(image)}
        if hashlib.sha256(frame.tobytes()).hexdigest() != original_pixels or sha256(source) != record["source_sha256"]:
            raise ValueError("Tuning original was modified")
        report["frames"].append(record)
        print(f"Prepared {row['scene']} / {row['frame']}", flush=True)
    report["median_enhance_ms"] = {k: statistics.median(f["outputs"][k]["enhance_ms"] for f in report["frames"]) for k in variants}
    (output / "report.json").write_text(json.dumps(report, indent=2, ensure_ascii=False, allow_nan=False), encoding="utf-8")
    (output / "index.html").write_text(review_html(report), encoding="utf-8")
    feedback = "Clip_437 (normal): preferred= ; brightness= ; noise= ; color= ; halo/blur=\nClip_230 (hard): preferred= ; useful improvement= ; main issue=\nProblem frames: filename or index / variant / issue\nGlobal params remain undecided until cross-condition validation.\n"
    (output / "feedback_template.txt").write_text(feedback, encoding="utf-8")
    ready = {"status": "awaiting_human_review", "tuning_frames": len(rows), "evaluation_images_processed": 0,
             "global_fixed_params": dict(FIXED_PARAMS), "report_sha256": sha256(output / "report.json"),
             "html_sha256": sha256(output / "index.html")}
    (output / "REVIEW_READY.json").write_text(json.dumps(ready, indent=2), encoding="utf-8")
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=DEFAULT_ROOT)
    parser.add_argument("--manifest-dir", default="data/manifests/a_night")
    parser.add_argument("--output", default="data/frames/tuning/night/review_v1")
    parser.add_argument("--warmups", type=int, default=2)
    args = parser.parse_args(argv)
    try:
        report = run_review(args.root, args.manifest_dir, args.output, warmups=args.warmups)
    except (OSError, ValueError, TypeError, KeyError, IndexError) as exc:
        parser.exit(1, f"Night tuning review failed: {exc}\n")
    print(json.dumps({"tuning_frames": len(report["frames"]), "status": report["status"],
                      "median_enhance_ms": report["median_enhance_ms"]}, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
