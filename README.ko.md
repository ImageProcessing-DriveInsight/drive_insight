# DriveInsight

디지털 영상처리 팀 프로젝트 02 · 16조 Black Box · [English](README.md)

DriveInsight는 악조건(야간, 비, 안개, 역광, 터널)에서 찍힌 블랙박스 프레임을 보정하고, 그 보정이 사람 눈에만
좋아 보이는지 기계가 읽는 데도 도움이 되는지 확인합니다. 모든 프레임을 세 조건으로 처리하고 같은 기준으로 채점합니다.

| 조건 | 뜻 |
| --- | --- |
| `orig` | 원본 프레임 |
| `fixed` | 고정 보정: 모든 프레임에 같은 파라미터 (A) |
| `adaptive` | 적응형 보정: 화질을 재고 프레임마다 파라미터를 고름 (B) |

세 조건은 번호판 인식과 차량 검출(C), 시각 언어 모델(VLM)의 장면 요약(D)으로 비교합니다. 영상처리 연산은 팀이
NumPy로 직접 구현했고, 사전학습 모델은 차량 검출, 글자 인식, 장면 요약에만 씁니다
([사전학습 모델과 직접 구현](#사전학습-모델과-직접-구현) 참고).

```text
클립 / 이미지 시퀀스 ──► 원본 PNG 프레임 (B) ──┬─► orig
                                                ├─► 고정 보정 (A) ──────────────► fixed
                                                └─► 화질 측정 → 규칙 → 연산 (B) ─► adaptive
조건마다 ──► 차량 → 번호판 후보 → 크롭 전처리 → OCR → 상태 판정 (C)
         ──► 장면 요약 (D)
모든 조건 ──► 평가, 집계, 비교, 환경 조건별 결과 (C) ──► 리뷰 패키지 (B)
```

## 팀과 모듈

| 팀원 | 모듈 | 맡은 일 |
| --- | --- | --- |
| A | `src/dip/` | 색 공간 변환, 히스토그램 평활화, 감마, Gaussian·Median 필터, Unsharp masking(NumPy), `apply_ops`, `fixed_enhance`, 고정 보정 일괄 처리, 야간 데이터 점검과 프레임 목록 |
| B | `src/io/`, `src/adaptive/`, `src/package/` | 프레임·영상 입출력, 화질 측정, 규칙 기반 파라미터, `adaptive_enhance`, 평가 목록과 라벨, 리뷰 패키지, 민감도 실험 |
| C | `src/plate/`, `src/eval/` | 차량·번호판 검출, 크롭 전처리, OCR과 상태 판정, OCR 평가, 집계, 비교, 차량 검출률, 환경 조건별 결과 |
| D | `src/common/`, `src/pipeline/`, `src/vlm/` | 실험 실행기와 시간 측정, VLM 요약과 채점, 프로젝트 파일, 제출. 아직 머지 전(#38) |

인터페이스, 폴더, 일정은 [팀 계획](docs/plan/team_plan.ko.md), 기능과 진행 상태는 [기능 명세](docs/plan/feature_spec.ko.md),
전체 문서 목록은 [docs/](docs/README.ko.md)에 있습니다.

## 설치

Windows의 Python 3.12(팀원 PC)에서 씁니다. 모든 명령은 저장소 루트에서 실행합니다.

```bat
python -m venv .venv
.venv\Scripts\activate
python -m pip install -r requirements-plate.txt -r requirements-b.txt -r requirements-dip.txt
```

- 새 가상환경 하나에 설치합니다. `requirements-video-io.txt`는 같이 설치하지 않습니다. `opencv-python-headless`를
  고정하는데, OpenCV 배포판이 섞이면 `cv2`가 깨질 수 있습니다.
- `requirements-plate.txt`의 `pandas`, `chardet` 버전은 최신 빌드가 막힌 팀원 PC 한 대 때문에 고정한 것입니다.
- 모델 가중치는 처음 실행할 때 받아집니다. YOLO는 `weights/`(git 제외), PaddleOCR은 `~/.paddlex/official_models/`입니다.
- B의 문서는 Windows에서 `python` 대신 `py`를 씁니다. 둘 다 됩니다.

## 데이터

실제 클립, 프레임, 라벨, 결과는 **git에 없습니다.** 실제 번호판이 보이거나 글자가 들어 있고, AI Hub 데이터는 승인받은
팀원만 쓸 수 있기 때문입니다. 팀원끼리 직접 주고받습니다.

```text
data/clips/                        원본 영상 (수정하지 않음)
data/eval_set.csv                  clip, timestamp_ms, condition, source, license (팀원 목록을 B가 합침)
data/frames/orig/ fixed/ adaptive/ 세 조건 폴더에 같은 <clip>_<ms>.png
data/frames/clear/                 합성 안개를 만든 맑은 프레임 (C의 안개 클립만)
data/annotations/scenes.json       프레임별 라벨: 차량, 번호판, 사건 (B의 라벨 도구)
data/annotations/aihub_vehicles.json  차량 검출률용으로 바꾼 AI Hub 차량 라벨 (C)
data/labels/plates.json            OCR 평가용 번호판 라벨 (scenes.json에서 내보냄)
data/plate_countries.json          미국 번호판 프레임 (있을 때만)
results/                           출력, 아래 참고
package/<clip>/                    리뷰 패키지
```

프레임은 항상 `uint8` BGR, `(H, W, 3)` 배열입니다. 세 조건 폴더의 파일 이름이 똑같아서, 모든 조건을 같은 프레임으로 채점합니다.

## 실행

순서대로 진행합니다. 각 담당이 자기 단계를 돌리고 결과 파일을 넘깁니다.

| 단계 | 담당 | 명령 | 출력 |
| --- | --- | --- | --- |
| 1. 팀원 목록 합치기 | B | `python -m tools.prepare_data member_a.csv member_b.csv member_c.csv member_d.csv` | `data/eval_set.csv` |
| 2. 원본 프레임 추출 | B | `python -m tools.b_cli extract` | `data/frames/orig/` |
| 3. 라벨 | B, 각 담당 | `python -m tools.b_labels init`, `scenes.json` 채우기(초안: `python tools/label_draft.py draft`), `python -m tools.b_labels export --require-review` | `data/annotations/scenes.json`, `data/labels/plates.json` |
| 3a. AI Hub 차량 라벨 | C | `python tools/aihub_vehicles.py <라벨 폴더> [--names names.csv]` | `data/annotations/aihub_vehicles.json` |
| 4. 고정 보정 | A | `python -m src.dip.batch` | `data/frames/fixed/`, `results/params/fixed.json` |
| 5. 적응형 보정 | B | `python -m tools.b_cli frames --apply-ops src.dip.fixed:apply_ops` | `data/frames/adaptive/`, `results/params/adaptive.json` |
| 6. 번호판, 차량, 평가, 비교 | C | `python tools/plate_report.py --scenes data/annotations/scenes.json data/annotations/aihub_vehicles.json` | `results/` |
| 7. 환경 조건별 결과 | C | `python tools/env_report.py --scenes data/annotations/scenes.json data/annotations/aihub_vehicles.json [--envs envs.csv]` | `results/by_env/` |
| 8. 장면 요약과 실행기 | D | 진행 중(#38) | `results/vlm/score.csv`, `results/timing.csv` |
| 9. 리뷰 패키지 | B | `python -m tools.b_cli package <clip>` | `package/<clip>/summary.html` |

그 밖의 도구:

```bash
python -m tools.b_cli video data/clips/<clip>.mp4 --mode adaptive   # 보정 영상 (--mode fixed도 가능)
python -m tools.sensitivity --scale 0.8 1.2 --labels data/labels    # B: 적응형 임계값 배율 실험
python -m tools.audit_night_data --decode-images --output data/annotations/<report>.json   # A: 야간 데이터 점검
python -m tools.select_night_frames                                 # A: 공통 기준으로 야간 프레임 목록
python -m tools.verify_fixed_batch snapshot --snapshot data/annotations/fixed_orig_snapshot.json   # A: 일괄 처리 전
python -m tools.verify_fixed_batch verify --snapshot data/annotations/fixed_orig_snapshot.json     # A: 일괄 처리 후
python tools/synth_fog.py make <맑은 클립> <출력>                   # C: 맑은 날 영상으로 합성 안개
python tools/pick_frames.py scan <클립>                             # C: 차량 크기로 타임스탬프 고르기
python tools/compare_images.py --hide 2                             # C: 발표용 이미지, 번호판 뒤 두 글자 가림
```

## 출력

| 파일 | 내용 |
| --- | --- |
| `results/ocr/<cond>.csv` | 번호판마다 한 행: 박스, 크롭, 글자, 신뢰도, 상태(`readable`, `uncertain`, `unreadable`), OCR 시간 |
| `results/ocr/ocr_summary.csv` | 검출률, 완전 일치율, 문자 정확도, 틀렸는데 readable로 낸 수, 못 읽는 번호판을 readable로 낸 수 |
| `results/summary.csv` | 조건별 OCR 지표, VLM 점수, 단계별 시간 |
| `results/compare.csv`, `worse_cases.csv` | `orig` → `fixed`, `fixed` → `adaptive`에서 좋아지거나 나빠진 프레임과 부호 검정, 나빠진 번호판 |
| `results/vehicles.csv`, `vehicle_compare.csv` | 차량 크기별 검출률, 조건 사이에 새로 찾거나 놓친 차량 |
| `results/by_env/` | 같은 표를 환경 조건(안개, 야간, 비, 터널, 역광)별로 |
| `results/figures/` | 발표용 번호판·차량 이미지 |
| `package/<clip>/summary.html` | 리뷰 패키지: 대표 프레임, OCR, VLM, 파일 목록 |

`results/ocr/`, `worse_cases.csv`, `results/vehicles/`, `results/figures/`, `results/by_env/`에는 번호판 글자나 실제 번호판
이미지가 들어가므로 git이 무시합니다.

## 지금까지의 결과

직접 찍은 블랙박스 클립에 합성 안개(클립 11개, 프레임 48장, 읽을 수 있는 라벨 번호판 13개, 라벨 차량 222대,
[자세히](docs/dashcam_results.ko.md)):

- 문자 정확도는 안개 프레임 0.81, 고정 보정 뒤 0.70, 적응형 보정 뒤 0.81입니다. 고정 보정은 5프레임을 나쁘게 했고
  좋아진 프레임은 없습니다(부호 검정 p 0.0625, 방향일 뿐 증명은 아님).
- 이 프레임들에서는 적응형 규칙이 하나도 발동하지 않아 적응형이 원본과 같습니다.
- 차량 검출률은 안개 0.54(폭 100 px 미만 차량은 0.12), 고정 보정 뒤 0.51입니다.

야간, 비, 터널, 역광 결과는 통합 점검 3(11/24)과 D의 VLM 점수 뒤에 추가합니다.

## 사전학습 모델과 직접 구현

| 부분 | 사전학습 | 직접 구현 |
| --- | --- | --- |
| 영상 보정 (A) | – | 색 공간 변환, 히스토그램 평활화, 감마, Gaussian·Median 필터, Unsharp masking(NumPy), 고정 파라미터 |
| 적응형 보정 (B) | – | 밝기·대비·노이즈·선명도 측정, 규칙 기반 파라미터 선택 |
| 프레임·영상 입출력 (B) | OpenCV(읽기·쓰기만) | 타임스탬프 추출, 출력 검사 |
| 차량 검출 (C) | YOLOv8n, Ultralytics 8.4.208, COCO 가중치, AGPL-3.0 | 클래스·신뢰도 필터, 촬영 차량 필터(대시보드와 반사), 차량당 박스 하나 |
| 번호판 검출 (C) | – | 후보 탐색: 수직 에지, 밝기, 적분 영상 기반 주변 대비, 박스 확장, NMS, 차량당 후보 4개 |
| 크롭 전처리 (C) | – | 그레이 변환, 쌍선형 리사이즈, 대비 스트레칭, 극성 맞춤, 기울기 보정, Otsu |
| OCR (C) | PaddleOCR 3.7.0, `korean` PP-OCRv5, Apache-2.0 | 줄 잇기, O/I 보정, 정규화. 미국 번호판은 번호 줄만 |
| 상태 판정 (C) | – | 한국·미국 번호판 형식에 따른 `readable` / `uncertain` / `unreadable` 규칙 |
| 평가 (C) | – | 짝짓기, 지표, 집계, 비교, 부호 검정, 환경 조건별 결과, 발표용 이미지 |
| 장면 요약 (D) | VLM은 D가 채움(#38) | 프롬프트, 스키마, 주장 검사, 채점 |
| 타임스탬프 고르기, 합성 안개 (C, 도구만) | YOLOv8n 박스, YOLOv8n-seg 마스크 | 가까운 차량 규칙, Koschmieder 안개 모델, A의 Gaussian으로 산란 흐림, 센서 노이즈 |

OpenCV는 이미지·영상 입출력에만 씁니다. `src/`에 OpenCV 처리 함수나 `_stub` 함수가 남아 있으면
`python tools/check_forbidden.py src/`가 실패합니다.

## 테스트

```bash
python -X utf8 -m pytest -q
python tools/check_forbidden.py src/
```

테스트는 합성 프레임, 가짜 라벨, 모델 대역을 써서 데이터나 모델 다운로드가 필요 없습니다. 한국어 Windows에서는
`-X utf8`이 필요합니다. B의 패키지 테스트 두 개가 기본 인코딩으로 텍스트를 읽기 때문입니다.

## 데이터 출처와 라이선스

| 데이터 | 쓰는 곳 | 조건 |
| --- | --- | --- |
| 직접 찍은 블랙박스 클립 | 안개 클립(합성 안개)과 OCR | 팀원이 직접 촬영 |
| AI Hub 71588(야간 자동차 전용도로), 630(다양한 기상 상황 주행: 비), 71570(주간 자동차 전용도로), 71930(71570 업사이클링: 터널 이미지) | 보정, 차량 검출(차량 다각형), 장면 요약. 번호판이 가려져 있어 OCR에는 안 씀 | AI Hub 이용 조건: 승인받은 팀원만, 재배포·팀 밖 업로드 금지 |
| GLARE(역광 클립) | 역광 보정과 요약 | CC BY 4.0. N. Gray et al., "GLARE: A Dataset for Traffic Sign Detection in Sun Glare," IEEE T-ITS 24(11):12323–12330, 2023, doi:10.1109/TITS.2023.3294411 |
| BDD100K(야간·해 질 녘 이미지, 쓸 경우) | 야간·해 질 녘 OCR | F. Yu et al., "BDD100K: A Diverse Driving Dataset for Heterogeneous Multitask Learning," CVPR 2020. BDD100K 라이선스 조건 |

모델 라이선스는 위 표와 [docs/model_selection.ko.md](docs/model_selection.ko.md)에 있습니다.
