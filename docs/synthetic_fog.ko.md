# 합성 안개 클립 (ALL-01)

[English](synthetic_fog.md)

한국 번호판이 읽히는 공개 안개 영상을 찾지 못했습니다. AI Hub 주행 영상은 번호판을 가리고,
악천후 데이터셋은 영상이 아니라 이미지입니다. 그래서 안개 클립은 맑은 날 영상에
`tools/synth_fog.py`로 안개를 입혀 만듭니다. 눈은 합성하지 않습니다.

보고서와 발표 자료에는 안개가 합성이라는 것과 아래 설정을 밝혀야 합니다.

## 모델

```text
I = J·t + A·(1 − t)      t = exp(−β·d)      β = 3.912 / 가시거리
```

`J`는 맑은 프레임, `A`는 안개 밝기, `d`는 거리(m)입니다. 가시거리만큼 떨어진 곳에서는
대비가 2 %만 남습니다(Koschmieder).

| 부분 | 방법 |
| --- | --- |
| 거리 `d` | 수평으로 단 카메라에서 본 평평한 도로: 지평선 행 `y_h` 아래는 `d = near·(H − 1 − y_h) / (y − y_h)`, 지평선부터 위는 `far`(300 m). 맨 아래 행은 `near`(4 m) |
| 차량 | 맑은 프레임에 YOLOv8n-seg 마스크. 차량 클래스와 임계값은 파이프라인과 같음. 마스크 안의 `d`는 마스크 맨 아래 행, 즉 차가 도로에 닿는 곳의 도로 거리. 가장자리에 배경이 묻지 않게 마스크를 2 px 줄임 |
| 흐림 | 빛 산란으로 먼 곳이 흐려짐: 1080행 기준 σ = 1.5 px 가우시안(A의 `gaussian`)을 `1 − t`만큼 섞음 |
| 노이즈 | 센서 노이즈 σ = 2(8비트 단계). 프레임마다 새로 뽑고, 시드로 재현 |

한 클립의 모든 프레임은 같은 설정을 씁니다. 노이즈와 차량 마스크만 프레임마다 바뀝니다.

화면 전체에 같은 농도로 입히지 않는 이유: 그건 밝기를 전체적으로 일정하게 바꾸는 것과 같아서,
전역 히스토그램 평활화가 거의 그대로 되돌립니다. B의 적응형 규칙 `CT_LOW`는 대비가 35 아래로
떨어지면 그걸 켜기 때문에, 적응형이 실제 안개에서보다 훨씬 좋게 나옵니다. 거리에 따라 짙어지는 안개는 그렇게 되돌아가지
않습니다(`test_fog_thickens_with_distance_so_hist_eq_cannot_undo_it`).

## 농도

| `--density` | 가시거리 | 10 m에서 남는 빛 | 20 m | 40 m |
| --- | --- | --- | --- | --- |
| `light` | 300 m | 0.88 | 0.77 | 0.59 |
| `medium`(기본) | 150 m | 0.77 | 0.59 | 0.35 |
| `heavy` | 75 m | 0.59 | 0.35 | 0.12 |

다른 값은 `--visibility`로 정합니다. 클립별 농도는 결과를 보기 전에 정하고, OCR이나 VLM 점수를
보고 바꾸지 않습니다.

## 작업 순서

맑은 원본 영상은 `data/clips/`가 아니라 `data/clear/`(git 제외)에 둡니다.
구간과 타임스탬프는 먼저 OCR 없이 차량 크기로 고릅니다([타임스탬프 고르기](frame_pick.ko.md)).

```bash
# 0. 구간과 타임스탬프. 3단계의 매니페스트 행을 추가하고 make 구간을 출력
python tools/pick_frames.py scan data/clear/day_01.mp4
python tools/pick_frames.py pick data/clear/day_01.mp4 --clip fog_01.mp4 --density medium
# 1. 한 프레임을 맑은 것·안개 낀 것 나란히. 빨간 선이 지평선 행
python tools/synth_fog.py preview data/clear/day_01.mp4 --at 5000 --horizon 0.45
# 2. 안개 클립(10–30초)과 설정 파일 data/clips/fog_01.fog.json
python tools/synth_fog.py make data/clear/day_01.mp4 data/clips/fog_01.mp4 --horizon 0.45 --start-ms 12000 --end-ms 37000
# 3. fog_01.mp4의 매니페스트 행 작성 -> B가 합치고 data/frames/orig/fog_01_<ms>.png 추출
# 4. 같은 이름의 맑은 프레임 data/frames/clear/fog_01_<ms>.png (타임스탬프는 data/eval_set.csv에서)
python tools/synth_fog.py reference data/clips/fog_01.mp4
# 5. 맑은 프레임으로 라벨 초안 (박스 위치는 같고 검출은 더 잘 됨)
python tools/label_draft.py draft --frames data/frames/clear --only "fog_*"
# 6. orig, fixed, adaptive OCR 뒤에: 맑은 프레임을 기준으로 (results/ocr/clear.csv, #79)
python -m src.plate.run clear
```

- 지평선 행은 도로가 하늘과 만나거나 사라지는 곳에 맞춥니다. 너무 낮으면 가까운 도로까지 뿌옇고,
  너무 높으면 먼 도로가 맑게 남습니다.
- `make`는 CPU에서 1080p 프레임당 약 0.33초, 30fps 30초 클립이면 약 5분 걸립니다.
  이미 있는 클립이나 설정 파일은 덮어쓰지 않습니다.
- 매니페스트 행: `condition`은 `fog`, `source`는 `own dashcam, synthetic fog (tools/synth_fog.py, medium)`처럼,
  `license`는 `own footage`처럼 적습니다.
- 라벨 `status`는 다른 조건과 같은 기준으로 안개 프레임을 보고 정합니다. 안개 프레임이나 앞뒤 프레임에서
  사람이 읽을 수 있을 때만 `readable`입니다. 글자는 맑은 프레임을 보고 정확히 적습니다.

## 설정 파일

`<clip>.fog.json`은 안개 클립 옆에 생깁니다. 모델, 모든 설정(`visibility`, `horizon`, `near`, `far`,
`airlight`, `blur`, `noise`, `seed`, `vehicles`), 원본 경로와 SHA-256, 프레임 구간, fps, 크기, 코덱이
들어 있습니다. `reference`는 원본이 해시와 같은지 확인합니다. 클립과 함께 공유하고, 보고서에는
설정값을 적습니다.

## 주의할 점

- 언덕, 커브, 기울어진 카메라에서는 평평한 도로 가정이 맞지 않습니다.
- 촬영 차량의 대시보드는 아래쪽 행에 있어 그 행의 도로 거리를 받습니다. 차 안에 있는데도 안개가 조금
  끼는 셈입니다. YOLOv8n-seg는 일부 프레임에서만 이것을 차로 찾았는데, 이 마스크는 뺍니다(`own_car`, #78).
  그래서 대시보드의 안개는 프레임마다 같습니다.
- 마스크 모델이 놓친 차량은 행마다 도로 거리를 받아서 윗부분이 배경처럼 흐려집니다. 마스크는
  프레임마다 찾으므로 차량 가장자리가 조금 떨릴 수 있습니다.
- 가중치 `weights/yolov8n-seg.pt`(7 MB, git 제외)는 처음 실행할 때 받습니다. 인증서 오류로 실패하면
  <https://github.com/ultralytics/assets/releases/download/v8.4.0/yolov8n-seg.pt>를 `weights/`에 저장하세요.
  `--no-vehicles`를 주면 마스크를 쓰지 않습니다.
- OpenCV가 쓸 수 있으면 H.264(`avc1`), 아니면 MPEG-4(`mp4v`)로 저장합니다. 시도하는 동안 OpenCV가
  H.264나 `Failed to initialize VideoWriter` 오류를 출력할 수 있는데, 마지막에 `wrote N frames`가 나오면
  클립은 정상입니다. 실제로 쓴 코덱은 설정 파일에 있습니다.

## 샘플 실행

샘플 사진을 천천히 확대해 만든 10초 1080p 테스트 클립(블랙박스 영상 아님), `medium`, 지평선 0.45:
300프레임에 98초, H.264로 저장. 차는 윤곽 그대로 남았고, 하늘과 배경은 회색으로 사라졌고,
도로 안개는 지평선으로 갈수록 짙어졌습니다.
