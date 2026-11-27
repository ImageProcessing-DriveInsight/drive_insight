# Results on the Evaluation Frames (#116, #118, #121, #125)

[한국어](eval_results.ko.md)

Every evaluation frame received by 11/27: fog 48, night 30 and rain 30 (run on 11/24), and backlight 42
(added on 11/26), each in orig, fixed and adaptive. Only numbers are here. Frames, labels, crops, plate
texts and slide images stay outside git. The VLM scores of all four environments are in. Tunnel is left
out: no tunnel frames came before the deadline.

## Setup

| | |
| --- | --- |
| Fog | 48 frames from 11 own dashcam clips with synthetic fog ([dashcam_results.md](dashcam_results.md)) |
| Night | 30 frames, AI Hub 71588, 5 scenes × 6, picked by h1gyeon9 with the team's shared rule |
| Rain | 30 frames, AI Hub 630, 5 runs × 6 (4 daytime, 1 at night), picked by leojuho with the same rule |
| Backlight | 42 frames, GLARE, 7 clips × 6, picked by callmeaein (`eval_set.csv`). US plates. 1920×1080 (24), 1280×720 (12), 720×480 (6) |
| Fixed | h1gyeon9's baseline for every frame: Gaussian 3×3 σ 1.0, gamma 0.75, no histogram equalization, unsharp 0.8. Fixed before this run |
| Adaptive | leojuho's rules on `develop` (`src/adaptive/`) with `apply_ops` |
| Plate labels | Fog only: 13 readable plates (C's labels). AI Hub has no plate text and backlight has no plate labels, so the plate metrics cover fog only |
| Vehicle labels | Fog: 222 (C's). Night and rain: AI Hub boxes converted by `tools/aihub_vehicles.py` ([#90](aihub_vehicles.md)). Night: 114 vehicles in 24 frames; the 6 frames with group labels are left out. Rain: 82 vehicles in 30 frames. Backlight: none |
| VLM | `qwen3-vl:4b-instruct` on Ollama, one request per frame, claims merged per clip. Fog, night and rain: callmeaein's runs; the claims were checked by eye against the frames (fog by leojuho), then scored by callmeaein. Backlight: the claims come from a run on C's PC with the same model and prompt (same prompt hash), checked and scored by C; the times come from callmeaein's run of the same frames |
| Times | Fixed and adaptive rerun for all 108 fog, night and rain frames on one PC (C's). The rerun frames are byte-identical to the ones evaluated, so only the times changed. The backlight fixed and adaptive frames were made on the same PC |

```bash
python tools/eval_lists.py --list data/manifests/a_night/evaluation_frames.csv low_light --list data/annotations/rain_eval_runs.csv rain --list data/annotations/backlight_eval.csv backlight
python tools/plate_report.py --scenes data/annotations/scenes.json data/annotations/aihub_vehicles.json
python tools/env_report.py --scenes data/annotations/scenes.json data/annotations/aihub_vehicles.json --envs data/annotations/envs.csv
```

`rain_eval_runs.csv` is leojuho's rain list (`source`, `frame`) with each frame's run from the rain
`frames.csv` as `scene`, so the VLM rows of a run can be split by condition. `backlight_eval.csv` is
callmeaein's backlight list with each frame's clip, and `data/plate_countries.json` marks the 7 GLARE
clips as `us`.

## Checks before the run

- Delivered frames: the night fixed frames and the night and rain adaptive frames are pixel-identical to
  C's rerun of `fixed_enhance` and `adaptive_enhance` on `develop`. The adaptive settings match the
  rerun for all 60 frames.
- Fog: every OCR and vehicle number equals the 11/20 run ([#78](dashcam_results.md)); only the times differ.
- Backlight: callmeaein's 42 PNGs match the GLARE clips in name, size and frame position. A fresh decode of
  the clips is not pixel-identical (mean difference 0.5–1.7 levels, a decoder difference), so fixed and
  adaptive were made from the PNGs, not from new frames.
- Adding backlight left every fog, night and rain number unchanged.
- Fog VLM: callmeaein's fog scores match leojuho's filled sheet (each image's counts equal one clip's
  row). Adding them left the night and rain scores and every OCR and vehicle number unchanged.
- Backlight VLM: every checkable claim has a label. Adding the backlight scores and times left the fog,
  night and rain scores and every OCR, vehicle and enhancement number unchanged.

## Plates

Fog:

| | orig | fixed | adaptive | clear |
| --- | --- | --- | --- | --- |
| Exact match | 0.23 | 0.15 | 0.23 | 0.23 |
| Char accuracy | 0.81 | 0.70 | 0.81 | 0.81 |

`orig → fixed`: 5 frames worse, none better (sign test p 0.0625).

Night and rain have no plate labels. C's pipeline marked every plate result there `unreadable`, in every
condition (night 57–59, rain 35–36 plate results). Without labels this does not tell whether any of
these plates could be read.

Backlight has no plate labels either. No plate was read in any condition. Of the 55–66 plate results
per condition, all are `unreadable` except 7 marked `readable` (orig 2, fixed 3, adaptive 2). C checked
those 7 crops by eye: all are the dashcam's date and time overlay at the bottom of one clip's frames,
not plates.

## Vehicle detection rate

| | vehicles | orig | fixed | adaptive |
| --- | --- | --- | --- | --- |
| Fog | 222 | 0.54 (119) | 0.51 (113) | 0.54 (119) |
| Night | 114 | 0.25 (28) | 0.25 (28) | 0.22 (25) |
| Rain | 82 | 0.10 (8) | 0.11 (9) | 0.10 (8) |

Backlight has no vehicle labels, so it has no rate.

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

## VLM scene summaries

Only vehicle and event claims can be checked against a frame. Weather and visibility claims count as
uncheckable and stay out of the score. The hallucination rate is unsupported / checkable claims. In
these sheets every checkable claim is a fact claim, so the scene accuracy is 1 − the hallucination rate,
and only the rate is shown.

| | checkable claims | orig | fixed | adaptive |
| --- | --- | --- | --- | --- |
| Fog | 26 / 25 / 26 | 3.8 % (1) | 4.0 % (1) | 3.8 % (1) |
| Night | 6 per condition | 33 % (2) | 33 % (2) | 50 % (3) |
| Rain | 6 per condition | 17 % (1) | 17 % (1) | 17 % (1) |
| Backlight | 20 / 19 / 20 | 20 % (4) | 21 % (4) | 20 % (4) |

Uncheckable claims: fog 17 / 15 / 17, night 4 / 2 / 1, rain 14 / 12 / 18, backlight 7 / 7 / 5
(orig / fixed / adaptive).

In fog, the one unsupported claim in each condition is a truck in `fog_05`, whose frames show a bus and
cars only. The reviewer marked 3 vehicle claims uncheckable because the vehicle could be a van or an
SUV; they count as uncheckable.

In rain, the VLM made 29 fog claims such as "heavy fog" in 12 of the 15 sheets (5 runs × 3
conditions). They are weather claims, so they are not scored, but the model takes rain for fog.

In backlight, the 4 unsupported claims are the same in each condition: a truck in 3 clips and a
motorcycle in 1. In 18 of the 126 frames the first reply repeated one word until the token limit
(orig 7, fixed 4, adaptive 7). The retry with a repeat penalty ([#124](https://github.com/ImageProcessing-DriveInsight/drive_insight/pull/124))
gave a valid reply for all 18.

## Adaptive rules

| | frames with a rule | rules fired | brightness, contrast (median) | settings chosen |
| --- | --- | --- | --- | --- |
| Fog | 0 of 48 | none | 153, 60 | none, so adaptive equals orig |
| Night | 30 of 30 | `SH_LOW` 30, `BR_DARK` 18, `CT_LOW` 18, `BR_DIM` 12 | 8, 12 | gamma 0.5 and histogram equalization on 18, gamma 0.75 on 12, unsharp 0.8 on all |
| Rain | 30 of 30 | `SH_LOW` 25, `BR_DIM` 10, `CT_LOW` 6, `BR_DARK` 2 | 106, 38 | gamma 0.75 on 10 and 0.5 on 2, histogram equalization on 6, unsharp 0.8 on 25 |
| Backlight | 5 of 42, all in one clip | `BR_DIM` 5 | 127, 74 | gamma 0.75 on 5; adaptive equals orig on the other 37 |

## Step times

Mean ms per frame on C's PC:

| | fixed | adaptive | OCR orig / fixed / adaptive |
| --- | --- | --- | --- |
| Fog | 144 | 152 | 1226 / 1201 / 1224 |
| Night | 166 | 342 | 2173 / 1746 / 1609 |
| Rain | 155 | 221 | 1755 / 2016 / 1696 |
| Backlight | 112 | 123 | 852 / 723 / 802 |

The first OCR frame of the 11/24 run loads the models (6.7 s). Here it is a night frame in orig, which
adds about 190 ms to the night orig mean. The backlight OCR ran on 11/26 after a warm-up frame, so no
backlight frame holds the load time.

VLM, mean s per frame on callmeaein's PC (orig / fixed / adaptive): fog 20.7 / 19.9 / 21.1, night
14.3 / 23.7 / 23.3, rain 19.8 / 18.6 / 21.0, backlight 21.6 / 22.0 / 25.7. Why night orig is shorter is
not known yet. The backlight gap is run-to-run spread, not the enhancement: on the 37 frames where
adaptive equals orig, adaptive still took 4.4 s longer on average. The steps ran on different PCs, so
there is no total time per frame.

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
5. **No plate is read at night, in rain or in backlight** in any condition. In backlight, the only
   `readable` results were the dashcam's date and time overlay.
6. **Adaptive rarely changes backlight frames.** It fires on 5 of 42, all in one clip.
7. **The VLM scores do not separate the conditions.** In fog the hallucination rate is about 4 % in all
   three, from the same one claim. At night it is 33 % in orig and fixed and 50 % in adaptive; in rain
   it is 17 % in all three; in backlight it is 20–21 % in all three, from the same 4 claims. With 6
   checkable claims at night and in rain, one claim moves the rate by 17 points.

## Caveats

- Small samples: 13 readable fog plates, night and rain differences of 1–4 vehicles, and 6 checkable
  VLM claims per condition at night and in rain (25–26 in fog, 19–20 in backlight).
- Plate metrics cover fog only. Night and rain have vehicle labels but no plate text; backlight has
  neither.
- The fog vehicle labels come from YOLO on the clear frames, so the fog rates are relative to those.
  The night and rain labels are AI Hub's. callmeaein reviewed C's fog labels (ALL-03) and found no problems.
- The settings were fixed before this run. Do not tune them on these results.
- The overall `summary.csv` pools the VLM counts of all environments, so use the numbers per
  environment (`results/by_env/`).
- The backlight VLM claims and times come from two runs of the same model and prompt: the claims from
  C's PC with the retry of #124, the times from callmeaein's PC. The scores and times of fog, night and
  rain come from callmeaein's runs.
- Tunnel is left out: no tunnel frames came before the deadline (11/28).
- Times are from one run on each PC, not a benchmark.
