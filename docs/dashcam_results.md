# Results on Own Dashcam Clips (#78)

[한국어](dashcam_results.ko.md)

First real numbers for C's part: own clear-day dashcam clips with synthetic fog, read in the
original (foggy), fixed and adaptive frames, and in the clear frames the fog was made from (#79).
Only numbers are here. Clips, frames, labels, crops, slide images and plate texts stay outside git.

The rerun on 11/24 with the night and rain frames (#116, [results on the evaluation frames](eval_results.md))
gave the same OCR and vehicle numbers as below. Only the times were measured again on one PC; the new
times are there.

## Setup

| | |
| --- | --- |
| Clips | 11 own front-camera clips, 1 min each, 1920×1080 at 30.3 fps, overcast daytime on 11/17 (5) and 11/18 (6). Light drizzle: raindrops on the windshield in several clips |
| Frames | 48 timestamps, 2–5 per clip, picked by vehicle size without OCR ([frame_pick.md](frame_pick.md)); one 20 s window per clip |
| Fog | `tools/synth_fog.py`, `medium` (150 m) for the odd clips (26 frames) and `heavy` (75 m) for the even ones (22 frames), horizon 0.54 for all (the camera did not move), other settings default. Fixed before any OCR ran |
| Fixed | A's `python -m src.dip.batch`, default parameters |
| Adaptive | B's `python -m tools.b_cli frames` with A's `apply_ops` |
| Clear | the clear frames the fog was made from (`python -m src.plate.run clear`, #79) |
| Labels | C, from zoomed crops: text spelled on the clear frame, status judged on the foggy frame (`readable` only if every character can be read there). 66 plates: 13 readable (10 different plates; one car is in 3 frames), 53 unreadable. Plates narrower than about 40 px and plates hidden behind other cars are not labeled. One plate whose Hangul could not be settled at its closest clear view is labeled unreadable. Vehicles: 222, drafted by YOLO on the clear frames and checked by eye; 9 duplicate boxes of vehicles seen as both car and truck were removed after the first run (#88). Reviewed by D (ALL-03, 11/28): no problems found |

```bash
python tools/plate_report.py    # OCR on every condition, evaluation, aggregation, comparison, slide images (#81), vehicle rate and comparison (#83, #86, #87)
```

## Results

13 readable labeled plates in 48 frames:

| | clear | orig (fog) | fixed | adaptive |
| --- | --- | --- | --- | --- |
| Detection rate | 1.00 | 1.00 | 1.00 | 1.00 |
| Exact match | 0.23 (3) | 0.23 (3) | 0.15 (2) | 0.23 (3) |
| Char accuracy | 0.81 | 0.81 | 0.70 | 0.81 |
| Status: readable / uncertain / unreadable | 3 / 10 / 0 | 3 / 10 / 0 | 2 / 10 / 1 | 3 / 10 / 0 |
| `readable_wrong` | 0 | 0 | 0 | 0 |
| `overconfident` (53 unreadable labels) | 2 | 2 | 0 | 2 |
| Unreadable labels with a plate box | 35 | 28 | 20 | 28 |
| Plate results (one per vehicle found) | 221 | 125 | 118 | 125 |
| OCR ms per frame, mean / median | 2132 / 1917 | 1571 / 1483 | 1414 / 1276 | 1424 / 1421 |
| Enhancement ms per frame | | | 148 | 155 |

By fog density, char accuracy (exact reads):

| | plates | clear | orig | fixed | adaptive | plate results, clear → orig |
| --- | --- | --- | --- | --- | --- | --- |
| `medium` (150 m) | 8 | 0.88 (3) | 0.85 (3) | 0.81 (2) | 0.85 (3) | 108 → 71 |
| `heavy` (75 m) | 5 | 0.68 (0) | 0.74 (0) | 0.53 (0) | 0.74 (0) | 113 → 54 |

`compare.csv`: of the 13 frames with a readable label (35 have none), `orig → fixed` has 0 better,
5 worse and 8 unchanged; `fixed → adaptive` has 5 better, 0 worse and 8 unchanged.
Both splits have a sign test p of 0.0625 (`sign_p`, #84): with only 5 frames moving, even 5 to 0
stays above 0.05, so the direction is consistent but not proven. `worse_cases.csv` lists the 5
plates fixed made worse.

## Vehicle detection rate (#83)

222 labeled vehicles in the 48 frames, matched at IoU ≥ 0.5 (`results/vehicles.csv`). The labels
were drafted by YOLO on the clear frames, so clear is 1.00 by construction
([note](plate_recognition.md#vehicle-detection-rate-83)).

| Labeled width | vehicles | clear | orig (fog) | fixed | adaptive |
| --- | --- | --- | --- | --- | --- |
| All | 222 | 1.00 | 0.54 (119) | 0.51 (113) | 0.54 (119) |
| < 100 px | 65 | 1.00 | 0.12 (8) | 0.11 (7) | 0.12 (8) |
| 100–199 px | 81 | 1.00 | 0.53 (43) | 0.49 (40) | 0.53 (43) |
| ≥ 200 px | 76 | 1.00 | 0.89 (68) | 0.87 (66) | 0.89 (68) |

By fog density, orig (found / labeled):

| | all | < 100 px | 100–199 px | ≥ 200 px |
| --- | --- | --- | --- | --- |
| `medium` (150 m) | 0.62 (67/108) | 0.26 (8/31) | 0.62 (21/34) | 0.88 (38/43) |
| `heavy` (75 m) | 0.46 (52/114) | 0.00 (0/34) | 0.47 (22/47) | 0.91 (30/33) |

Boxes that match no labeled vehicle: 6 in orig and adaptive, 4 in fixed, none in clear.

## Vehicle by vehicle (#86)

`vehicle_compare.csv`: of the 222 labeled vehicles, `orig → fixed` gains 4 and loses 10, with 109
found in both and 99 in neither (sign test p 0.18). `fixed → adaptive` is the mirror image, since
the adaptive frames equal the originals.

- Gained (`vehicles_better.png`): 3 vehicles 100–199 px wide and 1 under 100 px, in 4 frames. In
  orig, 3 had no box near them and 1 had a box on its front half only (IoU 0.35; a pole splits the
  car in two).
- Lost (`vehicles_worse.png`): 6 vehicles 100–199 px wide, 2 under 100 px and 2 of at least 200 px,
  in 9 frames. Fixed had no box on 9 of them. On the widest, a truck close ahead, it boxed only
  the car in front of the truck (IoU 0.12).

So fixed enhancement also has improvement cases on the own clips, at the vehicle level, but it
loses more vehicles than it gains, also among the near ones.

## What this shows

1. **Near plates read the same with and without fog; the Hangul is the limit.** The readable
   labeled plates are 62–92 px wide (median 70). Clear and foggy frames give the same char
   accuracy (0.81), and 10 of 13 are `uncertain` in both: the digits are read, the Hangul becomes
   `?`. The [plate size check](plate_size_check.md) found the Hangul lost below 100 px, and the
   wide dashcam lens puts a car's plate below that unless it is a few meters ahead. On development
   frames outside the evaluation windows, reading the raw crop or a 3× cubic enlargement instead of
   C's preprocessing did not bring the Hangul back either. No plate was read confidently wrong.
2. **Fog costs the far vehicles.** YOLO finds 0.54 of the labeled vehicles in fog: 0.89 of those
   at least 200 px wide but 0.12 of those under 100 px, and none of the 34 small ones in `heavy`
   fog. Plate results fall from 221 in the clear frames to 125 in the foggy ones (`medium` −34 %,
   `heavy` −52 %). Of the 53 plates labeled unreadable, 35 got a box in the clear frames and 28 in
   fog. The label rule keeps these plates out of the plate rates, so those do not show this loss;
   the vehicle rate and the counts do.
3. **Fixed enhancement hurts in fog.** Char accuracy drops from 0.81 to 0.70 (`heavy` 0.74 → 0.53):
   5 frames worse, none better (sign test p 0.0625), one plate turned `unreadable`, vehicle rate
   0.54 → 0.51 (4 vehicles gained, 10 lost, sign test p 0.18), 8 fewer boxes on unreadable labels. Gamma 0.75 brightens frames that fog has already made bright (brightness median 154), so
   the plates lose contrast (`results/figures/worse.png`).
4. **Adaptive did nothing.** No rule fired on any of the 48 frames, so the adaptive frames equal
   the originals pixel for pixel. B's whole-frame contrast was 48–73 (median 60), above the
   `CT_LOW` limit of 35, because the dark dashboard fills the bottom quarter of a dashcam frame and
   the fog brightens the rest. Measured on rows 0–799 (above the dashboard), the same frames have a
   median contrast of 37 and 22 of 48 are below 35; the clear frames there have 84. Suggestion for
   B: measure frame quality above the hood line.
5. **Two overconfident reads.** One is the plate whose Hangul the labeler could not settle; OCR read
   the letter the labeler leaned toward. The other is a truck plate labeled unreadable (55 px, its
   Hangul not readable in fog). Plate labels were fixed before any OCR ran and were not changed afterwards; only the 9 duplicate
   vehicle boxes were removed (#88).
6. **No confident reads on non-plates.** In the label drafts, plate boxes also landed on lettering
   on trucks, a company sticker and a carmaker logo, but no condition has a `readable` read without
   a labeled plate.

## Caveats

- 13 readable plates (10 different plates, the 3 exact reads from 2 cars), so one plate is 0.08 of
  exact match. The numbers show directions, not small differences.
- The fog is synthetic. A vehicle gets the fog of the distance where it meets the road, so near
  plates get little fog: at 10 m, `medium` keeps 0.77 and `heavy` 0.59 of the light.
- One labeler (C), reviewed by D (ALL-03), who found no problems.
- The vehicle labels come from YOLO on the clear frames, so vehicles it missed there are not
  counted: the fog vehicle rates are relative to the clear frames, not to every vehicle on the road.
- The fog clips were made before cars reflected on the dashboard were dropped from the vehicle
  masks (#78); those masks only touch the dashboard. OCR ran after the change.
- The first OCR frame of each run includes loading the models (about 6.5 s), which raises the mean
  a little. The clear run takes longer because it finds more vehicles. The times are from the rerun
  after #88: before it, a vehicle seen as car and truck was searched and read twice (orig 1654 ms
  per frame then, 1571 now). No OCR metric changed.
- The vehicles of one frame share its fog, so they are not fully independent; read the vehicle
  sign test as a guide.
