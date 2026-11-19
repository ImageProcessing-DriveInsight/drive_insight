# 팀원 C 작업 가이드 · 번호판 인식 + 평가

DriveInsight · Team 16 Black Box · 초판 2026-11-08 · **최신화 2026-11-16**

[English](member_c_guide.md) · [역할 분담 및 WBS](team_plan.ko.md) · [기능 명세](feature_spec.ko.md)

C는 차량·번호판을 찾아 읽고(`src/plate/`), 세 조건의 결과를 모아 비교표를 만듭니다(`src/eval/`).

## 현재 상태 (11/16)

| | |
| --- | --- |
| **머지 완료** | C-01\~C-11: #2, #4, #8, #10, #12, #14, #16, #24, #26 |
| **바로 넘길 수 있음** | `detect_plates`(D), 프레임이 오면 `run_ocr`로 `orig.csv` 생성(B, D), `eval_ocr`(B), 결과가 모이면 `summary.csv`와 `compare.csv`(전원) |
| **기다리는 것** | 원본 프레임과 라벨 스키마(B), 고정 보정 프레임(A), 적응형 보정 프레임(B), VLM 점수와 `timing.csv`(D) |
| **다음 할 일** | 스키마가 오면 라벨링. 실제 프레임이 오면 OCR → 평가 → 집계 → 비교 실행 |

## 날짜별 할 일

개발과 데이터 작업을 한 줄로 합쳤습니다. 괄호 안은 기능 명세의 ID입니다. 데이터 작업은 저장소로 추적되지 않으니 직접 체크하세요.

**주말 (11/7–11/8)**

- [ ] 안개·눈 클립 2–3개 업로드, 출처·라이선스·타임스탬프 3–5개 기록. 절반 이상은 번호판이 보이는 장면 (ALL-01) — 번호판이 읽히는 공개 안개 영상이 없어 맑은 날 영상에 `tools/synth_fog.py`로 합성 안개(#61), 눈은 합성 안 함
- [x] 함수 껍데기 커밋: `detect_plates(frame) -> []`, `eval_ocr`, `aggregate` (#2)
- [x] 차량 검출기·번호판 검출기·OCR 설치, 한국 번호판 사진 10장 테스트, 선정 메모 작성 (C-01, #4, #8)

**1주차 (11/9–11/16): 원본 프레임으로 인식 완성**

- [x] 11/9–11/10 차량 검출 `detect_vehicles` (C-02, #10)
- [ ] 11/9–11/14 내 클립 정답 라벨링, B의 스키마·예시 따름 (ALL-02) — 스키마 생김, `tools/label_draft.py`로 초안과 확인 이미지(#54)
- [ ] 11/10 통합 점검 1: 실행기가 내 껍데기 함수를 불러 끝까지 도는지 확인
- [x] 11/10–11/12 번호판 후보 검출 `detect_plate_candidates` (C-03, #10)
- [x] 11/12–11/14 크롭 전처리 직접 구현 `preprocess_plate` (C-04, #12)
- [x] 11/14–11/16 OCR 연결과 상태 판정 `recognize`, `judge` (C-05, C-06, #12)
- [ ] 11/15–11/16 D의 라벨 교차 검수 (ALL-03) — 라벨이 없어 대기
- [x] 11/16 `detect_plates` 통합과 `run_ocr` (C-07, C-08, #14)
- [ ] 11/16 `results/ocr/orig.csv` 생성 후 D·B에게 공유 — 원본 프레임 대기

**2주차 (11/17–11/24): 평가와 집계**

- [ ] 11/17 통합 점검 2: 고정 보정 프레임에 OCR이 붙는지, 라벨 불일치 확정 (안건은 아래)
- [x] 11/17–11/19 OCR 평가 `eval_ocr` (C-09). B의 민감도 스크립트가 부를 수 있는 함수로 (#16)
- [ ] 11/19–11/20 고정·적응형 프레임 실행, `fixed.csv`, `adaptive.csv` (C-08)
- [ ] 11/20–11/22 D의 클립 VLM 사실 검증 (ALL-04)
- [x] 가짜 CSV로 전체 집계 `aggregate`, 조건 간 비교표 `compare` 완성 (C-10, C-11, #24, #26)
- [ ] 11/22–11/24 VLM 최종 점수가 나온 뒤 실제 결과로 집계와 비교 다시 실행
- [ ] 11/24 통합 점검 3: 세 조건 결과 확정

**마지막 주 (11/25–11/28)**

- [ ] 버그 수정, 아래 "사전학습 vs 직접 구현" 표를 README용으로 D에게 전달
- [ ] 아래 "제출 전 최종 점검" 항목 전부 확인

## 받는 것과 주는 것

| 구분 | 무엇 | 누구 | 예정일 | 그 전까지 대역 | 11/16 상태 |
| --- | --- | --- | --- | --- | --- |
| 받음 | 원본 프레임 `frames/orig/` | B | 11/8 | 인터넷 번호판 사진, 내 클립에서 직접 뽑은 몇 장 | 저장소에 없음. 인터넷 사진 10장으로 개발 |
| 받음 | 라벨 스키마와 예시 3장 | B | 11/8 | – | 저장소에 없음. 번호판 형식 제안([docs/ocr_evaluation.ko.md](../ocr_evaluation.ko.md), #16) |
| 받음 | 확정된 정답 라벨 `data/labels/` | 전원 | 11/16 | D의 가짜 라벨(`tests/fixtures/`) | 저장소에 없음. 테스트는 자체 가짜 라벨 사용 |
| 받음 | 고정 보정 프레임 `frames/fixed/` | A | 11/15 | 원본 프레임 | 저장소에 없음 |
| 받음 | 적응형 보정 프레임 `frames/adaptive/` | B | 11/18 | 고정 보정 프레임 | 11/18 예정 |
| 받음 | VLM 점수 `results/vlm/score.csv`, `timing.csv` | D | 11/21 (최종값 11/22 이후) | 가짜 CSV | 11/21 예정. 형식은 [docs/aggregation.ko.md](../aggregation.ko.md)에 제안 |
| 줌 | `detect_plates` 함수 | D(실행기) | 11/16 | 빈 리스트를 돌려주는 껍데기(11/8) | 머지 완료(#14) |
| 줌 | OCR 결과와 크롭 `results/ocr/` | B(패키지), D | 11/16 | – | 프레임이 오면 `python -m src.plate.run orig` |
| 줌 | `eval_ocr` 함수 | B(민감도 실험) | 11/19 | – | 머지 완료(#16) |
| 줌 | `summary.csv`, 조건 간 비교표, 악화 사례 목록 | 전원(보고서·발표) | 11/24 | – | 코드 머지 완료(#24, #26). 수치는 실제 결과가 오면 |
| 줌 | README용 "사전학습 vs 직접 구현" 표 | D | 11/25 | – | 아래에 준비됨 |

`detect_plates`는 항상 `{"bbox", "crop_path", "text", "conf", "status"}` 딕셔너리의 리스트를 돌려주고, 번호판이 없으면 빈 리스트를 돌려줍니다. `cond`, `frame_id`는 선택 인자로 추가했습니다(11/17 확정).

## 실행 방법

```bash
pip install -r requirements-plate.txt
python -m pytest tests/
python tools/model_check.py <samples>          # C-01: 샘플로 검출기·OCR 비교
python tools/preprocess_check.py <samples>     # C-04: 전처리 유무별 OCR 비교
python -m src.plate.run orig                   # C-08: data/frames/orig → results/ocr/orig.csv
python -m src.eval.ocr --labels data/labels    # C-09: results/ocr/<cond>.csv → ocr_summary.csv
python -m src.eval.aggregate                   # C-10: ocr_summary.csv, vlm/score.csv, timing.csv → summary.csv
python -m src.eval.compare                     # C-11: compare.csv, worse_cases.csv (라벨: data/labels)
python tools/label_draft.py draft              # ALL-02: scenes.json에 박스 초안 + 확인 이미지
python tools/synth_fog.py make <clear> <out>   # ALL-01: 맑은 날 영상으로 안개 클립 생성
python tools/compare_images.py                 # C-11: 발표용 번호판·프레임 이미지 (--hide 2)
```

`<samples>` 폴더에는 `full/`, `crops/`, `labels.csv`(`file,text`)가 있습니다. 샘플 사진은 저장소 밖에 둡니다.

## 기능별 구현 내용

검출과 OCR은 사전학습 모델을 쓰고, 전처리·후보 탐색·판정·평가는 직접 구현했습니다. 과제 FAQ상 사전학습 모델을 쓰면 "기존 대비 기여"를 설명해야 하므로, 직접 구현한 부분이 C의 기여가 됩니다.

### C-01 모델 선정 — [docs/model_selection.ko.md](../model_selection.ko.md)

인터넷의 한국 번호판 사진 10장(주간 5장, 야간·먼 거리 5장), OCR은 손으로 자른 번호판으로 비교했습니다.

| 단계 | 선택 | 결과 |
| --- | --- | --- |
| 차량 검출 | YOLOv8n (Ultralytics 8.4.208, COCO, AGPL-3.0) | 10/10장에서 차량 검출, CPU에서 장당 19ms |
| 번호판 검출 | 사전학습 번호판 검출기는 쓰지 않음(출처가 불분명한 공개 가중치는 코드를 실행할 수 있는 pickle 파일) | 후보 탐색 직접 구현(C-03) |
| OCR | PaddleOCR 3.7.0 `korean` (PP-OCRv5, Apache-2.0) | 정확히 읽음 7/10, EasyOCR은 3/10 |

OCR의 주된 오류는 가운데 한글을 숫자로 읽거나 빠뜨리는 것이었고, 번호판 형식 검사로 모두 걸러졌습니다.

### C-02, C-03 검출 — `src/plate/detect.py`, `src/plate/candidates.py`

- `detect_vehicles`: car, truck, bus, motorcycle, `conf` ≥ 0.4, bbox `(x, y, w, h)`, 큰 박스부터.
- `detect_plate_candidates`(직접 구현): 차량 박스 위쪽 35% 아래를 탐색합니다. 모든 창의 수직 에지 밀도와 밝기에서 주변 띠의 값을 뺀 점수를 적분 영상으로 계산합니다. 폭 8가지 × 가로세로 비 3가지(2:1, 3:1, 4.5:1)를 시도하고, 최고 창을 에지가 이어지는 범위까지 넓힌 뒤 NMS로 차량당 상위 4개를 남깁니다(#71 전에는 3개).
- 실제 사진: 10/10장에서 상위 3개 안, 8/10장에서 1위. 밝기 항 덕분에 촘촘한 그릴 옆의 번호판을 찾았고, 박스 확장으로 판 가운데만 잡던 문제를 해결했습니다.

### C-04\~C-06 인식 — [docs/plate_recognition.ko.md](../plate_recognition.ko.md)

- `preprocess_plate`(직접 구현): 그레이 → 높이 64px 쌍선형 리사이즈 → 대비 스트레칭 → 글자를 어둡게 맞춤 → 기울기 보정 ±10°(행 투영이 가장 몰리는 각도) → Otsu(선택). OpenCV와 비교하면 리사이즈 차이 ≤ 1, Otsu는 완전히 같습니다(테스트에서만 비교).
- 전처리 비교: 손 크롭에서는 원본·그레이·기울기 보정 모두 7/10이었지만 Otsu는 2/10이었습니다. 자동 후보 크롭에서는 그레이+스트레칭+기울기 보정이 원본과 같은 수(7/10)를 읽으면서, 대상이 아닌 크롭을 자신 있게 읽는 경우가 줄었습니다(2 → 0). 그래서 기본값은 이진화 없음입니다.
- `recognize`: PaddleOCR, 위→아래로 줄을 잇고, `O`→`0`, `I`/`l`→`1`, 숫자·한글만 남기며, conf는 박스 점수 중 최솟값입니다.
- `judge`(직접 구현): readable / uncertain / unreadable. 한 자리만 고치면 형식이 맞으면 그 자리를 `?`로 표시하고, 어디를 고칠지 애매하면 unreadable, conf < 0.5는 항상 unreadable입니다. status만이 아니라 `(status, text)`를 돌려줍니다.

### C-07, C-08 통합 — `src/plate/detect.py`, `src/plate/run.py`

- 차량당 결과 하나: 후보를 순서대로 읽다가 readable이 나오면 멈추고, 가장 좋은 결과(상태, 그다음 conf)를 남깁니다.
- 크롭은 `results/ocr/crops/<cond>/<frame_id>_<n>.png`에 저장합니다(git 제외).
- `results/ocr/<cond>.csv` 열: `frame, plate, x, y, w, h, crop_path, text, conf, status, ocr_ms`. 번호판이 없는 프레임도 한 줄을 남겨 세 조건의 프레임 목록이 같게 합니다.
- 실제 사진으로 끝까지 실행: readable·정확 7/10, uncertain 3/10, 틀린 readable 0건, 장당 약 1.6초.
  10장 중 3장은 자동차 회사 광고용 번호판(케, 차)이라, 번호판 글자 검사(#34) 이후에는 uncertain이고 실제 번호판 7장 중 5장이 readable·정확입니다.

### C-09 평가 — `src/eval/ocr.py`, [docs/ocr_evaluation.ko.md](../ocr_evaluation.ko.md)

- 두 박스가 작은 박스의 절반 이상 겹치면 IoU 큰 순서로 1:1로 짝짓고, 읽을 수 있는 표준 라벨 기준으로 검출률·완전일치율·문자 정확도를 계산합니다. 표준이 아닌 번호판(광고용, 군용)은 따로 셉니다(#52).
- unreadable 라벨은 따로 세고 과신 건수(`overconfident`)를 보고합니다. `readable_wrong`, `missing_frames`도 있습니다.
- `frame_char_accuracy`는 C-11에서 쓸 프레임별 점수입니다.
- 손으로 계산한 3건이 `tests/test_ocr_eval.py`에 있습니다.

### C-10 집계 — `src/eval/aggregate.py`, [docs/aggregation.ko.md](../aggregation.ko.md)

- `summary.csv`는 조건마다 한 행: 번호판 수, 검출률, 완전일치율, 문자 정확도, 과신 건수, `readable_wrong`, VLM 장면 정확도, 환각률, 확인 불가 주장 수, 단계별 프레임당 평균 ms.
- `score.csv`에 개수 열이 있으면 클립을 합쳐 계산하고, 없으면 행별 비율을 평균합니다. 파일이 없으면 해당 열만 비워 두므로 결과가 다 모이기 전에도 돌아갑니다.
- 손으로 계산한 경우가 `tests/test_aggregate.py`에 있습니다.

### C-11 비교 — `src/eval/compare.py`, [docs/comparison.ko.md](../comparison.ko.md)

- `orig` → `fixed`, `fixed` → `adaptive` 두 쌍입니다. 프레임의 평균 문자 정확도가 오르면 개선, 내리면 악화, 같으면 변화 없음입니다. 읽을 수 있는 라벨이 없거나 CSV에 없는 프레임은 따로 세므로, 세 수의 합은 비교한 프레임 수와 같습니다.
- `compare.csv`에는 `summary.csv`에서 계산한 지표 변화량도 들어갑니다. `worse_cases.csv`는 나빠진 번호판마다 두 조건의 크롭 경로를 적고, 많이 떨어진 순서로 정렬합니다. 계획서가 "보정이 항상 좋다고 가정하지 않는다"고 약속했기 때문에, 발표에서 가장 설득력 있는 자료가 됩니다.
- 손으로 계산한 경우가 `tests/test_compare.py`에 있습니다.

## 사전학습 vs 직접 구현 (README용)

| 부분 | 사전학습 | 직접 구현 |
| --- | --- | --- |
| 차량 검출 | YOLOv8n, Ultralytics 8.4.208, COCO 가중치, AGPL-3.0 | 클래스·신뢰도 필터, 박스 변환과 정렬 |
| 번호판 검출 | – | 후보 탐색: 수직 에지, 밝기, 적분 영상 기반 주변 대비 점수, 박스 확장, NMS |
| 크롭 전처리 | – | 그레이 변환, 쌍선형 리사이즈, 대비 스트레칭, 극성 맞춤, 기울기 보정, Otsu |
| OCR | PaddleOCR 3.7.0, `korean` PP-OCRv5 모델, Apache-2.0 | 줄 잇기, O/I 보정, 문자열 정규화 |
| 상태 판정 | – | readable / uncertain / unreadable 규칙, `?` 표시 |
| 평가 | – | 짝짓기, 검출률, 완전일치율, 문자 정확도, 과신 건수, 집계, 비교 |

가중치: YOLO는 처음 실행할 때 `weights/`에 받아지고(git 제외), PaddleOCR은 `~/.paddlex/official_models/`에 받아집니다.

## 통합 점검 2(11/17) 안건

- `detect_plates(frame, cond=None, frame_id=None)`: 선택 인자 유지. 기존 호출도 그대로 동작합니다.
- 라벨 스키마: 번호판 부분을 [docs/ocr_evaluation.ko.md](../ocr_evaluation.ko.md)의 형식으로 맞추거나 `load_labels`만 수정합니다.
- 눈 클립에 쓸 `eval_set.csv`의 condition 값.
- `data/clips/`, `data/frames/`는 git에서 제외.
- `compare(summary)` 대신 `compare(results_dir, labels)`: 프레임별 개수에는 OCR CSV와 라벨이 필요합니다.
- D와 `vlm/score.csv`의 열 확정: 조건·클립별 개수([docs/aggregation.ko.md](../aggregation.ko.md)).
- 번호판 글자가 든 결과 CSV(`results/ocr/<cond>.csv`, `worse_cases.csv`): 실제 결과는 git에서 제외.
- 원본 프레임이 오면 바로 `python -m src.plate.run orig` 실행.

## 리스크와 결과

| 상황 | 알 수 있는 때 | 대안 | 결과 |
| --- | --- | --- | --- |
| OCR이 한국 번호판을 거의 못 읽음(10장 중 3장 이하) | 11/8–11/9, C-01 | 다른 OCR로 교체, 안 되면 문자 정확도 중심 | 해당 없음: PaddleOCR 7/10 (3/10인 EasyOCR은 제외) |
| 번호판 검출 모델이 한국 번호판을 못 잡음 | 11/10–11/12, C-03 | 차량 박스 안 엣지·비율 기반 후보 탐색 직접 구현, 안 되면 라벨 bbox + OCR만 자동화 | 직접 구현 사용: 10/10장에서 상위 3개 안 |
| 블랙박스 프레임의 번호판이 너무 작음 | 11/17 축소 사진으로 측정, 이후 원본 결과 | 번호판이 크게 보이는 타임스탬프를 더 고르고 B에게 추가 요청 | 측정함([plate_size_check.ko.md](../plate_size_check.ko.md)): 폭 80 px부터 잘 읽고, 그 아래는 한글을 놓치며, 40 px 미만은 못 읽음. 기준: 1920×1080에서 80 px 이상. 실제 프레임은 아직 확인 전 |
| 모델 설치·GPU 문제 | 11/8 | CPU용 작은 모델(n 사이즈)로 고정 | CPU로 충분. PC 한 대에서 `pandas==2.2.3`, `chardet==5.2.0` 고정(Windows 응용 프로그램 제어), `enable_mkldnn=False`(PaddlePaddle 3.3 CPU), 백신 HTTPS 검사로 OS 인증서 저장소 필요 |
| 라벨이 늦게 확정됨 | 11/16 | 가짜 라벨로 `eval_ocr`을 먼저 완성하고 숫자만 다시 뽑음 | 발생 중: 저장소에 스키마 없음. 가짜 파일로 평가·집계·비교 완성(#16, #24, #26) |

## 제출 전 최종 점검

11/25 전에 아래가 모두 되어 있으면 C의 몫은 끝났습니다.

- [x] `src/plate/`와 `src/eval/`에 `cv2` 처리 함수가 없음. 입출력용 `imdecode`, `imencode`만 사용
- [x] `_stub`이 붙은 함수 0개
- [ ] `orig.csv`, `fixed.csv`, `adaptive.csv`의 프레임 목록이 완전히 같음 — 프레임 필요
- [x] 모든 결과 행에 `bbox`, `crop_path`, `text`, `conf`, `status`가 있고, `unreadable`이면 `text`가 `None` (테스트)
- [x] `eval_ocr`이 손으로 계산한 3건과 같은 값을 냄 (#16)
- [x] 비교표에서 개선 + 악화 + 변화 없음 = 비교한 프레임 수 (#26, 테스트)
- [x] 검출기·OCR의 모델명, 버전, 가중치 출처, 라이선스가 선정 메모에 있음
- [ ] D에게 README용 표 전달 — 위에 표 준비됨
- [ ] 모델 가중치가 자동으로 받아지거나 받는 방법이 README에 있음 — 코드에서는 자동, README는 D 담당
- [ ] 발표용 자료로 쓸 개선 사례 3건, 악화 사례 3건의 크롭 이미지 — 실제 결과가 오면 악화 사례는 `worse_cases.csv`에서, 개선 사례는 직접 고름
