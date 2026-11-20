# 조건 간 비교 (C-11)

[English](comparison.md)

`compare(results_dir, labels)`는 `orig` → `fixed`, `fixed` → `adaptive`를 프레임 단위로 비교합니다.
`write_compare`(또는 CLI)는 `results/compare.csv`와 `results/worse_cases.csv`를 씁니다.

```
python -m src.eval.aggregate                       # C-10: results/summary.csv (지표 변화용)
python -m src.eval.compare --labels data/labels    # C-11: compare.csv, worse_cases.csv
```

## 개선, 악화, 변화 없음

프레임 점수는 그 프레임에서 읽을 수 있는 라벨 번호판들의 평균 문자 정확도입니다.
[ocr_evaluation.ko.md](ocr_evaluation.ko.md)의 `frame_char_accuracy`와 같은 값이고, 놓친 번호판은 0입니다.

- **개선(better) / 악화(worse):** 비교 대상 조건에서 점수가 오름 / 내림
- **변화 없음(unchanged):** 점수가 같음(차이 ≤ 1e-9)
- 비교하지 않고 따로 셈:
  - `no_readable_label`: 번호판이 없거나, 눈으로도 읽을 수 없는 번호판만 있음
  - `missing`: 두 OCR CSV 중 하나에 프레임이 없음

따라서 `better + worse + unchanged = frames`입니다. VLM 점수는 프레임이 아니라 클립 단위라서 지표 변화에만 나타납니다.

`sign_p`는 `better`와 `worse`에 대한 양측 정확 부호 검정입니다(#84). 대상 조건이 프레임을 좋게 할 확률과
나쁘게 할 확률이 같다고 할 때, 지금만큼 또는 그보다 한쪽으로 치우친 결과가 나올 확률입니다. 변화 없는 프레임은
빼고, 움직인 프레임이 없으면 빈 값입니다. 프레임이 적으면 값이 큽니다. 5 대 0이 0.0625이고, 0.05 아래로
내려가는 가장 작은 경우는 6 대 0입니다.

## `compare.csv`

비교 쌍마다 한 행입니다.

| 열 | 의미 |
| --- | --- |
| `base`, `target` | `orig` → `fixed`, `fixed` → `adaptive` |
| `frames`, `better`, `worse`, `unchanged` | 비교한 프레임 수와 그 분류 |
| `no_readable_label`, `missing` | 비교에서 뺀 프레임 수 |
| `sign_p` | `better`와 `worse`에 대한 양측 정확 부호 검정(#84) |
| `delta_detection_rate`, `delta_exact_match`, `delta_char_accuracy` | 대상 − 기준, `summary.csv`에서 계산 |
| `delta_vlm_scene_acc`, `delta_hallucination_rate`, `delta_total_ms` | 대상 − 기준, `summary.csv`에서 계산 |

쌍 중 한 조건의 OCR CSV가 없으면 개수는 빈 값입니다. 두 값 중 하나가 없거나
`summary.csv`(C-10, #24)가 없으면 변화량은 빈 값입니다.

## `worse_cases.csv`

악화된 프레임에서 문자 정확도가 떨어진 번호판마다 한 행이며, 많이 떨어진 순서로 정렬합니다.
두 조건의 크롭 경로를 함께 적어서 두 결과를 나란히 확인할 수 있습니다.

| 열 | 의미 |
| --- | --- |
| `base`, `target`, `frame` | 비교 쌍과 프레임(`.png`를 뺀 파일 이름) |
| `label` | 라벨 번호판 글자 |
| `base_text`, `base_status`, `base_char_acc`, `base_crop` | 기준 조건의 결과 |
| `target_text`, `target_status`, `target_char_acc`, `target_crop` | 대상 조건의 결과. 놓쳤으면 글자와 크롭은 빈 값 |

한 번호판은 좋아지고 다른 번호판은 같은 만큼 나빠진 프레임은 변화 없음이며 목록에 나오지 않습니다.
`results/ocr/<cond>.csv`와 마찬가지로 이 파일에는 번호판 글자가 들어 있습니다.

## 발표용 이미지

`tools/compare_images.py`는 이 숫자 뒤의 번호판과 프레임을 그림으로 보여 줍니다.

```bash
python tools/compare_images.py                      # results/figures/: better.png, worse.png, *_vs_fixed.png, frames/
python tools/compare_images.py --hide 2             # 라벨 번호판마다 마지막 2글자를 가림
python tools/compare_images.py --frames fog_01_3500 # 고른 프레임의 프레임 이미지
python tools/plate_report.py                       # OCR, 평가, 집계, 비교, 이 이미지까지 한 번에 (#81)
```

| 이미지 | 내용 |
| --- | --- |
| `better.png` | `fixed`나 `adaptive`에서 `orig`보다 잘 읽힌 라벨 번호판, 많이 좋아진 순(`--top`, 기본 6개) |
| `worse.png` | `fixed`나 `adaptive`에서 `orig`보다 못 읽힌 라벨 번호판, 많이 나빠진 순 |
| `better_vs_fixed.png` | `adaptive`에서 `fixed`보다 잘 읽힌 라벨 번호판. `compare.csv`의 `fixed → adaptive` 행과 같은 비교(두 조건이 모두 있을 때) |
| `worse_vs_fixed.png` | `adaptive`에서 `fixed`보다 못 읽힌 라벨 번호판 |
| `frames/<frame>.png` | 목록에 나온 프레임(또는 `--frames`)을 조건별로 나란히, 라벨 번호판 박스와 함께 |

`results/ocr/clear.csv`가 있으면(#79) 모든 이미지 맨 앞에 `clear` 열이 붙습니다. 안개를 입히기 전 맑은 프레임과
거기서 OCR이 읽은 결과입니다. 맑은 프레임이 없는 프레임에는 `no clear frame`이라고 나옵니다. 목록은 여전히
`orig`, `fixed`, `adaptive`만 비교합니다.

- 번호판 한 줄에는 라벨, 그리고 조건마다 번호판 영역과 OCR이 읽은 글자, 문자 정확도, 판정 상태가 나옵니다.
  초록은 완전일치, 주황은 일부 맞음, 빨강은 틀림이나 놓침입니다(`missed`는 짝지어진 박스가 없음).
- `readable`로 판정됐는데 글자가 틀린 결과는 문자 정확도와 상관없이 `readable, wrong`으로 빨갛게 표시합니다.
  자신 있게 틀린 답이기 때문입니다(지표의 `readable_wrong`). 목록은 문자 정확도 순이라 이런 결과도
  좋아진 목록에 들어갈 수 있습니다. 예: uncertain `240?1974`(0.57) 대비 `24어8197`(0.86).
- 번호판 영역은 조건마다 프레임에서 라벨 박스에 사방 10 %를 더해 잘라 냅니다. 그래서 모든 열이
  같은 곳을 보여 주고, OCR이 놓친 번호판도 보입니다. 작은 번호판은 부드럽게 하지 않고 키워서
  실제 해상도가 그대로 보입니다.
- 대상은 모든 조건의 OCR CSV에 있는, 읽을 수 있는 표준 라벨 번호판입니다(`plate_details`와 같음).
  `orig`과 다른 조건 하나 이상이 있어야 하고, 없는 조건은 빠집니다.
- 프레임은 `data/frames/<cond>/`(`--frames-dir`), 라벨은 `data/labels`(`--labels`)에서 읽습니다.

이미지에는 실제 번호판이 보이므로 git이 무시하는 `results/figures/`에 저장됩니다. 발표 자료에는
`--hide N`으로 이미지와 글자의 마지막 N글자를 가리세요. 라벨 번호판만, 라벨 박스를 글자 수 비율로
나눠 가리므로 쓰기 전에 이미지를 하나씩 눈으로 확인하세요.

## 차량 (#86, #87)

같은 비교를 차량 라벨(`scenes.json`)과 [차량 검출률](plate_recognition.ko.md#차량-검출률-83)의
차량 박스로도 합니다. 비교 쌍마다 라벨 차량은 `gained`(뒤 조건에서만 찾음), `lost`(앞 조건에서만
찾음), `both`, `neither` 중 하나이므로 gained + lost + both + neither = 라벨 차량 수입니다.
`sign_p`는 gained와 lost에 같은 부호 검정을 한 값입니다. 한 프레임의 차량들은 같은 안개를 받아
완전히 독립이 아니므로, `sign_p`는 정확한 유의수준이 아니라 참고값으로 읽으세요.

```bash
python -m src.eval.vehicles      # vehicle_compare.csv, vehicles/changes.csv도 씀
python tools/compare_images.py   # 차량 라벨과 박스가 있으면 vehicles_*.png도 씀
```

| 파일 | 내용 |
| --- | --- |
| `results/vehicle_compare.csv` | 비교 쌍마다 한 행: `frames`, `labeled`, `gained`, `lost`, `both`, `neither`, `sign_p` |
| `results/vehicles/changes.csv` | 새로 찾거나 놓친 차량마다 한 행: 비교 쌍, 프레임, 크기, 박스, 앞·뒤 조건의 IoU. git이 무시하는 `results/vehicles/` 안에 있음 |
| `vehicles_better.png` | `orig`에서는 못 찾고 `fixed`나 `adaptive`에서 찾은 차량, 폭이 큰 순서 |
| `vehicles_worse.png` | `orig`에서는 찾았지만 `fixed`나 `adaptive`에서 놓친 차량 |
| `vehicles_better_vs_fixed.png`, `vehicles_worse_vs_fixed.png` | `adaptive`를 `fixed`와 같은 방식으로 비교 |

차량 행마다 라벨 크기, 그다음 조건별 차량 영역(라벨 박스에 각 변 15 % 여유)이 있고, 맑은 프레임
박스가 있으면 `clear`가 맨 앞입니다. 라벨 박스는 회색입니다. 검출 박스는 차량을 찾았으면(IoU ≥ 0.5)
초록, 못 찾았으면 빨강입니다. 놓친 차량에는 가장 많이 겹친 검출 박스를 그리므로, 너무 크거나 차의
절반만 덮은 박스가 보입니다. IoU 0.1 미만이면 다른 차의 가장자리이므로 그리지 않습니다. `--hide N`은 차량 영역 안의 라벨 번호판도 가립니다. 읽을 수 있는
라벨이 없는 번호판은 가리지 않습니다.

## 손으로 확인한 경우

`tests/test_compare.py`의 docstring에 계산 과정을 적어 두었습니다. 개선·악화·변화 없음 프레임
하나씩과 이유별로 빠진 프레임, 놓친 번호판, 번호판 두 개가 있어 변화 없음이 되는 프레임,
악화 사례의 정렬 순서를 확인합니다.
