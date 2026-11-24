# Results on the Evaluation Frames (#116)

[한국어](eval_results.ko.md)

First run on every evaluation frame received by 11/24: fog 48, night 30 and rain 30, each in orig,
fixed and adaptive. Only numbers are here. Frames, labels, crops, plate texts and slide images stay
outside git. The VLM scores and the tunnel and backlight frames are still to come.

## Setup

| | |
| --- | --- |
| Fog | 48 frames from 11 own dashcam clips with synthetic fog ([dashcam_results.md](dashcam_results.md)) |
| Night | 30 frames, AI Hub 71588, 5 scenes × 6, picked by h1gyeon9 with the team's shared rule |
| Rain | 30 frames, AI Hub 630, 5 runs × 6 (4 daytime, 1 at night), picked by leojuho with the same rule |
| Fixed | h1gyeon9's baseline for every frame: Gaussian 3×3 σ 1.0, gamma 0.75, no histogram equalization, unsharp 0.8. Fixed before this run |
| Adaptive | leojuho's rules on `develop` (`src/adaptive/`) with `apply_ops` |
| Plate labels | Fog only: 13 readable plates (C's labels). AI Hub has no plate text, so the plate metrics cover fog only |
| Vehicle labels | Fog: 222 (C's). Night and rain: AI Hub boxes converted by `tools/aihub_vehicles.py` ([#90](aihub_vehicles.md)). Night: 114 vehicles in 24 frames; the 6 frames with group labels are left out. Rain: 82 vehicles in 30 frames |
| Times | Fixed and adaptive rerun for all 108 frames on one PC (C's). The rerun frames are byte-identical to the ones evaluated, so only the times changed |

```bash
python tools/eval_lists.py --list data/manifests/a_night/evaluation_frames.csv low_light --list data/annotations/rain_eval_runs.csv rain
python tools/plate_report.py --scenes data/annotations/scenes.json data/annotations/aihub_vehicles.json
python tools/env_report.py --scenes data/annotations/scenes.json data/annotations/aihub_vehicles.json --envs data/annotations/envs.csv
```

`rain_eval_runs.csv` is leojuho's rain list (`source`, `frame`) with each frame's run from the rain
`frames.csv` as `scene`, so the VLM rows of a run can be split by condition.

## Checks before the run

- Delivered frames: the night fixed frames and the night and rain adaptive frames are pixel-identical to
  C's rerun of `fixed_enhance` and `adaptive_enhance` on `develop`. The adaptive settings match the
  rerun for all 60 frames.
- Fog: every OCR and vehicle number equals the 11/20 run ([#78](dashcam_results.md)); only the times differ.

## Plates (fog)

| | orig | fixed | adaptive | clear |
| --- | --- | --- | --- | --- |
| Exact match | 0.23 | 0.15 | 0.23 | 0.23 |
| Char accuracy | 0.81 | 0.70 | 0.81 | 0.81 |

`orig → fixed`: 5 frames worse, none better (sign test p 0.0625).

Night and rain have no plate labels. C's pipeline marked every plate result there `unreadable`, in every
condition (night 57–59, rain 35–36 plate results). Without labels this does not tell whether any of
these plates could be read.

## Vehicle detection rate

| | vehicles | orig | fixed | adaptive |
| --- | --- | --- | --- | --- |
| Fog | 222 | 0.54 (119) | 0.51 (113) | 0.54 (119) |
| Night | 114 | 0.25 (28) | 0.25 (28) | 0.22 (25) |
| Rain | 82 | 0.10 (8) | 0.11 (9) | 0.10 (8) |

By labeled width, orig (found / labeled):

| | < 100 px | 100–199 px | ≥ 200 px |
| --- | --- | --- | --- |
| Fog | 0.12 (8/65) | 0.53 (43/81) | 0.89 (68/76) |
| Night | 0.12 (9/76) | 0.50 (14/28) | 0.50 (5/10) |
| Rain | 0.00 (0/17) | 0.10 (3/31) | 0.15 (5/34) |

Vehicle by vehicle (`vehicle_compare.csv`), gained / lost (sign test p):

| | orig → fixed | fixed → adaptive |
| --- | --- | --- |
| Fog | 4 / 10 (0.18) | 10 / 4 (0.18) |
| Night | 1 / 1 (1.0) | 1 / 4 (0.38) |
| Rain | 1 / 0 (1.0) | 0 / 1 (1.0) |

Boxes that match no labeled vehicle: night 1 in each condition, rain none.

## Adaptive rules

| | frames with a rule | rules fired | brightness, contrast (median) | settings chosen |
| --- | --- | --- | --- | --- |
| Fog | 0 of 48 | none | 153, 60 | none, so adaptive equals orig |
| Night | 30 of 30 | `SH_LOW` 30, `BR_DARK` 18, `CT_LOW` 18, `BR_DIM` 12 | 8, 12 | gamma 0.5 and histogram equalization on 18, gamma 0.75 on 12, unsharp 0.8 on all |
| Rain | 30 of 30 | `SH_LOW` 25, `BR_DIM` 10, `CT_LOW` 6, `BR_DARK` 2 | 106, 38 | gamma 0.75 on 10 and 0.5 on 2, histogram equalization on 6, unsharp 0.8 on 25 |

## Step times

Mean ms per frame on C's PC:

| | fixed | adaptive | OCR orig / fixed / adaptive |
| --- | --- | --- | --- |
| Fog | 144 | 152 | 1226 / 1201 / 1224 |
| Night | 166 | 342 | 2173 / 1746 / 1609 |
| Rain | 155 | 221 | 1755 / 2016 / 1696 |

The first OCR frame of the run loads the models (6.7 s). Here it is a night frame in orig, which adds
about 190 ms to the night orig mean.

## What this shows

1. **Enhancement barely moves vehicle detection at night or in rain.** Fixed and adaptive change
   1–4 vehicles, and no difference is significant.
2. **Fixed still hurts the fog plates** (char accuracy 0.81 → 0.70), as in #78.
3. **At night, adaptive fires on every frame and finds 3 fewer vehicles.** The frames are very dark
   (median brightness 8). Against fixed it loses 4 vehicles and gains 1 (p 0.38): a direction at most.
4. **Rain is hard for the detector.** YOLO finds 0.10 of the labeled vehicles, and only 0.15 of those
   at least 200 px wide. On the two rain tuning runs (not evaluation frames), the camera-car filter
   dropped no box and the labels lined up with the vehicles (IoU 0.7–0.95). So the detector misses
   these vehicles; the matching is not at fault.
5. **No plate is read at night or in rain** in any condition.

## Caveats

- Small samples: 13 readable fog plates, and night and rain differences of 1–4 vehicles.
- Plate metrics cover fog only. Night and rain have vehicle labels but no plate text.
- The fog vehicle labels come from YOLO on the clear frames, so the fog rates are relative to those.
  The night and rain labels are AI Hub's.
- The settings were fixed before this run. Do not tune them on these results.
- The VLM columns stay empty until callmeaein's `score.csv` arrives; then `plate_report.py --skip-ocr`
  and `env_report.py` rerun without new OCR. Tunnel and backlight are added once their frames exist.
- Times are from one PC and one run, not a benchmark.
