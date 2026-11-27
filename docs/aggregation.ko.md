# 전체 집계 (C-10)

[English](aggregation.md)

`aggregate(results_dir)`는 OCR 지표, VLM 점수, 단계별 시간을 합쳐
`results/summary.csv`에 조건마다 한 행으로 씁니다.

```
python -m src.eval.ocr --labels data/labels     # C-09: results/ocr/ocr_summary.csv
python -m src.eval.aggregate                    # C-10: results/summary.csv
python -m src.eval.aggregate --labels data/labels   # results/ocr/<cond>.csv를 다시 채점해서 사용
```

## 입력

모든 경로는 `results/` 아래입니다. 모든 파일에 `condition` 열이 있어야 합니다(조건별 시간 파일은 예외). 파일이 없으면 해당 열만 빈 값으로 두므로, 결과가 다 모이기 전에도 요약을 만들 수 있습니다.

| 파일 | 만드는 곳 | 쓰는 열 |
| --- | --- | --- |
| `ocr/ocr_summary.csv` | C-09 `python -m src.eval.ocr` | `plates`, `detection_rate`, `exact_match`, `char_accuracy`, `overconfident`, `readable_wrong` |
| `vlm/score.csv` | D-08 `score_vlm` | 아래 참고 |
| `timing.csv`, `<cond>/timing.csv` | D-04 실행기 | `frame`, `enhance_ms`, `ocr_ms`, `vlm_ms`, `total_ms` |
| `ocr/<cond>.csv`, `params/<cond>.json` | C-08 OCR 실행, A의 고정 보정·B의 적응형 보정 일괄 처리 | `ocr_ms`, `enhance_ms`. 시간 파일이 없는 조건에만 |

시간은 `timing.csv` 하나여도 되고, D의 실행기처럼 조건 폴더마다 하나씩(`results/fixed/timing.csv`)
있어도 됩니다. 조건별 파일에서는 `condition` 열이 없거나 비어 있어도 되고, 그때는 폴더 이름을 씁니다.
같은 조건·프레임이 두 파일에 있으면 요약을 멈춰서, 한 프레임이 두 번 세어지지 않게 합니다.

D의 실행기가 시간 파일을 쓰기 전까지, 시간 파일이 없는 조건은 단계별 로그에서 시간을 가져옵니다(#78).
`ocr_ms`는 `ocr/<cond>.csv`에서(프레임마다 한 번), `enhance_ms`는 `params/<cond>.json`에서 읽습니다.
`orig`에는 보정 단계가 없고, VLM 단계가 이 로그에 없으므로 `total_ms`는 비워 둡니다. 첫 OCR 프레임에는
모델을 불러오는 시간(약 6.5초)이 들어가 평균이 조금 올라갑니다.

### `vlm/score.csv` (D에게 제안하는 형식)

조건과 클립마다 한 행입니다. 빈 값이나 `N/A`는 값이 없다는 뜻입니다.

| 열 | 의미 |
| --- | --- |
| `condition`, `clip` | `orig`, `fixed`, `adaptive` 중 하나, 클립 ID |
| `facts`, `facts_correct` | 라벨에 있는 사실 수, 그중 VLM이 맞게 말한 수 |
| `checkable_claims`, `unsupported_claims` | 확인할 수 있는 주장 수, 그중 프레임으로 뒷받침되지 않는 수 |
| `uncheckable_claims` | 비율 계산에서 뺀 주장 수 |
| `scene_acc`, `hallucination_rate` | 그 행의 비율(개수 열이 있으면 없어도 됨) |

- 모든 행에 개수 4개가 있으면 클립을 합쳐서 계산합니다.
  장면 정확도 = Σ `facts_correct` / Σ `facts`, 환각률 = 100 × Σ `unsupported_claims` / Σ `checkable_claims`.
  사실이 많은 클립일수록 비중이 커지며, 모든 클립을 한 시트로 채점한 것과 같습니다.
- 개수가 없으면 각 행의 `scene_acc`와 `hallucination_rate`를 평균합니다. `N/A`는 건너뜁니다.
- 분모가 0인 비율은 빈 값입니다.

## `summary.csv`

| 열 | 의미 |
| --- | --- |
| `condition` | `orig`, `fixed`, `adaptive` 순서, 그 밖의 값은 뒤에. 예: 맑은 기준 `clear`([OCR 평가](ocr_evaluation.ko.md#맑은-기준-79)) |
| `plates` | 읽을 수 있는 라벨 번호판 수(OCR 비율의 분모) |
| `detection_rate`, `exact_match`, `char_accuracy` | 0–1, [ocr_evaluation.ko.md](ocr_evaluation.ko.md) 참고 |
| `overconfident`, `readable_wrong` | 개수 |
| `vlm_scene_acc` | 0–1 |
| `hallucination_rate` | 퍼센트 |
| `uncheckable_claims` | 개수, 비율과 따로 표시 |
| `enhance_ms`, `ocr_ms`, `vlm_ms`, `total_ms` | 프레임당 평균 ms. 빈 칸은 건너뜀(예: VLM을 호출하지 않은 프레임의 `vlm_ms`) |

수치는 원본 파일에서 그대로 옮기거나 합쳐서 계산하고, 소수점 4자리로 반올림합니다. 없는 값을 채워 넣지 않습니다.

## 손으로 확인한 경우

`tests/test_aggregate.py`의 docstring에 계산 과정을 적어 두었습니다. VLM 개수 합산
(0.4와 40.0. 클립별 비율을 평균하면 0.375와 37.5), 빈 칸이 있는 평균 시간, `N/A` 처리,
분모 0, 파일이 없는 경우, 조건 순서를 확인합니다.
