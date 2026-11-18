# B 모듈 실행 안내 (2026-11-17 develop 기준)

이 통합본은 제공된 develop ZIP(ea14cc71c4c993aff02f43e98545d692662c43e5)에 B 코드만 추가했다.
A/C의 기존 파일은 수정하지 않았다. 원본 PR #6의 I/O 파일도 로컬 검증용으로 포함했다.
GitHub 업로드·PR 생성·병합은 수행하지 않았다.

## 바로 실행

프로젝트 루트(src/tests 폴더가 있는 위치)에서 명령을 한 줄씩 실행한다.

```bat
py -m pip install -r requirements-b.txt
py -m pytest -q
py -m tools.b_status
```

Linux/macOS에서는 `py` 대신 `python`을 쓴다.
Windows에서는 `run_b_tests.cmd`를 더블클릭해 B 테스트를 실행할 수도 있다(의존성 설치는 먼저 필요).
현재 테스트는 합성 프레임과 모델 대역을 사용한다. 실제 모델 다운로드, 영상 품질 향상, 실제 번호판 인식 정확도를 검증한 결과가 아니다.

OpenCV 배포판은 환경에 하나만 설치한다. 이번 목록은 C의 ultralytics와 맞추기 위해 opencv-python을 사용한다.
기존 opencv-python-headless와 섞지 말고 새 가상환경 사용을 권장한다.

## 1. 평가 영상 목록과 원본 프레임

docs/b/clip_manifest_template.csv를 복사하여 각 팀원이 작성한다. 헤더만 들어 있으며 가짜 평가 행은 없다.
clip은 확장자를 포함한 파일명, timestamp_ms는 정수 밀리초다.
조건값은 low_light/rain/fog/snow/backlight/tunnel/mixed를 지원한다. snow 등의 명칭은 팀 합의 후 일관되게 사용한다.
각 영상은 출처와 라이선스를 기록한다. 10~30초 영상, 3~5개 평가 시점, 번호판이 보이는 시점 절반 이상 여부는 사람이 확인한다.
실제 영상 파일은 data/clips/에 놓는다. 다음은 파일을 준비한 후 실행하는 명령이다.

```bat
py -m tools.prepare_data member_a.csv member_b.csv member_c.csv member_d.csv
py -m tools.b_cli extract
py -m tools.b_labels init
```

병합 결과: data/eval_set.csv. 프레임: data/frames/orig/<clip>_<ms>.png.
이미 존재하는 평가표는 덮어쓰지 않는다. 이전 파일을 별도로 보관한 뒤 다시 실행한다.
추출기는 CFR 전용이며 VFR은 사전에 CFR 변환이 필요하다. PNG 타임스탬프는 최근접 프레임으로 반올림한다.

## 2. 라벨 작성과 C로 전달

`data/annotations/scenes.json`의 각 프레임을 사람이 확인하여 채운다.
초기 상태는 pending이다. 사실 확인이 끝난 항목만 complete로 바꾼다.
vehicles: [{class: car/truck/bus/motorcycle, bbox:[x,y,w,h]}].
plates: [{bbox:[x,y,w,h], status:readable/unreadable, text:문자열/null}].
events, visibility_notes는 문자열 목록이다. annotator와 reviewer는 작성자/검수자다.
실제로 번호판이 없는 경우에만 plates=[]로 확정한다. pending 빈 배열은 '검출 0건 정답'이 아니다.
A와 B가 교차 검수하고 reviewer를 기록한다. B는 A의 라벨을 검수한다.

```bat
py -m tools.b_labels export --require-review
```

전체 프레임과 라벨 목록/해상도가 일치해야 한다. bbox 범위와 text/status도 검사한다.
C용 출력: `data/labels/plates.json`. 프레임명을 키로 하며 값은 [{bbox,text}]다.
장면 전체 라벨은 data/annotations에 별도로 보존하므로 C의 load_labels가 장면 메타데이터를 번호판으로 오인하지 않는다.
실제 예시 3장은 영상 미제공으로 아직 작성하지 않았다. 형식 예시와 실제 정답을 혼동하지 않는다.

## 3. 적응형 처리

measure_quality와 select_params는 A 없이 동작한다. 규칙표는 docs/rules.md.
실제 보정에는 A의 apply_ops가 필요하다. 기본 경로는 src.dip.fixed:apply_ops.
현재 제공된 develop에는 이 함수가 없다. 원본을 보정 결과로 속여 저장하는 대체 함수는 제공하지 않는다.
A와 키 gamma, hist_eq, denoise, ksize, unsharp, rules 및 연산 순서를 확인한다.
A의 현재 gamma는 Y 채널에서 (Y/255)^g를 사용한다. g<1이면 밝아진다.

```bat
py -m tools.b_cli frames --apply-ops src.dip.fixed:apply_ops
py -m tools.b_cli video data/clips/rain_01.mp4 --mode adaptive
py -m tools.b_cli video data/clips/rain_01.mp4 --mode fixed
```

A가 다른 모듈 위치를 쓰면 --apply-ops 또는 --fixed로 지정한다.
출력 프레임은 data/frames/adaptive, 로그는 results/params/adaptive.json,
영상은 results/videos/{fixed,adaptive}/<clip>.mp4.
영상은 프레임 단위 스트리밍 처리하며 원본 오디오는 포함하지 않는 무음 MP4다.
코덱이 홀수 해상도를 잘라내는 것을 방지하기 위해 짝수 해상도만 허용한다.
영상 저장 후 FPS/프레임 수를 검사하며 실패한 출력은 최종 경로로 게시하지 않는다.
일괄 PNG 작업 중 실패하면 일부 출력 PNG가 남을 수 있다. 로그 JSON은 완료 시에만 저장된다.
입력·출력 경로를 같게 설정할 수 없다.

## 4. C의 OCR, 패키지

실제 OCR에는 C의 requirements-plate.txt와 모델 환경이 추가로 필요하다.

```bat
py -m src.plate.run orig
py -m src.plate.run fixed
py -m src.plate.run adaptive
py -m tools.b_cli package rain_01
```

C CSV: frame,plate,x,y,w,h,crop_path,text,conf,status,ocr_ms.
status가 빈 행은 'OCR 실행 완료, 번호판 검출 0건'으로 해석한다.
패키지는 CSV 자체 없음, 해당 클립 결과 없음, 일부 프레임 미처리를 별도로 표시한다.
좌표는 x/y/w/h를 읽어 패키지의 bbox 필드로 변환한다.
`package/rain_01/summary.html`을 열면 키프레임·OCR·VLM·파일 목록을 볼 수 있다.
원본 복사본은 SHA-256을 대조한다. 패키지는 재생성 시 덮어쓰지 않는다.
없는 영상/파라미터/VLM은 '없음' 표시 후 계속 생성한다.
D VLM 입력은 results/vlm/<condition>/<clip>.json이다. 아직 실제 응답 계약 검증은 하지 못했다.
params/<condition>.json은 프레임명→로그 또는 {"global": 고정 파라미터}를 받는다.

## 5. 민감도 실험

```bat
py -m tools.sensitivity --scale 0.8 1.2 --labels data/labels
```

임계값 7개를 동시에 배율 변경하며 1.0 기준 실험을 항상 포함한다.
각 배율에서 보정 PNG 생성 → C run_ocr → C eval_ocr 순서로 실행한다.
결과/크롭은 results/sensitivity/scale_<배율>/results에 격리한다.
labels는 orig PNG와 정확히 동일한 프레임 집합이어야 하며 번호판 0개 프레임도 포함한다.
최종 results/sensitivity/summary.csv에 metric,value,delta_vs_1을 기록한다.
읽을 수 있는 정답 번호판이 없으면 C가 반환한 None을 유지하며 0점으로 바꾸지 않는다.
기존 실험 폴더가 있으면 별도 보관 후 실행한다.

## 남은 외부 입력

- 실제 비 영상 2~3개와 A/C/D 평가 영상 목록, 출처·라이선스
- 실제 라벨 및 교차 검수, 실제 프레임 3장에 대한 라벨 예시
- A apply_ops/fixed_enhance 구현 및 파라미터 합의
- D VLM 응답, 실행기 연결과 C 클립에 대한 VLM 사실 검증
- 실제 영상 기반 정확도 비교·처리시간·프레임 간 깜박임 점검

이 자료가 없으므로 실제 eval_set/라벨/OCR 점수를 만들어 넣지 않았다.
