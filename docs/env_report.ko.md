# 환경 조건별 결과 (#92)

[English](env_report.md)

`tools/plate_report.py`는 `data/frames/<cond>/` 안의 프레임을 모두 합쳐서 셉니다. 안개·야간·비·터널 프레임이 함께 있으면
조건마다 다른 결과가 평균에 묻힙니다. `tools/env_report.py`는 `plate_report`를 돌린 뒤 결과를 프레임의 환경 조건으로 나누고,
OCR과 차량 검출은 다시 돌리지 않은 채 평가·집계·비교만 조건마다 다시 합니다.

```
python tools/plate_report.py --scenes data/annotations/scenes.json data/annotations/aihub_vehicles.json
python tools/env_report.py --scenes data/annotations/scenes.json data/annotations/aihub_vehicles.json [--envs envs.csv]
```

## 출력

| 경로 | 내용 |
| --- | --- |
| `results/by_env/<env>/` | 그 조건 프레임의 결과만. `summary.csv`, `compare.csv`, `vehicles.csv`, `vehicle_compare.csv`, `figures/` |
| `results/by_env/summary.csv`, `compare.csv`, `vehicles.csv`, `vehicle_compare.csv` | 조건별 표를 하나로 합친 표. 맨 앞에 `env` 열 |

## 프레임의 환경 조건

- `data/eval_set.csv`: `<클립 이름>_<timestamp_ms>.png`(B의 프레임 이름)는 그 행의 `condition`을 따릅니다.
  행의 `clip`은 VLM 점수를 나눌 때 씁니다.
- `--envs`: `frame`, `env` 열(선택: `clip`)이 있는 CSV입니다. 타임스탬프가 없는 AI Hub 프레임처럼 이름 규칙이 다른 프레임에 씁니다.
  `eval_set.csv`보다 우선합니다.
- 조건을 알 수 없는 프레임이 하나라도 있으면 멈춥니다. 어느 조건에도 들어가지 않고 빠지는 프레임이 없게 하려는 것입니다.

## 나누는 방식

- OCR 결과, 차량 검출 결과, 보정 로그(`params/<cond>.json`), 시간 파일은 프레임 단위로 나눕니다. `params`에서 `global`처럼
  프레임 이름이 아닌 키는 그대로 둡니다.
- 번호판 라벨도 같은 프레임으로 나눕니다(메모리에서만 하고 파일로 쓰지 않습니다). 다른 조건 프레임의 라벨이 남아 있으면
  그 번호판을 놓친 것으로 세기 때문입니다.
- VLM 점수(`vlm/score.csv`)는 `clip`으로 나눕니다. `clip`이 빈 행은 나눌 수 없어서 뺍니다.
- 차량 라벨은 나눌 필요가 없습니다. 검출 결과가 있는 프레임만 세기 때문입니다.

## 차량 라벨 파일 여러 개

`--scenes`에 파일을 여러 개 주면 합쳐서 씁니다(`src.eval.vehicles`, `tools/plate_report.py`, `tools/compare_images.py`,
`tools/env_report.py`). 직접 찍은 프레임의 `scenes.json`과 AI Hub 변환 파일([#90](aihub_vehicles.ko.md))을 함께 쓰는 경우입니다.
같은 프레임이 두 파일에 있으면 멈춥니다. 파일을 주지 않으면 전처럼 `data/annotations/scenes.json`을 씁니다.

## 확인한 것

- 직접 찍은 안개 프레임 48장(조건 하나)으로 돌렸을 때, 조건별 표의 OCR 지표·시간·차량 검출률이 합친 표와 모두 같았습니다(11/23).
- 테스트(`tests/test_env_report.py`)는 손으로 만든 안개·비·야간 결과를 씁니다. 합치면 orig가 번호판 2개 중 1개를 맞히지만,
  조건별로는 안개 1개 중 0개, 비 1개 중 1개가 되는지 확인합니다. 시간, 보정 로그, VLM 점수, 차량 라벨 두 파일, 조건을 모르는
  프레임, 다시 실행할 때 지워지는 옛 파일도 확인합니다.

## 데이터 취급

`results/by_env/`에는 번호판 글자가 든 OCR 결과와 실제 번호판 크롭 이미지가 들어가므로 git이 무시합니다.
다시 돌리면 이번에 찾은 조건의 폴더를 통째로 새로 씁니다.
