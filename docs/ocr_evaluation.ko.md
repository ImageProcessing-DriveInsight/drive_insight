# OCR 평가 (C-09)

[English](ocr_evaluation.md)

`eval_ocr(results, labels)`는 조건 하나를 채점합니다. `python -m src.eval.ocr`는
`results/ocr/<cond>.csv`를 모두 채점해 `results/ocr/ocr_summary.csv`를 씁니다.

## 번호판 라벨 형식(제안)

팀 라벨 스키마가 정해지기 전까지는 `data/labels/`의 JSON 파일에서 번호판 라벨을 읽습니다.
각 파일은 프레임 파일 이름과 그 프레임의 번호판 목록을 짝지어 둡니다. `text: null`은 눈으로도 읽을 수 없는 번호판입니다.
번호판이 없는 프레임은 빈 목록입니다.

```json
{
  "fog_01_3500.png": [
    {"bbox": [412, 380, 96, 28], "text": "12가3456"},
    {"bbox": [120, 402, 40, 12], "text": null}
  ],
  "fog_01_7000.png": []
}
```

실제 스키마가 오면 `src/eval/ocr.py`의 `load_labels`만 고치면 됩니다.

## 매칭

프레임마다 예측 번호판과 라벨 번호판을 IoU ≥ 0.5 조건으로 1:1로 짝짓습니다. IoU가 큰 쌍부터 짝짓습니다.

## 지표

읽을 수 있는 라벨 번호판(`text`가 null이 아님):

| 지표 | 정의 |
| --- | --- |
| `detection_rate` | 짝지어진 번호판 수 / 번호판 수 |
| `exact_match` | 짝지어졌고 라벨과 글자가 완전히 같은 번호판 수 / 번호판 수 |
| `char_accuracy` | max(0, 1 − 편집 거리 / 라벨 길이)의 평균. 놓쳤거나 글자가 없으면 0 |
| `readable_wrong` | 짝지어졌지만 readable로 판정되면서 글자가 틀린 번호판 수 |

읽을 수 없는 라벨 번호판은 위 비율에서 뺍니다.

| 지표 | 정의 |
| --- | --- |
| `unreadable_labels` | 개수 |
| `overconfident` | 그런데도 readable로 판정된 개수(지어낸 글자를 보여 주게 됨) |

그 밖에 `frames`(라벨이 있는 프레임 수), `plates`, `missing_frames`(라벨은 있는데 CSV에 없는 프레임 수)도 냅니다.
읽을 수 있는 라벨 번호판이 하나도 없으면 비율은 빈 값입니다.

`frame_char_accuracy(results, labels)`는 조건 비교(C-11)에 쓰도록 프레임별 평균 문자 정확도를 냅니다.
읽을 수 있는 라벨 번호판이 없는 프레임은 `None`입니다.

## 손으로 확인한 경우

`tests/test_ocr_eval.py`에는 손으로 계산한 3가지 경우가 docstring에 정리되어 있습니다.
과신한 답 하나가 섞인 경우, 박스를 놓치고 글자를 틀린 경우, 1:1 매칭 경우입니다.
