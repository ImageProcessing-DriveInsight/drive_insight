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

## `compare.csv`

비교 쌍마다 한 행입니다.

| 열 | 의미 |
| --- | --- |
| `base`, `target` | `orig` → `fixed`, `fixed` → `adaptive` |
| `frames`, `better`, `worse`, `unchanged` | 비교한 프레임 수와 그 분류 |
| `no_readable_label`, `missing` | 비교에서 뺀 프레임 수 |
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

## 손으로 확인한 경우

`tests/test_compare.py`의 docstring에 계산 과정을 적어 두었습니다. 개선·악화·변화 없음 프레임
하나씩과 이유별로 빠진 프레임, 놓친 번호판, 번호판 두 개가 있어 변화 없음이 되는 프레임,
악화 사례의 정렬 순서를 확인합니다.
