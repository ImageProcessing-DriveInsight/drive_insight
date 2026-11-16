# Plate Recognition (C-04, C-05, C-06)

Crop → `preprocess_plate` (own) → `recognize` (PaddleOCR) → `judge` (own rules).

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

- PaddleOCR `korean` (see `docs/model_selection.md`)
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

Plate format: `^([가-힣]{2})?\d{2,3}[가-힣]\d{4}$` (optional region name, e.g. `서울12가3456`).

One fix means, in order: replace one character with `?`, insert one `?`, or drop one character.
If more than one place could be wrong, the result is unreadable. No character is ever filled in.

| OCR text | conf | Status | Text |
| --- | --- | --- | --- |
| `12가3456` | 0.95 | readable | `12가3456` |
| `12가3456` | 0.70 | uncertain | `12가3456` |
| `1273456` (Hangul read as 7) | 0.99 | uncertain | `12?3456` |
| `123456` (Hangul dropped) | 0.90 | uncertain | `12?3456` |
| `12가34567` (one extra digit, could be any) | 0.90 | unreadable | `None` |
| any | < 0.5 | unreadable | `None` |
