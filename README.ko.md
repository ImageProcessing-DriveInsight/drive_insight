# DriveInsight

디지털 영상처리 팀 프로젝트 02 · 16조 Black Box · [English](README.md)

DriveInsight는 악조건(야간, 비, 안개, 역광, 터널)에서 찍힌 블랙박스 프레임을 보정하고, 그 보정이 사람 눈에만
좋아 보이는지 기계가 읽는 데도 도움이 되는지 확인합니다. 모든 프레임을 세 조건으로 처리하고 같은 기준으로 채점합니다.

| 조건 | 뜻 |
| --- | --- |
| `orig` | 원본 프레임 |
| `fixed` | 고정 보정: 모든 프레임에 같은 파라미터 (h1gyeon9) |
| `adaptive` | 적응형 보정: 화질을 재고 프레임마다 파라미터를 고름 (leojuho) |

세 조건은 번호판 인식과 차량 검출(sangwon5579), 시각 언어 모델(VLM)의 장면 요약(callmeaein)으로 비교합니다. 영상처리 연산은 팀이
NumPy로 직접 구현했고, 사전학습 모델은 차량 검출, 글자 인식, 장면 요약에만 씁니다
([사전학습 모델과 직접 구현](#사전학습-모델과-직접-구현) 참고).

```text
클립 / 이미지 시퀀스 ──► 원본 PNG 프레임 (leojuho) ──┬─► orig
                                                      ├─► 고정 보정 (h1gyeon9) ──────────────► fixed
                                                      └─► 화질 측정 → 규칙 → 연산 (leojuho) ─► adaptive
조건마다 ──► 차량 → 번호판 후보 → 크롭 전처리 → OCR → 상태 판정 (sangwon5579)
         ──► 장면 요약 (callmeaein)
모든 조건 ──► 평가, 집계, 비교, 환경 조건별 결과 (sangwon5579) ──► 리뷰 패키지 (leojuho)
```

## 팀과 모듈

| 팀원 | 모듈 | 맡은 일 |
| --- | --- | --- |
| [h1gyeon9](https://github.com/h1gyeon9) | `src/dip/` | 색 공간 변환, 히스토그램 평활화, 감마, Gaussian·Median 필터, Unsharp masking(NumPy), `apply_ops`, `fixed_enhance`, 고정 보정 일괄 처리, 야간 데이터 점검과 프레임 목록 |
| [leojuho](https://github.com/leojuho) | `src/io/`, `src/adaptive/`, `src/package/` | 프레임·영상 입출력, 화질 측정, 규칙 기반 파라미터, `adaptive_enhance`, 평가 목록과 라벨, 리뷰 패키지, 민감도 실험 |
| [sangwon5579](https://github.com/sangwon5579) | `src/plate/`, `src/eval/` | 차량·번호판 검출, 크롭 전처리, OCR과 상태 판정, OCR 평가, 집계, 비교, 차량 검출률, 환경 조건별 결과 |
| [callmeaein](https://github.com/callmeaein) | `src/common/`, `src/pipeline/`, `src/vlm/` | 실험 실행기와 시간 측정, VLM 요약과 채점, `main.py`, 프로젝트 파일, 제출(#38) |

인터페이스, 폴더, 일정은 [팀 계획](docs/plan/team_plan.ko.md)(팀원을 위 순서대로 A, B, C, D로 부름), 기능과 진행 상태는 [기능 명세](docs/plan/feature_spec.ko.md),
전체 문서 목록은 [docs/](docs/README.ko.md)에 있습니다.

## 설치

Windows의 Python 3.12(팀원 PC)에서 씁니다. 모든 명령은 저장소 루트에서 실행합니다.

```bat
python -m venv .venv
.venv\Scripts\activate
python -m pip install -r requirements.txt
```

`requirements.txt`에는 `requirements-plate.txt`, `requirements-b.txt`, `requirements-dip.txt`의 버전이 모두 들어 있고,
VLM 클라이언트용 `requests`가 더해져 있습니다.

**Visual Studio:** `DriveInsight.sln`을 엽니다. 위에서 만든 `.venv`를 쓰고 `main.py`로 시작하므로 F5로 전체 실험이
돌아갑니다. 인자는 프로젝트 → 속성 → 디버그 → 스크립트 인수에 넣습니다.

**VLM(장면 요약):** [Ollama](https://ollama.com) 0.12.7 이상을 설치하고 모델을 한 번 받습니다(약 3.3 GB). `vlm` 단계가
도는 동안 Ollama를 켜 둡니다.

```bat
ollama pull qwen3-vl:4b-instruct
```

모델이 PC에서 직접 돌기 때문에 API 키가 필요 없고 포함되어 있지도 않습니다. 다른 Ollama 주소는 환경 변수
`OLLAMA_URL`로 바꿉니다(기본값 `http://localhost:11434`). Ollama가 없으면 `--offline`을 씁니다([실행](#실행) 참고).

- 새 가상환경 하나에 설치합니다. `requirements-video-io.txt`는 같이 설치하지 않습니다. `opencv-python-headless`를
  고정하는데, OpenCV 배포판이 섞이면 `cv2`가 깨질 수 있습니다.
- `requirements-plate.txt`의 `pandas`, `chardet` 버전은 최신 빌드가 막힌 팀원 PC 한 대 때문에 고정한 것입니다.
- 모델 가중치는 처음 실행할 때 받아집니다. YOLO는 `weights/`(git 제외), PaddleOCR은 `~/.paddlex/official_models/`입니다.
- leojuho의 문서는 Windows에서 `python` 대신 `py`를 씁니다. 둘 다 됩니다.
- PaddleOCR이 `opencv-python` 옆에 `opencv-contrib-python`을 설치하므로 `cv2`는 contrib 빌드에서 옵니다.
  정상이며, 이 상태로 모든 테스트가 통과합니다.

## 데이터

실제 클립, 프레임, 라벨, 결과는 **git에 없습니다.** 실제 번호판이 보이거나 글자가 들어 있고, AI Hub 데이터는 승인받은
팀원만 쓸 수 있기 때문입니다. 팀원끼리 직접 주고받습니다.

```text
data/clips/                        원본 영상 (수정하지 않음)
data/eval_set.csv                  clip, timestamp_ms, condition, source, license (팀원 목록을 leojuho가 합침)
data/frames/orig/ fixed/ adaptive/ 세 조건 폴더에 같은 <clip>_<ms>.png
data/frames/clear/                 합성 안개를 만든 맑은 프레임 (sangwon5579의 안개 클립만)
data/annotations/scenes.json       프레임별 라벨: 차량, 번호판, 사건 (leojuho의 라벨 도구)
data/annotations/aihub_vehicles.json  차량 검출률용으로 바꾼 AI Hub 차량 라벨 (sangwon5579)
data/annotations/envs.csv          이미지 프레임(AI Hub 등)마다 조건 (sangwon5579)
data/labels/plates.json            OCR 평가용 번호판 라벨 (scenes.json에서 내보냄)
data/plate_countries.json          미국 번호판 프레임 (있을 때만)
results/                           출력, 아래 참고
package/<clip>/                    리뷰 패키지
```

프레임은 항상 `uint8` BGR, `(H, W, 3)` 배열입니다. 세 조건 폴더의 파일 이름이 똑같아서, 모든 조건을 같은 프레임으로 채점합니다.

## 실행

### 한 번에 실행

```bat
python main.py
```

`main.py`는 세 조건을 `enhance`, `ocr`, `vlm` 단계로 돌리고 `results/summary.csv`를 만듭니다. 세 조건 폴더의 프레임
이름이 다르면 먼저 오류로 멈춥니다. 이미 있는 결과는 덮어쓰지 않습니다. OCR 결과, VLM 파일, 채운 시트, 패키지는 그대로
두고 없는 것만 만듭니다.

| 명령 | 하는 일 |
| --- | --- |
| `python main.py --condition fixed --steps vlm` | 한 조건, 한 단계 (`--condition`을 반복하면 여러 조건) |
| `python main.py --clip <클립> --clip <클립>` | 이 클립들만 VLM 단계 실행 |
| `python main.py --offline` | VLM을 호출하지 않음. `results/vlm/<cond>/<clip>.json`을 다시 쓰고, 저장된 파일이 없는 클립을 알려 줌 |
| `python main.py --no-run --make-sheets` | 조건 이름을 가린 사실 확인 시트 `results/vlm/verify/s001.csv`, … 대응표는 `results/vlm/verify_key.csv` |
| `python main.py --no-run --score` | 다 채운 시트(`label` = `correct`, `unsupported`, `uncheckable`)를 채점해 `results/vlm/score.csv`에 저장 |
| `python main.py --no-run --package <클립>` | 리뷰 패키지 `package/<클립>/summary.html` |

보정 단계는 `data/frames/fixed/`, `data/frames/adaptive/`의 프레임(아래 4, 5단계)을 그대로 씁니다. 다시 만들지 않습니다.
사실 확인 담당에게는 대응표 없이 `verify/` 폴더만 줍니다.

### 담당별 단계

순서대로 진행합니다. 각 담당이 자기 단계를 돌리고 결과 파일을 넘깁니다.

| 단계 | 담당 | 명령 | 출력 |
| --- | --- | --- | --- |
| 1. 팀원 목록 합치기 | leojuho | `python -m tools.prepare_data member_a.csv member_b.csv member_c.csv member_d.csv` | `data/eval_set.csv` |
| 2. 원본 프레임 추출 | leojuho | `python -m tools.b_cli extract` | `data/frames/orig/` |
| 3. 라벨 | leojuho, 각 담당 | `python -m tools.b_labels init`, `scenes.json` 채우기(초안: `python tools/label_draft.py draft`), `python -m tools.b_labels export --require-review` | `data/annotations/scenes.json`, `data/labels/plates.json` |
| 3a. 이미지 프레임 목록 | sangwon5579 | `python tools/eval_lists.py --list <팀원 목록> <조건> ...` | `data/annotations/envs.csv`, `eval_names.csv` |
| 3b. AI Hub 차량 라벨 | sangwon5579 | `python tools/aihub_vehicles.py <라벨 폴더> --names data/annotations/eval_names.csv` | `data/annotations/aihub_vehicles.json` |
| 4. 고정 보정 | h1gyeon9 | `python -m src.dip.batch` | `data/frames/fixed/`, `results/params/fixed.json` |
| 5. 적응형 보정 | leojuho | `python -m tools.b_cli frames --apply-ops src.dip.fixed:apply_ops` | `data/frames/adaptive/`, `results/params/adaptive.json` |
| 6. 번호판, 차량, 평가, 비교 | sangwon5579 | `python tools/plate_report.py --scenes data/annotations/scenes.json data/annotations/aihub_vehicles.json` | `results/` |
| 7. 환경 조건별 결과 | sangwon5579 | `python tools/env_report.py --scenes data/annotations/scenes.json data/annotations/aihub_vehicles.json --envs data/annotations/envs.csv` | `results/by_env/` |
| 8. 장면 요약, 사실 확인, 채점 | callmeaein | `python main.py --steps vlm`, 그다음 `--no-run --make-sheets`, 시트 채우기, `--no-run --score` | `results/vlm/<cond>/<clip>.json`, `results/<cond>/timing.csv`, `results/<cond>/config_snapshot.json`, `results/vlm/score.csv` |
| 9. 리뷰 패키지 | leojuho | `python -m tools.b_cli package <clip>` | `package/<clip>/summary.html` |

그 밖의 도구:

```bash
python -m tools.b_cli video data/clips/<clip>.mp4 --mode adaptive   # 보정 영상 (--mode fixed도 가능)
python -m tools.sensitivity --scale 0.8 1.2 --labels data/labels    # leojuho: 적응형 임계값 배율 실험
python -m tools.audit_night_data --decode-images --output data/annotations/<report>.json   # h1gyeon9: 야간 데이터 점검
python -m tools.select_night_frames                                 # h1gyeon9: 공통 기준으로 야간 프레임 목록
python -m tools.verify_fixed_batch snapshot --snapshot data/annotations/fixed_orig_snapshot.json   # h1gyeon9: 일괄 처리 전
python -m tools.verify_fixed_batch verify --snapshot data/annotations/fixed_orig_snapshot.json     # h1gyeon9: 일괄 처리 후
python tools/synth_fog.py make <맑은 클립> <출력>                   # sangwon5579: 맑은 날 영상으로 합성 안개
python tools/pick_frames.py scan <클립>                             # sangwon5579: 차량 크기로 타임스탬프 고르기
python tools/compare_images.py --hide 2                             # sangwon5579: 발표용 이미지, 번호판 뒤 두 글자 가림
```

## 출력

| 파일 | 내용 |
| --- | --- |
| `results/ocr/<cond>.csv` | 번호판마다 한 행: 박스, 크롭, 글자, 신뢰도, 상태(`readable`, `uncertain`, `unreadable`), OCR 시간 |
| `results/ocr/ocr_summary.csv` | 검출률, 완전 일치율, 문자 정확도, 틀렸는데 readable로 낸 수, 못 읽는 번호판을 readable로 낸 수 |
| `results/summary.csv` | 조건별 OCR 지표, VLM 점수, 단계별 시간 |
| `results/vlm/<cond>/<clip>.json` | 클립별 VLM 장면 요약: `vehicles`, `events`(order, content, frame), `visibility_notes`, `uncertain` |
| `results/vlm/score.csv` | 조건·클립마다 한 행: 사실 수, 맞힌 사실, 확인 가능·근거 없음·확인 불가 주장 수, 장면 정확도, 환각률 |
| `results/<cond>/timing.csv` | 프레임·단계별 시간(`enhance_ms`, `ocr_ms`, `vlm_ms`, `total_ms`) |
| `results/<cond>/config_snapshot.json` | 마지막 실행의 단계, 모델 버전, VLM 프롬프트의 SHA-256 해시 |
| `results/compare.csv`, `worse_cases.csv` | `orig` → `fixed`, `fixed` → `adaptive`에서 좋아지거나 나빠진 프레임과 부호 검정, 나빠진 번호판 |
| `results/vehicles.csv`, `vehicle_compare.csv` | 차량 크기별 검출률, 조건 사이에 새로 찾거나 놓친 차량 |
| `results/by_env/` | 같은 표를 환경 조건(안개, 야간, 비, 터널, 역광)별로 |
| `results/figures/` | 발표용 번호판·차량 이미지 |
| `package/<clip>/summary.html` | 리뷰 패키지: 대표 프레임, OCR, VLM, 파일 목록 |

`results/ocr/`, `worse_cases.csv`, `results/vehicles/`, `results/figures/`, `results/by_env/`에는 번호판 글자나 실제 번호판
이미지가 들어가므로 git이 무시합니다.

## 지금까지의 결과

안개, 야간, 비, 역광 150장을 원본·고정·적응형 보정으로 돌린 결과입니다([자세히](docs/eval_results.ko.md)):

- 안개, 직접 찍은 블랙박스 클립에 합성 안개(클립 11개, 프레임 48장, 읽을 수 있는 라벨 번호판 13개, 라벨 차량 222대,
  [자세히](docs/dashcam_results.ko.md)):
  - 문자 정확도는 안개 프레임 0.81, 고정 보정 뒤 0.70, 적응형 보정 뒤 0.81입니다. 고정 보정은 5프레임을 나쁘게 했고
    좋아진 프레임은 없습니다(부호 검정 p 0.0625, 방향일 뿐 증명은 아님).
  - 이 프레임들에서는 적응형 규칙이 하나도 발동하지 않아 적응형이 원본과 같습니다.
  - 차량 검출률은 안개 0.54(폭 100 px 미만 차량은 0.12), 고정 보정 뒤 0.51입니다.
- 야간, AI Hub(프레임 30장, 그중 24장에 라벨 차량 114대): 차량 검출률은 원본과 고정 보정 0.25, 적응형 보정 0.22입니다.
  적응형 규칙은 모든 프레임에서 발동했습니다.
- 비, AI Hub(프레임 30장, 라벨 차량 82대): 차량 검출률은 원본 0.10, 고정 보정 뒤 0.11, 적응형 보정 뒤 0.10입니다.
- 역광, GLARE(클립 7개, 프레임 42장, 미국 번호판, 라벨 없음): 어느 조건에서도 번호판을 읽지 못했고, `readable`로 나온
  결과는 블랙박스 날짜·시각 글자뿐이었습니다. 적응형 규칙은 5장, 모두 한 클립에서만 발동했습니다.
- 야간과 비에서 보정이 바꾸는 차량은 1–4대이고, 의미 있는 차이는 없습니다. AI Hub에는 번호판 문자가 없어 번호판 지표는
  안개만 있고, 야간과 비에서는 번호판을 하나도 읽지 못했습니다.
- VLM 장면 요약(`qwen3-vl:4b-instruct`)의 환각률은 원본 / 고정 / 적응형에서 안개 3.8 / 4.0 / 3.8 %(조건마다 같은 주장
  하나), 야간 33 / 33 / 50 %, 비 17 / 17 / 17 %(확인할 수 있는 주장 각 6개), 역광 20 / 21 / 20 %(조건마다 같은 주장
  4개)라 의미 있는 차이는 없습니다. 비에서는 모델이 장면을 안개로 자주 봅니다.

터널은 마감 전까지 프레임이 없어 뺐습니다.

## 사전학습 모델과 직접 구현

| 부분 | 사전학습 | 직접 구현 |
| --- | --- | --- |
| 영상 보정 (h1gyeon9) | – | 색 공간 변환, 히스토그램 평활화, 감마, Gaussian·Median 필터, Unsharp masking(NumPy), 고정 파라미터 |
| 적응형 보정 (leojuho) | – | 밝기·대비·노이즈·선명도 측정, 규칙 기반 파라미터 선택 |
| 프레임·영상 입출력 (leojuho) | OpenCV(읽기·쓰기만) | 타임스탬프 추출, 출력 검사 |
| 차량 검출 (sangwon5579) | YOLOv8n, Ultralytics 8.4.208, COCO 가중치, AGPL-3.0 | 클래스·신뢰도 필터, 촬영 차량 필터(대시보드와 반사), 차량당 박스 하나 |
| 번호판 검출 (sangwon5579) | – | 후보 탐색: 수직 에지, 밝기, 적분 영상 기반 주변 대비, 박스 확장, NMS, 차량당 후보 4개 |
| 크롭 전처리 (sangwon5579) | – | 그레이 변환, 쌍선형 리사이즈, 대비 스트레칭, 극성 맞춤, 기울기 보정, Otsu |
| OCR (sangwon5579) | PaddleOCR 3.7.0, `korean` PP-OCRv5, Apache-2.0 | 줄 잇기, O/I 보정, 정규화. 미국 번호판은 번호 줄만 |
| 상태 판정 (sangwon5579) | – | 한국·미국 번호판 형식에 따른 `readable` / `uncertain` / `unreadable` 규칙 |
| 평가 (sangwon5579) | – | 짝짓기, 지표, 집계, 비교, 부호 검정, 환경 조건별 결과, 발표용 이미지 |
| 장면 요약 (callmeaein) | Qwen3-VL 4B Instruct(`qwen3-vl:4b-instruct`), 로컬 Ollama, temperature 0, Apache-2.0 | 프롬프트, JSON 스키마 검사와 1회 재시도, 클립 단위 병합, 캐시, 조건을 가린 주장 시트, 채점 |
| 타임스탬프 고르기, 합성 안개 (sangwon5579, 도구만) | YOLOv8n 박스, YOLOv8n-seg 마스크 | 가까운 차량 규칙, Koschmieder 안개 모델, h1gyeon9의 Gaussian으로 산란 흐림, 센서 노이즈 |

OpenCV는 이미지·영상 입출력에만 씁니다. `src/`에 OpenCV 처리 함수나 `_stub` 함수가 남아 있으면
`python tools/check_forbidden.py src/`가 실패합니다.

## 테스트

```bash
python -X utf8 -m pytest -q
python tools/check_forbidden.py src/
```

새 환경에서 736개 통과, 3개 건너뜀(YOLO 가중치를 아직 받지 않음, Windows가 아닌 PC에 한글·Arial 글꼴 없음).

테스트는 합성 프레임, 가짜 라벨, 모델 대역을 써서 데이터나 모델 다운로드가 필요 없습니다. 한국어 Windows에서는
`-X utf8`이 필요합니다. leojuho의 패키지 테스트 두 개가 기본 인코딩으로 텍스트를 읽기 때문입니다.

## 데이터 출처와 라이선스

| 데이터 | 쓰는 곳 | 조건 |
| --- | --- | --- |
| 직접 찍은 블랙박스 클립 | 안개 클립(합성 안개)과 OCR | 팀원이 직접 촬영 |
| AI Hub 71588(야간 자동차 전용도로), 630(다양한 기상 상황 주행: 비), 71570(주간 자동차 전용도로), 71930(71570 업사이클링: 터널 이미지) | 보정, 차량 검출(차량 다각형), 장면 요약. 번호판이 가려져 있어 OCR에는 안 씀 | AI Hub 이용 조건: 승인받은 팀원만, 재배포·팀 밖 업로드 금지 |
| GLARE(역광 클립) | 역광 보정과 요약 | CC BY 4.0. N. Gray et al., "GLARE: A Dataset for Traffic Sign Detection in Sun Glare," IEEE T-ITS 24(11):12323–12330, 2023, doi:10.1109/TITS.2023.3294411 |
| BDD100K(야간·해 질 녘 이미지, 쓸 경우) | 야간·해 질 녘 OCR | F. Yu et al., "BDD100K: A Diverse Driving Dataset for Heterogeneous Multitask Learning," CVPR 2020. BDD100K 라이선스 조건 |

모델 라이선스는 위 표와 [docs/model_selection.ko.md](docs/model_selection.ko.md)에 있습니다.
