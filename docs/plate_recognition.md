# Plate Recognition (C-04 – C-08)

[한국어](plate_recognition.ko.md)

Crop → `preprocess_plate` (own) → `recognize` (PaddleOCR) → `judge` (own rules).

## Pipeline (C-07, C-08)

`detect_plates(frame, cond=None, frame_id=None)` gives one result per vehicle:

1. `detect_vehicles` (YOLOv8n), largest first
2. `detect_plate_candidates` for that vehicle (top 3)
3. Each candidate with a 10% border: preprocess → OCR → judge, in order, stopping at the first readable one
4. Keep the best read (status, then conf) and save its crop to `results/ocr/crops/<cond>/<frame_id>_<n>.png`

`cond` and `frame_id` are optional so `detect_plates(frame)` still works (crops then go to `crops/misc/` under a hash of the frame).
Plate crops show real plates and are ignored by git.

`python -m src.plate.run <cond>` reads `data/frames/<cond>/*.png` and writes `results/ocr/<cond>.csv`:

| Column | Meaning |
| --- | --- |
| `frame` | frame file name, e.g. `fog_01_3500.png` |
| `plate` | plate index in the frame (empty if no plate) |
| `x`, `y`, `w`, `h` | plate box |
| `crop_path` | relative to the project root |
| `text` | empty when unreadable, may contain `?` when uncertain |
| `conf` | OCR confidence |
| `status` | `readable`, `uncertain`, `unreadable`, or empty if no plate |
| `ocr_ms` | time for the whole frame |

A frame with no plate still gets one row, so the CSVs of all conditions list the same frames.

On the 10 real photos: the labeled plate was readable and exact in 7/10, the other 3 were uncertain, and no wrong read was readable. About 1.6 s per frame on CPU.
3 of the 10 turned out to be carmaker advertising plates (케, 차), which no real car carries. Since the plate character check (#34) they are uncertain: 5 of the 7 real plates are readable and exact, 2 uncertain, none wrong.

## Preprocessing (C-04)

Own implementation with NumPy:

1. Gray: BT.601 weighted sum
2. Resize to 64 px height, keep aspect ratio (bilinear)
3. Contrast stretch: 2nd–98th percentile to 0–255
4. Polarity: make text dark on a light background (minority Otsu class in the center is the text)
5. Deskew: try −10° to +10° in 0.5° steps, keep the angle whose row projection of dark pixels is most concentrated
6. Otsu binarization (optional, off by default)

Checks against OpenCV (tests only): bilinear resize differs by at most 1, Otsu threshold is identical.

### Effect on OCR

10 real plate photos (5 day, 5 night), PaddleOCR.
Run: `python tools/preprocess_check.py <samples>`

Hand-cropped plates:

| Mode | Read exactly | Char accuracy | Readable | Wrong readable | Uncertain | Unreadable |
| --- | --- | --- | --- | --- | --- | --- |
| Raw crop | 7/10 | 0.95 | 7 | 0 | 3 | 0 |
| Gray + stretch | 7/10 | 0.94 | 7 | 0 | 3 | 0 |
| Gray + stretch + deskew | 7/10 | 0.94 | 7 | 0 | 3 | 0 |
| Binary (Otsu) | 2/10 | 0.83 | 2 | 0 | 8 | 0 |

Automatic candidate crops (`detect_plate_candidates`, 46 crops):

| Mode | Plate read exactly | Readable crops | Readable but not the labeled text |
| --- | --- | --- | --- |
| Raw crop | 7/10 | 18 | 2 |
| Gray + stretch + deskew | 7/10 | 11 | 0 |
| Binary (Otsu) | 4/10 | 4 | 0 |

"Readable but not the labeled text" may include correct reads of other cars' plates, since only one plate per photo is labeled.

**Decision:** gray + stretch + deskew, no binarization.
It reads as many plates as the raw crop, and gives fewer confident reads on crops that are not the labeled plate.
Otsu binarization breaks thin strokes and loses most reads.

## Recognition (C-05)

- PaddleOCR `korean` (see [model_selection.md](model_selection.md))
- Boxes are joined top-to-bottom, then left-to-right (two-line plates)
- `O`→`0` and `I`/`l`→`1` (plates have no Latin letters), then only digits and Hangul are kept
- Confidence is the lowest box score

## Status (C-06)

| Status | Rule | Text |
| --- | --- | --- |
| readable | Full plate format and conf ≥ 0.8 | as read |
| uncertain | conf ≥ 0.5 and full format with conf < 0.8 | as read |
| uncertain | conf ≥ 0.5 and one fix makes it fit the format | `?` at the unsure position |
| unreadable | anything else | `None` |

Plate format: optional region, 2–3 digits, one use character, 4 digits (e.g. `12가3456`, `123가4567`,
`서울12바3456`). Only plate characters fit:

| Part | Characters |
| --- | --- |
| Use, private | 가 나 다 라 마 거 너 더 러 머 버 서 어 저 고 노 도 로 모 보 소 오 조 구 누 두 루 무 부 수 우 주 |
| Use, commercial (taxi, bus, truck) | 바 사 아 자 |
| Use, parcel delivery | 배 |
| Use, rental | 하 허 호 |
| Region (commercial plates) | 서울 부산 대구 인천 광주 대전 울산 세종 경기 강원 충북 충남 전북 전남 경북 경남 제주 |

Any other Hangul is a misread, so it gets `?` like any other single error. In the plate size check (#32),
every wrong read that was still judged readable had such a Hangul (read as 에, 년, 시, 지) with the
right digits; all 7 are now uncertain. Carmaker advertising plates (e.g. 케, 차) are uncertain too,
since no real car carries them.

One fix means, in order: replace one character with `?`, insert one `?`, or drop one character.
If more than one place could be wrong, the result is unreadable. No character is ever filled in.

Limit: when OCR drops the Hangul or reads it as two digits, the `?` can land one position off
(e.g. `123가4567` read as `1234567` becomes `12?4567`). This happened in 2 of the 3 uncertain photos.
These stay uncertain, never readable.

| OCR text | conf | Status | Text |
| --- | --- | --- | --- |
| `12가3456` | 0.95 | readable | `12가3456` |
| `12가3456` | 0.70 | uncertain | `12가3456` |
| `1273456` (Hangul read as 7) | 0.99 | uncertain | `12?3456` |
| `12에3456` (에 is not a plate character) | 0.95 | uncertain | `12?3456` |
| `123456` (Hangul dropped) | 0.90 | uncertain | `12?3456` |
| `12가34567` (one extra digit, could be any) | 0.90 | unreadable | `None` |
| any | < 0.5 | unreadable | `None` |
