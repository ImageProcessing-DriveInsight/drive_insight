# 라벨 초안과 확인 이미지 (ALL-02, ALL-03)

[English](label_draft.md)

`tools/label_draft.py`는 B의 라벨 템플릿으로 하는 라벨링을 빠르게 해 줍니다. 박스를 미리 채우고
프레임 위에 그려 줍니다. 라벨 하나하나는 여전히 사람이 정합니다.

## 작업 순서

```bash
python -m tools.b_labels init        # B: data/frames/orig로 템플릿 data/annotations/scenes.json 생성
python tools/label_draft.py draft    # 손대지 않은 항목에 차량·번호판 박스를 채우고 확인 이미지 생성
# scenes.json 수정(아래 표), 그다음 다시 그려서 확인
python tools/label_draft.py check    # 전체 프레임, 또는 --only day_01_3500.png
python -m tools.b_labels export      # B: OCR 평가용 data/labels/plates.json 생성
```

경로 기본값은 `data/...`입니다. `--annotations`, `--frames`, `--check`로 바꿀 수 있습니다.
`--only`는 `draft`와 `check`를 프레임 이름이나 따옴표로 감싼 패턴(`"fog_*"` 등)에 맞는 것만 처리하게 합니다.
합성 안개 프레임은 맑은 프레임으로 초안을 만들 수 있습니다:
`draft --frames data/frames/clear --only "fog_*"` ([합성 안개](synthetic_fog.ko.md)).

## 초안이 채우는 것

| 필드 | 초안 | 라벨링하는 사람 |
| --- | --- | --- |
| `vehicles` | YOLO 박스와 `class`(car, truck, bus, motorcycle) | 박스 수정, 삭제, 추가 |
| `plates` | 차량마다 `detect_plates`의 박스 하나. `status`, `text`는 `null` | 박스 수정, 번호판이 아닌 박스 삭제, 놓친 번호판 추가. `status`는 `readable`(`text`에 모든 글자, `?` 없이) 또는 `unreadable`(`text`는 `null` 그대로) |
| `events`, `visibility_notes` | 건드리지 않음 | 채움 |
| `annotator`, `annotation_status` | 건드리지 않음 | 내 이름, 다 끝나면 `complete` |

- 손대지 않은 항목만 초안을 채웁니다. `pending`이고 차량과 번호판이 비어 있는 항목입니다.
  누군가 고친 항목은 절대 바꾸지 않으니 `draft`를 다시 돌려도 안전합니다. 도는 동안 저장한 수정도 남습니다.
- 번호판 글자는 절대 미리 채우지 않습니다. 그래서 OCR 결과가 라벨에 섞이지 않습니다.
- `status`가 빈 번호판은 B의 검사기를 통과하지 못해서, 초안이 실수로 내보내질 일이 없습니다.

## 확인 이미지

| 색 | 박스 |
| --- | --- |
| 파랑 | 차량, `V0`, `V1`, ... |
| 빨강 | 아직 `status`가 빈 번호판 |
| 초록 | `readable` 번호판, 글자 표시 |
| 노랑 | `unreadable` 번호판 |

번호는 `scenes.json`의 `vehicles`, `plates` 목록 안의 순서입니다.
이미지는 `data/annotations/check/`에 저장됩니다. 실제 번호판이 보이므로 git이 무시합니다.

## 주의할 점

- 초안에는 파이프라인이 찾은 번호판만 있습니다. 번호판 박스가 없는 차량을 하나씩 보고, 번호판이 보이면 추가하세요.
  놓친 번호판이 라벨에서 빠지면 검출률이 실제보다 좋게 나옵니다.
- 초안 박스는 번호판 테두리까지 포함하거나 조금 넓을 수 있습니다. 번호판 가장자리에 맞춰 그리세요.
  평가는 작은 박스 기준 겹침으로 짝짓기 때문에([OCR 평가](ocr_evaluation.ko.md)) 몇 픽셀 차이는 결과를 바꾸지 않습니다.
- 초안 번호판 중에는 번호판이 아닌 것(사이드미러, 조명, 배경)도 있습니다. 삭제하세요.
- #88 전에는 YOLO가 차 한 대를 car와 truck으로 두 번 잡을 수 있었습니다(IoU 0.92–1.0). C의 라벨에 이런 쌍이 9개 있었고 #88에서 지웠습니다. 그 뒤에 만든 초안은 차량당 박스가 하나입니다. 그 전 초안이라면 한 차에 박스 두 개가 겹쳐 있지 않은지 확인하세요.

## 샘플 실행

샘플 사진 10장: CPU에서 모델 로딩 포함 장당 약 2초. 초안에 차량 19개, 번호판 박스 16개가 나왔습니다.
실제 번호판은 모두 박스가 있었고, 16개 중 6개는 번호판이 아니었습니다.
