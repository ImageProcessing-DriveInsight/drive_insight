# Plate size check

[한국어](plate_size_check.ko.md)

How small and how degraded can a plate be and still be read? Measured before dashcam frames arrive,
on the 10 real photos of C-01, shrunk to set plate widths. The photos stay outside the repo; only the
numbers are here.

```
python tools/plate_size_check.py <samples> [--test crop frame] [--widths 120 80 40] [--reuse]
```

`<samples>` is the C-01 folder (`full/`, `crops/`, `labels.csv`). Rows with plate text go to
`<samples>/out/size_<test>.csv`, counts to `size_<test>_summary.csv`.

## Setup

- **Plate width W:** 120, 100, 80, 60, 50, 40, 30, 25, 20 px. Area averaging (each new pixel is
  the mean of the pixels it covers), like a camera farther away. Nothing is upscaled: a sample whose
  plate is narrower than 0.95·W is left out of that width, so `n` can be below 10.
- **Degradations**, applied after shrinking (in frame pixels), then JPEG quality 75 like a video frame:

  | Variant | Model | Setting |
  | --- | --- | --- |
  | `clean` | none | |
  | `fog` | I = J·t + A·(1 − t) | t = 0.4, A = 220: plate contrast drops to 40 % |
  | `low_light` | I = J·k + noise | k = 0.2, Gaussian noise std 3 |
  | `blur` | horizontal motion blur | 5 px |

- **Crop test:** hand crops → `read_plate` (preprocess → OCR → judge). Reading only.
- **Frame test:** the full photo is shrunk so its plate is W px wide and pasted in the middle of a
  1920×1080 frame → `detect_plates` (vehicle → plate candidates → read). The plate width in the photo
  is the box `detect_plates` finds on the full photo. Also runs A's merged ops on the degraded frame
  (a preview, not A's fixed pipeline): `fog+hist_eq`, and `low_light+gamma+hist_eq` (gamma 0.5).
  They see only the photo area; the flat gray border would otherwise dominate the histogram.

## Crop test: reading only

Exact reads out of 10, with readable-but-wrong reads in brackets:

| Variant | 120 px | 100 px | 80 px | 60 px | 50 px | 40 px | 30 px | 25 px | 20 px |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| clean | 7 | 6 | 4 | 1 | 0 [1] | 0 | 0 | 0 | 0 |
| fog | 3 | 4 | 2 | 0 | 0 [1] | 0 | 0 | 0 | 0 |
| low_light | 1 [2] | 1 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| blur | 2 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |

Mean char accuracy:

| Variant | 120 px | 100 px | 80 px | 60 px | 50 px | 40 px | 30 px | 25 px | 20 px |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| clean | 0.96 | 0.86 | 0.88 | 0.86 | 0.76 | 0.40 | 0.03 | 0.00 | 0.00 |
| fog | 0.87 | 0.87 | 0.79 | 0.66 | 0.46 | 0.00 | 0.00 | 0.00 | 0.00 |
| low_light | 0.79 | 0.73 | 0.72 | 0.23 | 0.06 | 0.00 | 0.00 | 0.00 | 0.00 |
| blur | 0.84 | 0.54 | 0.16 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 |

Status, readable / uncertain / unreadable:

| Variant | 120 px | 100 px | 80 px | 60 px | 50 px | 40 px | 30 px | 25 px | 20 px |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| clean | 7/3/0 | 6/3/1 | 4/6/0 | 1/9/0 | 1/8/1 | 0/6/4 | 0/1/9 | 0/0/10 | 0/0/10 |
| fog | 3/7/0 | 4/6/0 | 2/7/1 | 0/9/1 | 1/6/3 | 0/0/10 | 0/0/10 | 0/0/10 | 0/0/10 |
| low_light | 3/7/0 | 1/8/1 | 0/9/1 | 0/4/6 | 0/1/9 | 0/0/10 | 0/0/10 | 0/0/10 | 0/0/10 |
| blur | 2/8/0 | 0/7/3 | 0/3/7 | 0/0/10 | 0/0/10 | 0/0/10 | 0/0/10 | 0/0/10 | 0/0/10 |

- **The Hangul character goes first.** Below 100 px the digits are still read, but the Hangul is lost.
  `judge` then marks it `?` and the plate `uncertain` (char accuracy about 0.86 = 7 of 8 characters),
  so exact reads fall long before char accuracy does.
- **Clean plates:** char accuracy holds down to 60 px and collapses at 40 px; at 30 px and below
  almost nothing is read.
- **Degraded plates need bigger plates.** Fog keeps char accuracy ≥ 0.79 down to 80 px; low light
  breaks below 80 px; 5 px motion blur only works at 120 px.
- **Wrong readable reads:** 4 of 360, all with a wrong Hangul (read as 에, 년, 시); one also lost a
  digit. The other wrong reads stayed `uncertain` or `unreadable`.

What did not help (clean, exact reads out of 10):

| Change | 100 px | 80 px | 60 px | 50 px |
| --- | --- | --- | --- | --- |
| Now: text detection + recognition, `TARGET_H` 64 | 6 | 4 | 1 | 0 |
| Recognition only (no text detection) | | 0 | 0 | 0 |
| No preprocessing | | 3 | 1 | 0 |
| `TARGET_H` 48 / 96 / 128 | 4 / 4 / 5 | 5 / 6 / 5 | 1 / 0 / 2 | 0 / 1 / 0 |

Recognition only reads the crop margins as text. A different resize height moves single plates
both ways, with no trend. This is the resolution limit of the OCR model, so the pipeline stays as is.

## Frame test: full pipeline

The plates in the full photos are 65–195 px wide, so the larger widths have fewer photos (`n`).

Exact reads / n, with readable-but-wrong reads in brackets:

| Variant | 120 px | 100 px | 80 px | 60 px | 50 px | 40 px | 30 px | 25 px | 20 px |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| clean | 4/5 [1] | 4/7 | 6/9 | 2/10 | 0/10 | 0/10 | 0/10 | 0/10 | 0/10 |
| fog | 3/5 | 4/7 [1] | 1/9 [1] | 0/10 | 0/10 | 0/10 | 0/10 | 0/10 | 0/10 |
| low_light | 3/5 | 0/7 | 0/9 | 0/10 | 0/10 | 0/10 | 0/10 | 0/10 | 0/10 |
| blur | 0/5 | 0/7 | 0/9 | 0/10 | 0/10 | 0/10 | 0/10 | 0/10 | 0/10 |
| fog+hist_eq | 3/5 | 5/7 | 2/9 | 1/10 | 0/10 | 0/10 | 0/10 | 0/10 | 0/10 |
| low_light+gamma+hist_eq | 3/5 | 0/7 | 0/9 | 0/10 | 0/10 | 0/10 | 0/10 | 0/10 | 0/10 |

Mean char accuracy:

| Variant | 120 px | 100 px | 80 px | 60 px | 50 px | 40 px | 30 px | 25 px | 20 px |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| clean | 0.97 | 0.93 | 0.95 | 0.63 | 0.51 | 0.37 | 0.11 | 0.00 | 0.00 |
| fog | 0.92 | 0.94 | 0.87 | 0.48 | 0.37 | 0.12 | 0.00 | 0.00 | 0.00 |
| low_light | 0.94 | 0.81 | 0.78 | 0.38 | 0.19 | 0.00 | 0.00 | 0.00 | 0.00 |
| blur | 0.52 | 0.43 | 0.31 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 |
| fog+hist_eq | 0.94 | 0.91 | 0.61 | 0.43 | 0.29 | 0.09 | 0.00 | 0.00 | 0.00 |
| low_light+gamma+hist_eq | 0.91 | 0.69 | 0.59 | 0.15 | 0.09 | 0.00 | 0.00 | 0.00 | 0.00 |

Frames where YOLO found a vehicle:

| Variant | 120 px | 100 px | 80 px | 60 px | 50 px | 40 px | 30 px | 25 px | 20 px |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| clean | 5/5 | 6/7 | 8/9 | 10/10 | 8/10 | 8/10 | 6/10 | 4/10 | 0/10 |
| fog | 5/5 | 6/7 | 7/9 | 8/10 | 5/10 | 4/10 | 2/10 | 0/10 | 0/10 |
| low_light | 5/5 | 7/7 | 8/9 | 7/10 | 6/10 | 3/10 | 3/10 | 0/10 | 0/10 |
| blur | 5/5 | 6/7 | 8/9 | 9/10 | 8/10 | 8/10 | 6/10 | 3/10 | 0/10 |
| fog+hist_eq | 5/5 | 7/7 | 9/9 | 9/10 | 7/10 | 7/10 | 4/10 | 1/10 | 0/10 |
| low_light+gamma+hist_eq | 5/5 | 7/7 | 9/9 | 8/10 | 5/10 | 4/10 | 0/10 | 0/10 | 0/10 |

- **80 px and up:** clean plates are read with char accuracy ≥ 0.93, and fog with ≥ 0.87.
- **Below 80 px the full pipeline drops faster than the crop test** (0.63 vs 0.86 at 60 px). The
  found plate box is looser than a hand crop, so a small plate gets fewer pixels of text.
- **OCR is the limit, not YOLO.** On clean frames the vehicle is still found for 8 of 10 photos at
  40 px (a car about 140 px wide), but by then almost nothing is read. Fog and low light lose
  vehicles earlier (5/10 and 6/10 at 50 px).
- **Wrong readable reads:** 3, again all a wrong Hangul with the right digits (read as 에, 지, 시).
- **A's ops (a preview, no denoising yet):**
  - On fog, `hist_eq` helps YOLO (vehicles found at 40 px: 7/10 vs 4/10) and removed the 2 wrong
    readable reads, but lowers char accuracy at 80 px and below (0.61 vs 0.87 at 80 px).
  - On low light, gamma + `hist_eq` lowers char accuracy at every width that reads anything
    (0.59 vs 0.78 at 80 px): stretching a dark frame also stretches its noise and JPEG blocks.
  - The plate preprocessing already stretches the contrast of each crop, so for OCR a global
    brightness change adds more noise than signal. A's pipeline denoises first (A-07), which may
    change this; on real frames the C-11 worse-case list will show it.

## Guideline for picking timestamps

For frames meant for the OCR comparison, in a 1920×1080 frame:

| Plate width | About | What to expect |
| --- | --- | --- |
| **≥ 80 px** | ≥ 4 % of the frame width | Mostly read when clean: char accuracy ≥ 0.93, about 2 in 3 exact. **Pick these.** |
| 60–80 px | 3–4 % | Digits only; the Hangul becomes `?`, status `uncertain`. Counts for char accuracy, rarely for exact match |
| 40–60 px | 2–3 % | Partly read; under fog or low light almost nothing |
| < 40 px | < 2 % | Nothing to compare: every condition scores about 0 |

- Under low light or motion blur even 80–120 px is marginal: pick the clip's largest plates there.
- With a 120° dashcam, 80 px is about 3.6 m away (90°: about 6 m): the car right in front, stopped
  or in slow traffic. Plates farther away still matter for the VLM, but they add only noise to the
  OCR comparison.
- To check a frame: at 100 % zoom the plate should be at least 80 px wide, about 1/24 of the frame width.
- Expect exact match to stay low in every condition; char accuracy is the OCR metric that can show
  a difference between `orig`, `fixed` and `adaptive`.

## Limits

- 10 photos and one setting per degradation. Real fog is not uniform, snow adds particles, and
  rain adds drops; these settings are only a stand-in.
- The plate width in the frame test is the found box, which can be a little wider than the plate.
- A plate in a 1920×1080 frame shrinks with distance d as W ≈ f · 0.52 m / d, with f = 960 / tan(FOV / 2)
  px. For a 120° horizontal field of view, W ≈ 290 / d: 100 px at about 3 m, 60 px at about 5 m.
  For 90°, W ≈ 500 / d: 100 px at about 5 m, 60 px at about 8 m.
