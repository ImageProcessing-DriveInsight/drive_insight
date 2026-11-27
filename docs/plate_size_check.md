# Plate size check

[한국어](plate_size_check.ko.md)

How small and how degraded can a plate be and still be read? Measured before dashcam frames arrive,
on the real photos of C-01, shrunk to set plate widths. The photos stay outside the repo; only the
numbers are here.

```
python tools/plate_size_check.py <samples> [--test crop frame] [--widths 120 80 40] [--variants clean fog] [--reuse]
```

`<samples>` is the C-01 folder (`full/`, `crops/`, `labels.csv`). Rows with plate text go to
`<samples>/out/size_<test>.csv`, counts to `size_<test>_summary.csv`.

Samples whose label is not a real plate are skipped. 3 of the 10 photos are carmaker advertising
plates (케, 차); since the plate character check (#34) their Hangul can never be read as readable, so
the numbers below are for the **7 real plates**, with `judge` as of #34.

## Setup

- **Plate width W:** 120, 100, 80, 60, 50, 40, 30, 25, 20 px. Area averaging (each new pixel is
  the mean of the pixels it covers), like a camera farther away. Nothing is upscaled: a sample whose
  plate is narrower than 0.95·W is left out of that width, so `n` can be below 7.
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

Exact reads out of 7:

| Variant | 120 px | 100 px | 80 px | 60 px | 50 px | 40 px | 30 px | 25 px | 20 px |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| clean | 4 | 4 | 3 | 0 | 0 | 0 | 0 | 0 | 0 |
| fog | 2 | 3 | 1 | 0 | 0 | 0 | 0 | 0 | 0 |
| low_light | 1 | 1 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| blur | 1 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |

Mean char accuracy:

| Variant | 120 px | 100 px | 80 px | 60 px | 50 px | 40 px | 30 px | 25 px | 20 px |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| clean | 0.94 | 0.82 | 0.88 | 0.83 | 0.71 | 0.30 | 0.04 | 0.00 | 0.00 |
| fog | 0.86 | 0.88 | 0.74 | 0.72 | 0.42 | 0.00 | 0.00 | 0.00 | 0.00 |
| low_light | 0.77 | 0.71 | 0.67 | 0.26 | 0.08 | 0.00 | 0.00 | 0.00 | 0.00 |
| blur | 0.81 | 0.53 | 0.14 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 |

Status, readable / uncertain / unreadable:

| Variant | 120 px | 100 px | 80 px | 60 px | 50 px | 40 px | 30 px | 25 px | 20 px |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| clean | 4/3/0 | 4/2/1 | 3/4/0 | 0/7/0 | 0/6/1 | 0/3/4 | 0/1/6 | 0/0/7 | 0/0/7 |
| fog | 2/5/0 | 3/4/0 | 1/5/1 | 0/7/0 | 0/5/2 | 0/0/7 | 0/0/7 | 0/0/7 | 0/0/7 |
| low_light | 1/6/0 | 1/5/1 | 0/6/1 | 0/3/4 | 0/1/6 | 0/0/7 | 0/0/7 | 0/0/7 | 0/0/7 |
| blur | 1/6/0 | 0/5/2 | 0/2/5 | 0/0/7 | 0/0/7 | 0/0/7 | 0/0/7 | 0/0/7 | 0/0/7 |

- **The Hangul character goes first.** Below 100 px the digits are still read, but the Hangul is
  lost. `judge` then marks it `?` and the plate `uncertain`: at 60 px all 7 clean plates are
  uncertain with char accuracy 0.83, so exact reads fall long before char accuracy does.
- **Clean plates:** char accuracy holds down to 60 px (≥ 0.82) and collapses at 40 px (0.30); at
  30 px and below almost nothing is read.
- **Degraded plates need bigger plates.** Fog keeps char accuracy ≥ 0.72 down to 60 px; low light
  stays below 0.8 even at 120 px and breaks below 80 px; 5 px motion blur only works at 120 px.
- **Wrong readable reads:** none. Before the plate character check (#34), 4 of 360 reads on all 10
  photos were readable but wrong, all with a wrong Hangul (read as 에, 년, 시).

What did not help (clean, OCR text equal to the label, all 10 photos, before #34):

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

Exact reads / n:

| Variant | 120 px | 100 px | 80 px | 60 px | 50 px | 40 px | 30 px | 25 px | 20 px |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| clean | 5/5 | 4/6 | 3/6 | 2/7 | 0/7 | 0/7 | 0/7 | 0/7 | 0/7 |
| fog | 3/5 | 3/6 | 0/6 | 0/7 | 0/7 | 0/7 | 0/7 | 0/7 | 0/7 |
| low_light | 3/5 | 0/6 | 0/6 | 0/7 | 0/7 | 0/7 | 0/7 | 0/7 | 0/7 |
| blur | 0/5 | 0/6 | 0/6 | 0/7 | 0/7 | 0/7 | 0/7 | 0/7 | 0/7 |
| fog+hist_eq | 3/5 | 4/6 | 1/6 | 1/7 | 0/7 | 0/7 | 0/7 | 0/7 | 0/7 |
| low_light+gamma+hist_eq | 3/5 | 0/6 | 0/6 | 0/7 | 0/7 | 0/7 | 0/7 | 0/7 | 0/7 |

Mean char accuracy:

| Variant | 120 px | 100 px | 80 px | 60 px | 50 px | 40 px | 30 px | 25 px | 20 px |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| clean | 1.00 | 0.96 | 0.93 | 0.53 | 0.37 | 0.28 | 0.00 | 0.00 | 0.00 |
| fog | 0.92 | 0.91 | 0.85 | 0.46 | 0.25 | 0.00 | 0.00 | 0.00 | 0.00 |
| low_light | 0.94 | 0.82 | 0.78 | 0.32 | 0.04 | 0.00 | 0.00 | 0.00 | 0.00 |
| blur | 0.52 | 0.50 | 0.36 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 |
| fog+hist_eq | 0.94 | 0.89 | 0.50 | 0.39 | 0.23 | 0.00 | 0.00 | 0.00 | 0.00 |
| low_light+gamma+hist_eq | 0.91 | 0.68 | 0.52 | 0.21 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 |

Frames where YOLO found a vehicle:

| Variant | 120 px | 100 px | 80 px | 60 px | 50 px | 40 px | 30 px | 25 px | 20 px |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| clean | 5/5 | 5/6 | 6/6 | 7/7 | 5/7 | 5/7 | 4/7 | 2/7 | 0/7 |
| fog | 5/5 | 5/6 | 5/6 | 6/7 | 3/7 | 3/7 | 1/7 | 0/7 | 0/7 |
| low_light | 5/5 | 6/6 | 6/6 | 5/7 | 4/7 | 2/7 | 2/7 | 0/7 | 0/7 |
| blur | 5/5 | 5/6 | 6/6 | 6/7 | 5/7 | 5/7 | 4/7 | 3/7 | 0/7 |
| fog+hist_eq | 5/5 | 6/6 | 6/6 | 6/7 | 4/7 | 4/7 | 2/7 | 0/7 | 0/7 |
| low_light+gamma+hist_eq | 5/5 | 6/6 | 6/6 | 5/7 | 2/7 | 2/7 | 0/7 | 0/7 | 0/7 |

- **80 px and up:** clean plates are read with char accuracy ≥ 0.93, and fog with ≥ 0.85.
- **Below 80 px the full pipeline drops faster than the crop test** (0.53 vs 0.83 at 60 px). The
  found plate box is looser than a hand crop, so a small plate gets fewer pixels of text.
- **OCR is the limit, not YOLO.** On clean frames the vehicle is still found for 5 of 7 photos at
  40 px (a car about 140 px wide), but by then little is read (0.28). Fog and low light lose
  vehicles earlier (3/7 and 4/7 at 50 px).
- **Wrong readable reads:** none. Before #34 there were 3 on all 10 photos, again all a wrong Hangul
  with the right digits (read as 에, 지, 시).
- **A's ops (a preview, no denoising yet):**
  - On fog, `hist_eq` finds a few more vehicles at 30–50 px (4/7 vs 3/7 at 40 px) and gives more
    exact reads (4/6 vs 3/6 at 100 px), but char accuracy at 80 px drops (0.50 vs 0.85) because
    2 plates become unreadable.
  - On low light, gamma + `hist_eq` lowers char accuracy at every width that reads anything
    (0.52 vs 0.78 at 80 px) and finds fewer vehicles at 50 px (2/7 vs 4/7): stretching a dark frame
    also stretches its noise and JPEG blocks.
  - The plate preprocessing already stretches the contrast of each crop, so for OCR a global
    brightness change adds more noise than signal. A's pipeline denoises first (A-07), which may
    change this; on real frames the C-11 worse-case list will show it.

## Guideline for picking timestamps

For frames meant for the OCR comparison, in a 1920×1080 frame:

| Plate width | About | What to expect |
| --- | --- | --- |
| **≥ 80 px** | ≥ 4 % of the frame width | Mostly read when clean: char accuracy ≥ 0.93; exact for half at 80 px, all at 120 px. **Pick these**, the bigger the better |
| 60–80 px | 3–4 % | Mostly digits; the Hangul is often lost (`?`, `uncertain`). Char accuracy 0.53 in the frame test, 0.83 on hand crops; rarely exact |
| 40–60 px | 2–3 % | Partly read when clean (char accuracy 0.28–0.53); under fog or low light almost nothing |
| < 40 px | < 2 % | Nothing to compare: every condition scores about 0 |

- Under low light or motion blur even 80–120 px is marginal: pick the clip's largest plates there.
- With a 120° dashcam, 80 px is about 3.6 m away (90°: about 6 m): the car right in front, stopped
  or in slow traffic. Plates farther away still matter for the VLM, but they add only noise to the
  OCR comparison.
- To check a frame: at 100 % zoom the plate should be at least 80 px wide, about 1/24 of the frame width.
- Expect exact match to stay low in every condition; char accuracy is the OCR metric that can show
  a difference between `orig`, `fixed` and `adaptive`.

## Limits

- 7 real plates and one setting per degradation. Real fog is not uniform, snow adds particles, and
  rain adds drops; these settings are only a stand-in.
- The plate width in the frame test is the found box, which can be a little wider than the plate.
- A plate in a 1920×1080 frame shrinks with distance d as W ≈ f · 0.52 m / d, with f = 960 / tan(FOV / 2)
  px. For a 120° horizontal field of view, W ≈ 290 / d: 100 px at about 3 m, 60 px at about 5 m.
  For 90°, W ≈ 500 / d: 100 px at about 5 m, 60 px at about 8 m.
