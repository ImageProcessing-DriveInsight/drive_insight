# AI Hub 차량 라벨로 차량 검출률 재기 (#90)

[English](aihub_vehicles.md)

AI Hub 자료는 번호판이 가려져 있어 OCR 평가에는 쓸 수 없지만, 차량마다 영역 라벨(다각형)이 있습니다.
`tools/aihub_vehicles.py`는 이 라벨을 차량 검출률(`src/eval/vehicles.py`)이 읽는 scenes 파일로 바꿉니다.
그러면 원본·고정·적응형에서 라벨이 있는 차를 몇 대 찾았는지 야간·비·터널 프레임에서 잴 수 있습니다.

```
python tools/aihub_vehicles.py <라벨 폴더> [<라벨 폴더> ...] [--out data/annotations/aihub_vehicles.json] [--names names.csv]
python -m src.eval.vehicles --frames <프레임 폴더> --scenes data/annotations/aihub_vehicles.json
```

## 라벨 형식

| 형식 | 데이터 | 차량으로 세는 클래스 |
| --- | --- | --- |
| labelme (`shapes`, `points`) | 71588 야간 자동차 전용도로, 630 다양한 기상 | car, truck, bus, motorcycle, trailer, caravan |
| polygon (`annotations`, 좌표를 한 줄로 나열) | 71570 주간 자동차 전용도로, 71930 업사이클링 | vehicle, truck, bus, ambulance, schoolBus, otherCar, policeCar |

- 차량 박스는 다각형을 감싸는 박스이고, 이미지 밖으로 나간 부분은 잘라냅니다.
- 차량 검출기(YOLO)가 찾는 종류(car, bus, truck, motorcycle)에 해당하는 클래스만 셉니다.
  내 차 보닛(ego vehicle), 사람, 자전거, 기차, 표지판, 도로는 뺍니다.
- 묶음 라벨(cargroup, busgroup 등)이 있는 프레임은 `annotation_status: "group"`으로 적어 평가에서 뺍니다.
  묶음 안의 차는 각자 박스가 없어서, 검출기가 찾으면 라벨 없는 검출(`unmatched`)로 잘못 세지기 때문입니다.
- 차량이 없는 프레임도 빈 목록으로 평가에 들어가고, 거기서 나온 검출은 `unmatched`로 셉니다.

## 프레임 이름

- 기본: 라벨에 적힌 이미지 파일 이름의 확장자를 `.png`로 바꿉니다(`a.jpg` → `a.png`). 라벨에 파일 이름이 없으면 JSON 파일 이름을 씁니다.
- 평가 프레임 이름을 따로 정하면 `source,frame` 열이 있는 CSV를 `--names`로 넘깁니다. `source`는 원본 이미지 파일 이름입니다.
  CSV에 없는 라벨은 건너뛰므로, 고정한 평가 목록만 남길 때도 씁니다.
- 두 라벨이 같은 프레임 이름이 되면 멈춥니다.

## 팀 데이터에서 확인한 수 (11/22)

라벨만 바꿔 본 결과이고 검출은 돌리지 않았습니다. 평가 목록을 고정하기 전에 결과를 보지 않기 위해서입니다.

| 데이터 | 프레임 | 평가에 들어가는 프레임 | 차량 | 폭 <100 px | 100–199 px | ≥200 px |
| --- | --- | --- | --- | --- | --- | --- |
| 71588 야간 (A) | 10,000 | 8,552 (묶음 라벨 1,448장 제외) | 21,287 | 15,524 | 3,287 | 2,476 |
| 630 비 (B) | 3,000 | 3,000 | 5,640 | 1,637 | 1,830 | 2,173 |
| 71570 터널·밝은 하늘 (D) | 320 | 320 | 1,813 | 1,534 | 184 | 95 |
| 71930 터널 (D) | 176 | 176 | 759 | 541 | 132 | 86 |

- 폭 100 px 미만인 먼 차가 많으므로 전체 검출률보다 크기별 검출률(`size` 열)을 보는 게 좋습니다.
- 차 한 대가 다각형 여러 개로 나뉘어 있으면 박스도 여러 개가 됩니다. 71588과 630에서 한 프레임 안의 차량 다각형이
  같은 `object_id`를 나눠 가진 경우는 없었습니다. 다만 71588 차량 다각형의 약 절반과 630 전체는 `object_id`가 없어서
  그 부분은 확인하지 못했습니다.

## 데이터 취급

- scenes 파일에는 번호판 정보가 없지만 AI Hub 라벨에서 나온 파일이므로 git이 무시하는 `data/annotations/`에 둡니다.
- 테스트(`tests/test_aihub_vehicles.py`)는 직접 만든 가짜 라벨만 씁니다.
