# 팀원별 기능 명세

DriveInsight · Team 16 Black Box · **최신화 2026-11-16**

[English](feature_spec.md) · [역할 분담 및 WBS](team_plan.ko.md) · [팀원 C 가이드](member_c_guide.ko.md)

팀원 A\~D가 구현할 기능을 ID, 입력→출력, 요구사항, 검증 방법으로 정리했습니다. 프레임은 모두 `uint8` BGR `(H, W, 3)`, 실험 조건은 `orig`·`fixed`·`adaptive`입니다. 수치 기준(속도, 임계값)은 출발점이고, 통합 점검 1(11/10)에서 조정합니다.

상태 열은 11/16 기준 저장소 내용만 반영합니다. **—** 는 저장소에 아직 없다는 뜻입니다(저장소 밖에서 진행 중일 수 있음).

## 팀원 A · 영상처리 연산

과목 핵심 채점 대상인 영상처리 연산을 NumPy로 직접 구현합니다. `cv2`는 테스트 코드에서 결과 비교용으로만 씁니다. 파일: `src/dip/`, `tests/`, `tools/check_forbidden.py`.

| ID | 기능 | 입력 → 출력 | 요구사항 | 검증 방법 | 상태 |
| --- | --- | --- | --- | --- | --- |
| A-01 | 색 공간 변환 | `bgr_to_ycrcb(img)`, `ycrcb_to_bgr(img)` | 변환 행렬 직접 계산. 밝기 연산은 Y 채널에만 적용해 색감 왜곡 방지 | 왕복 변환 후 원본과 픽셀 차 ≤ 2 | — |
| A-02 | 히스토그램 평활화 | `hist_eq(img) -> img` | 256구간 히스토그램과 CDF 정규화 직접 계산. 모든 픽셀이 같은 값이면 입력 그대로 반환 | `cv2.equalizeHist` 대비 평균 절대 차 ≤ 1 | — |
| A-03 | 감마 보정 | `gamma(img, g) -> img` | 256칸 LUT 직접 생성. `g`는 0.3–3.0, 범위 밖이면 `ValueError` | `g=1`이면 입력과 동일 | — |
| A-04 | Gaussian 필터 | `gaussian(img, ksize, sigma) -> img` | 커널 직접 생성(합 = 1), 분리형 1D 컨볼루션 2회, 반사 패딩. `ksize`는 3–9 홀수 | `cv2.GaussianBlur` 대비 차 ≤ 1 | — |
| A-05 | Median 필터 | `median(img, ksize) -> img` | `ksize` ∈ {3, 5}. `sliding_window_view` + `np.median` | 소금·후추 노이즈 제거, `cv2.medianBlur`와 일치 | — |
| A-06 | Unsharp masking | `unsharp(img, amount, sigma, threshold) -> img` | `out = img + amount × (img − blur)`, 0–255 클리핑. 차이가 `threshold` 미만인 픽셀은 미적용해 노이즈 증폭 방지 | `amount=0`이면 입력과 동일 | — |
| A-07 | 연산 실행기 | `apply_ops(img, params) -> img` | 순서 고정: 노이즈 제거 → 감마 → 평활화 → unsharp. 키가 없으면 생략, 모르는 키는 `ValueError`, `rules` 키는 무시 | 빈 dict면 입력과 동일 | — |
| A-08 | 고정 파이프라인 | `fixed_enhance(img) -> (img, params)` | 상수 `FIXED_PARAMS` 하나를 모든 프레임에 동일 적용 | 두 프레임의 `params`가 완전히 같음 | — |
| A-09 | 고정 보정 일괄 생성 | `frames/orig/` → `frames/fixed/`, `params/fixed.json` | 파일명 유지, 프레임별 처리 시간 기록 | 두 폴더 파일 목록 일치 | — |
| A-10 | 속도 개선 | 연산 전체 | 파이썬 루프 제거, 벡터화. B의 보정 영상 생성이 쓸 수 있는 속도 | 1080p 1장: Gaussian ≤ 0.5초, Median ≤ 1.5초, 고정 파이프라인 전체 ≤ 2초 | — |
| A-11 | 단위 테스트 | `tests/test_ops.py` | A-01\~A-08별 정상·경계·예외 입력 | `pytest` 전부 통과 | — |
| A-12 | 금지 함수 점검 | `check_forbidden.py src/` → 목록 | 입출력 외 cv2 함수 호출과 `_stub` 검출, 파일·줄 번호 출력 | 통합 점검 3과 11/25에 0건 | — |

## 팀원 B · 적응형 보정 + 영상 입출력 + 패키지

영상과 파일을 다루는 코드와 적응형 규칙을 맡습니다. 보정 연산 자체는 A의 `apply_ops`를 호출합니다. 파일: `src/io/`, `src/adaptive/`, `src/package/`, `tools/sensitivity.py`.

| ID | 기능 | 입력 → 출력 | 요구사항 | 검증 방법 | 상태 |
| --- | --- | --- | --- | --- | --- |
| B-01 | 프레임 추출 | `extract_frames(clip, timestamps) -> [png_path]` | `eval_set.csv`의 타임스탬프로 `frames/orig/<clip>_<ms>.png` 생성. OpenCV 입출력만 사용, 무손실 PNG | 타임스탬프 오차 ≤ 1프레임, 표의 행 수 = 파일 수 | 리뷰 중(#6) |
| B-02 | 영상 입출력 | `read_video(path)`, `get_meta(path)`, `write_video(frames, fps, path)` | 프레임을 하나씩 내는 이터레이터(전체를 메모리에 올리지 않음). fps, 프레임 수, 길이, 해상도 반환 | 읽고 그대로 쓴 영상의 fps·프레임 수 동일 | 리뷰 중(#6) |
| B-03 | 품질 측정 | `measure_quality(img) -> dict` | `brightness`(Y 평균), `contrast`(Y 표준편차), `noise`(라플라시안 기반 σ 추정), `sharpness`(라플라시안 분산). 컨볼루션은 직접 구현 | 밝은/어두운, 선명/흐린 샘플에서 값 방향이 맞음 | — |
| B-04 | 규칙 선택 | `select_params(quality) -> params` | 지표 구간별로 연산·강도를 고르는 규칙 표(예: 밝기 < 60이면 `gamma 0.5`). 같은 입력에 항상 같은 출력. 적용된 규칙 ID를 `params["rules"]`에 기록. 규칙 표는 `docs/rules.md`에도 정리 | 규칙별 단위 테스트, 문서와 코드의 규칙 ID 일치 | — |
| B-05 | 적응형 파이프라인 | `adaptive_enhance(img) -> (img, params, quality)` | `apply_ops(img, select_params(measure_quality(img)))`. 11/17 전까지는 `apply_ops_stub` | stub을 실제 함수로 바꾼 뒤에도 같은 규칙 ID가 나옴 | — |
| B-06 | 적응형 보정 일괄 생성 | `frames/orig/` → `frames/adaptive/`, `params/adaptive.json` | 프레임별 quality, params, 규칙 ID, 처리 시간 기록 | 파일 목록이 `orig`와 일치 | — |
| B-07 | 보정 영상 생성 | `enhance_video(clip, mode) -> mp4` | `mode`는 `fixed` 또는 `adaptive`. B-02로 읽고 쓰며 프레임마다 보정 적용. 진행률 표시 | 원본과 fps·프레임 수 동일 | — |
| B-08 | 리뷰 패키지 | `build_package(clip_id) -> package/<clip>/` | 원본 영상(복사), 보정 영상 2종, 조건별 키프레임, 번호판 크롭과 `plates.csv`, `params.json`, `vlm_summary.json`, `summary.html`. 빠진 결과는 "없음"으로 표시하고 멈추지 않음 | 원본 해시가 복사본과 같음, 모든 클립에서 폴더 생성 | — |
| B-09 | 민감도 실험 스크립트 | `sensitivity.py --scale 0.8 1.2` → 변화량 표 | 임계값을 ±20% 바꿔 적응형 프레임을 다시 만들고 C의 `eval_ocr`를 호출 | 임계값별 OCR 지표 표 생성 | — |

## 팀원 C · 번호판 인식 + 평가 집계

검출기와 OCR은 사전학습 모델을 쓰되, 크롭 전처리·후보 탐색·판정 규칙·평가는 직접 구현합니다. 없는 글자를 추측해 채우지 않습니다. 마지막에 모든 결과를 모아 조건 간 비교표를 만듭니다. 파일: `src/plate/`, `src/eval/`.

| ID | 기능 | 입력 → 출력 | 요구사항 | 검증 방법 | 상태 |
| --- | --- | --- | --- | --- | --- |
| C-01 | 모델 선정 | → 선정 메모 | 차량 검출기, 번호판 검출기, 한국어 OCR 후보를 한국 번호판 샘플 10장으로 비교. 모델명·버전·가중치 출처 기록 | 10장 중 읽힌 수 기록 | 완료(#4, #8): YOLOv8n 차량 10/10, PaddleOCR 7/10, EasyOCR 3/10. [메모](../model_selection.ko.md) |
| C-02 | 차량 검출 | `detect_vehicles(img) -> [{bbox, cls, conf}]` | car, truck, bus, motorcycle. `conf` ≥ 0.4. bbox는 `(x, y, w, h)`, 큰 박스부터 | 라벨 차량과 IoU ≥ 0.5 비율 | 완료(#10) |
| C-03 | 번호판 후보 검출 | `detect_plate_candidates(img, vehicles) -> [bbox]` | 직접 구현: 차량 박스 아래쪽 탐색. 수직 에지 밀도와 밝기를 주변 띠와 비교해 점수 계산(적분 영상), 최고 창을 판 전체로 확장, 차량당 상위 3개, 차량이 없으면 프레임 전체 | 라벨 번호판 검출률 | 완료(#10): 실제 사진 10/10장에서 상위 3개 안, 8/10장에서 1위 |
| C-04 | 크롭 전처리 | `preprocess_plate(crop, binarize=False, deskew=True) -> 그레이 크롭` | 직접 구현: 그레이 변환(가중합), 높이 64px 쌍선형 리사이즈, 대비 스트레칭, 글자를 어둡게 맞춤, 기울기 보정 ±10°, Otsu(선택) | 전처리 유무별 OCR 정확도 비교 | 완료(#12): 기본값 그레이+스트레칭+기울기 보정. Otsu는 2/10으로 떨어져 끔. [노트](../plate_recognition.ko.md) |
| C-05 | 문자 인식 | `recognize(crop) -> (text, conf)` | PaddleOCR `korean`. 두 줄 번호판은 위→아래로 이음. `O`→`0`, `I`/`l`→`1`, 숫자·한글만 남김. conf는 박스 점수 중 최솟값. 형식 `^([가-힣]{2})?\d{2,3}[가-힣]\d{4}$`(지역명 허용) | 라벨 문자열과 비교 | 완료(#12) |
| C-06 | 상태 판정 | `judge(text, conf) -> (status, text)` | `readable`: 형식 일치 + `conf` ≥ 0.8. `uncertain`: `conf` ≥ 0.5이고, 형식은 맞지만 `conf` < 0.8이거나 한 자리만 고치면 형식이 맞음(그 자리는 `?`). `unreadable`: 그 외, `text = None`. uncertain에 `?`가 필요해 text도 함께 반환 | 판정별 단위 테스트 | 완료(#12): 실제 사진에서 틀린 답이 readable로 나온 경우 0건 |
| C-07 | 통합 함수 | `detect_plates(frame, cond=None, frame_id=None) -> [PlateResult]` | 공통 인터페이스 형식. 차량당 결과 하나: 후보를 순서대로 읽다 readable이면 멈추고 가장 좋은 결과 유지. 크롭은 `results/ocr/crops/<cond>/<frame_id>_<n>.png` | 필드 누락 0건 | 완료(#14). 선택 인자는 11/17 확정 |
| C-08 | 조건별 실행 | `run_ocr(cond)`, `python -m src.plate.run <cond>`: `frames/<cond>/` → `results/ocr/<cond>.csv` | `orig`, `fixed`, `adaptive`를 같은 프레임 목록으로. 번호판이 없는 프레임도 빈 행 하나 유지 | 세 CSV의 프레임 목록 일치 | 코드 완료(#14), 실행은 프레임 대기 |
| C-09 | OCR 평가 | `eval_ocr(results, labels) -> dict`, `python -m src.eval.ocr` → `ocr_summary.csv` | 검출률(1:1, 작은 박스 기준 겹침 ≥ 0.5, IoU 큰 순서), 완전일치율, 문자 정확도(1 − 편집 거리 / 길이). unreadable 라벨은 별도 집계하고 과신 건수 보고. 표준이 아닌 번호판(광고용, 군용)은 `nonstandard_labels`로 따로 셈. `readable_wrong`, C-11용 `frame_char_accuracy`도 제공. B의 민감도 스크립트가 호출 가능 | 손으로 계산한 3건과 일치 | 완료(#16, #52). 라벨 형식은 [노트](../ocr_evaluation.ko.md), B의 라벨 내보내기가 이 형식으로 씀 |
| C-10 | 전체 집계 | `aggregate(results_dir, labels=None) -> summary.csv`, `python -m src.eval.aggregate` | OCR 지표, D의 VLM 점수, `timing.csv`를 조건별로 합침 | 원본 CSV들과 수치 일치 | 완료(#24): VLM 개수는 클립을 합쳐 계산, 없는 파일은 해당 열을 빈 값으로 둠. `score.csv` 형식은 [노트](../aggregation.ko.md)에 제안 |
| C-11 | 조건 간 비교표 | `compare(results_dir, labels) -> (비교표, 사례 목록)`, `write_compare` → `compare.csv`, `worse_cases.csv` | `orig` 대 `fixed`, `fixed` 대 `adaptive`에서 프레임별 개선·악화 건수를 모두 표시. 악화 사례는 크롭 경로와 함께 출력 | 개선 + 악화 + 변화 없음 = 전체 프레임 수 | 완료(#26): 읽을 수 있는 라벨이 없거나 CSV에 없는 프레임은 따로 셈. 시그니처는 11/17 확정. 발표용 이미지: `tools/compare_images.py`(#63). [노트](../comparison.ko.md) |

## 팀원 D · 실험 실행기 + VLM + 실행 환경

세 조건이 같은 프레임과 같은 설정으로 돌아가도록 보장하고, VLM 요약과 채점, 채점자 컴퓨터에서 돌아가는 실행 환경을 맡습니다. 파일: `src/common/`, `src/pipeline/`, `src/vlm/`, `main.py`.

| ID | 기능 | 입력 → 출력 | 요구사항 | 검증 방법 | 상태 |
| --- | --- | --- | --- | --- | --- |
| D-01 | 공용 유틸 | `load_frame`, `save_frame`, `get_logger`, `Timer`, `paths` | 모든 경로는 프로젝트 루트 기준 상대경로 | 다른 폴더에서 실행해도 동작 | — |
| D-02 | 진입점 | `main.py --condition --steps --clip` | 실행기, 패키지, 집계를 한 곳에서 호출. 인자 없이 실행하면 세 조건 전체 | `python main.py` 한 번으로 끝까지 | — |
| D-03 | 실험 실행기 | `run_experiment(condition, steps) -> results/` | `steps` = 보정, OCR, VLM 중 선택. 세 조건의 프레임 목록이 다르면 오류로 중단. 실행마다 모델 버전·프롬프트 해시를 `config_snapshot.json`에 저장 | 같은 입력으로 두 번 돌려 같은 결과 | — |
| D-04 | 시간 측정 | → `timing.csv` (frame, condition, enhance\_ms, ocr\_ms, vlm\_ms, total\_ms) | 단계별 측정 | 누락 행 0건 | — |
| D-05 | VLM 요약 | `summarize_scene(frames) -> dict` | VLM 하나를 고정하고 temperature 0. 응답 스키마: `vehicles`, `events`(순서, 내용, 프레임), `visibility_notes`, `uncertain`. 번호판 문자는 VLM이 주장하지 않도록 프롬프트에 명시. 스키마 위반 시 1회 재요청 후 실패 기록 | 스키마 검증 통과율 100% | — |
| D-06 | VLM 응답 캐시 | → `results/vlm/<cond>/<clip>.json` | 모든 응답 저장. API 키가 없거나 `--offline`이면 캐시를 읽어 채점·패키지까지 실행 | 키 없이 전체 흐름 완주 | — |
| D-07 | 주장 추출 | `extract_claims(vlm_json) -> verify_sheet.csv` | 응답을 확인 가능한 주장 단위로 나눠 검증 시트 생성. 조건 이름은 가리고 순서를 섞음 | 주장 수가 응답 항목 수 이상 | — |
| D-08 | VLM 채점 | `score_vlm(verify_sheet, labels) -> score.csv` | 장면 사실 정확도 = 라벨 사실 중 맞게 언급된 비율. 환각률 = 근거 없는 주장 / 확인 가능한 주장 × 100. 확인 불가 주장은 분모에서 빼고 별도 표기, 분모가 0이면 N/A | 손으로 계산한 3건과 일치 | — |
| D-09 | VS 프로젝트 | `.sln`, `.pyproj`, `requirements.txt` | 시작 파일 `main.py`, 가상환경 연결, 가중치 자동 다운로드 또는 안내, API 키는 미포함 | VS에서 F5로 실행 | — |
| D-10 | 실행 README | `README.md` | 설치, 실행 명령, 오프라인 모드, 사전학습 모델과 직접 구현 범위 표 | 팀원 외 한 명이 README만 보고 실행 | — |
| D-11 | 재현 테스트와 제출 | → `Team16_BlackBox_Src.zip` | 새 환경에서 zip만 풀어 실행, 절대경로·누락 파일 점검 | 새 환경 실행 성공, 11/28 22:00 전 제출 | — |

## 전원 · 데이터 작업(4등분)

사람이 판단해야 하는 세 작업은 클립 단위로 나눕니다. 자기가 모은 클립은 직접 라벨링하고, 라벨 검수와 VLM 사실 검증은 다른 사람 클립을 맡습니다. 배정은 [역할 분담 및 WBS](team_plan.ko.md)의 데이터 작업 4등분 표를 따릅니다.

| ID | 기능 | 입력 → 출력 | 요구사항 | 검증 방법 | 상태 |
| --- | --- | --- | --- | --- | --- |
| ALL-01 | 클립 수집 | → `data/clips/`, 출처·타임스탬프 목록 | 한 사람당 맡은 조건의 클립 2–3개, 클립당 10–30초. 공개 데이터셋 또는 본인 촬영본만. 타임스탬프 3–5개, 그중 절반 이상은 번호판이 보이는 프레임. 11/8 오전 마감 | B가 `eval_set.csv`로 합칠 때 항목 누락 0건 | — |
| ALL-02 | 정답 라벨링 | 자기 클립의 원본 프레임 → `labels/*.json` | 눈으로 확인되는 차량·사건만 기록. 번호판은 원본이나 연속 프레임으로 확실히 읽힐 때만 문자열, 아니면 unreadable | B의 스키마 검사 통과 | —(스키마 없음) |
| ALL-03 | 라벨 교차 검수 | 짝의 라벨 → 수정 의견 | A↔B, C↔D. 불일치 항목은 통합 점검 2(11/17)에서 확정 | 모든 라벨 파일에 검수자 표시 | — |
| ALL-04 | VLM 사실 검증 | 다른 사람 클립의 `verify_sheet.csv` → 판정 열 채움 | A→B→C→D→A 순환. 주장마다 맞음 / 근거 없음 / 확인 불가 중 하나. 원본 프레임과 라벨 기준, 조건 이름은 가려진 상태 | 10% 표본을 한 명 더 판정해 일치율 확인 | — |
