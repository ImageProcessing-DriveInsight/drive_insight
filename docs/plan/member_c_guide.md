# Member C Guide · Plate Recognition + Evaluation

DriveInsight · Team 16 Black Box · first version Nov 8, 2026 · **updated Nov 19, 2026**

[한국어](member_c_guide.ko.md) · [Team plan](team_plan.md) · [Feature spec](feature_spec.md) · [Talk script (KO)](member_c_talk.ko.md)

C finds and reads vehicles and plates (`src/plate/`) and combines the three conditions' results into a comparison (`src/eval/`).

## Status (11/23)

| | |
| --- | --- |
| **Merged** | C-01 to C-11: #2, #4, #8, #10, #12, #14, #16, #24, #26. Since then: plate size check #33, #37; plate characters #35; evaluation matching #53; label drafts #55; synthetic fog #62; slide images #64, #74; per-condition timing #66; US plates #70; four plate candidates #72; own dashcam clips and the one-command report #80; vehicle rate and sign test #85; vehicle by vehicle comparison and one box per vehicle #89; AI Hub vehicle label conversion #91; results per environment condition and several vehicle label files #93 |
| **Checked** | 11/19 rehearsal on two 1080p synthetic fog clips, then the first real run (#78): 11 own dashcam clips → 48 timestamps picked by vehicle size (#77) → synthetic fog → frames, clear references, labels → fixed and adaptive → OCR on orig, fixed, adaptive and the clear reference (#79) → evaluation, aggregation, comparison, slide images. OCR takes about 1.4–1.6 s per foggy 1080p frame |
| **Data** | 11 own clear-day clips (1 min, 1920×1080, 11/17 and 11/18) and 11 synthetic fog clips made from them, 48 frames, C's labels: 66 plates, 13 readable. All outside git. The AI Hub fog data (630, Hazy) has every plate masked (11/19). The AI Hub night, rain and tunnel data also has masked plates and no plate labels, so it cannot be used for OCR, but its vehicle region labels are the ground truth of the vehicle detection rate (#90): vehicles evaluated 21,287 in 71588 night, 5,640 in 630 rain, 1,813 in 71570, 759 in 71930 tunnel |
| **Ready to hand over** | `detect_plates` (D), `run_ocr` (B, D), `eval_ocr` (B), first real `summary.csv`, `compare.csv` and slide images ([dashcam_results.md](../dashcam_results.md)), vehicle detection rate and vehicle by vehicle comparison with slide images (#83, #86, #87), rerun in one command with `python tools/plate_report.py` (#81), AI Hub vehicle label conversion `tools/aihub_vehicles.py` (#90), results per environment condition `tools/env_report.py` (#92); C's fog clips, frames and labels by hand, not through git (D for ALL-03 and the VLM, B for the package) |
| **Waiting for** | Each condition owner's evaluation list (11/23), B's original frames and AI Hub name mapping, A's and B's enhanced frames (morning of 11/24), labels of the own frames, D's VLM scores (11/23) and runner (#38), D's review of C's labels (ALL-03) |
| **Next** | When the frames arrive, run `tools/plate_report.py` (vehicle labels: both `scenes.json` and the AI Hub conversion), then `tools/env_report.py` (`--envs` for AI Hub frames) for results per condition. Fix them at integration check 3 on 11/24 and rerun after the VLM scores for the final aggregation. Tell B that no adaptive rule fired on dashcam frames (contrast measured with the dashboard in the frame) and A that gamma 0.75 hurt plates in fog; rerun when they change; review D's labels and fact-check D's clips once they exist |

## Schedule

Development and data work in one list. IDs from the feature spec in brackets. Data items are not tracked in the repo; tick them yourself.

**Weekend (11/7–11/8)**

- [x] Upload 2–3 fog/snow clips with source, license and 3–5 timestamps; at least half with a visible plate (ALL-01) — 11 own clear-day clips with synthetic fog (#61), 48 timestamps picked by vehicle size (#77, #78); snow not synthesized. The AI Hub fog data has masked plates (11/19)
- [x] Commit stubs: `detect_plates(frame) -> []`, `eval_ocr`, `aggregate` (#2)
- [x] Install detectors and OCR, test 10 Korean plate photos, write the selection memo (C-01, #4, #8)

**Week 1 (11/9–11/16): recognition on original frames**

- [x] 11/9–11/10 Vehicle detection `detect_vehicles` (C-02, #10)
- [x] 11/9–11/14 Label own clips with B's schema (ALL-02) — 48 frames, 66 plates, 13 readable; drafts and check images with `tools/label_draft.py` (#54, #78)
- [ ] 11/10 Integration Check 1: the runner calls the stubs end to end — C's side ran end to end in the 11/19 rehearsal; D's runner (#38) is not merged yet
- [x] 11/10–11/12 Plate candidates `detect_plate_candidates` (C-03, #10)
- [x] 11/12–11/14 Own crop preprocessing `preprocess_plate` (C-04, #12)
- [x] 11/14–11/16 OCR and status `recognize`, `judge` (C-05, C-06, #12)
- [ ] 11/15–11/16 Review D's labels (ALL-03) — blocked: no labels yet
- [x] 11/16 `detect_plates` and `run_ocr` (C-07, C-08, #14)
- [x] 11/16 `results/ocr/orig.csv`, share with D and B — 48 own frames (#78); share by hand, it holds plate texts

**Week 2 (11/17–11/24): evaluation and aggregation**

- [ ] 11/17 Integration Check 2: OCR on fixed frames, settle label disagreements (agenda below) — OCR on fixed frames ran in the rehearsal; labels still to come
- [x] 11/17–11/19 OCR evaluation `eval_ocr`, callable from B's sensitivity script (C-09, #16)
- [x] 11/19–11/20 Run fixed and adaptive frames: `fixed.csv`, `adaptive.csv` (C-08) — on the 48 own frames, plus `clear.csv` (#78, #79)
- [ ] 11/20–11/22 VLM fact check of D's clips (ALL-04)
- [x] Aggregation `aggregate`, comparison `compare` with fake CSVs (C-10, C-11, #24, #26)
- [ ] 11/22–11/24 Rerun aggregation and comparison on real results, after the final VLM scores — results per condition with `tools/env_report.py` (#92) at the same time
- [ ] 11/24 Integration Check 3: results for three conditions fixed

**Last week (11/25–11/28)**

- [ ] Bug fixes; give D the "pretrained vs own" table below for the README
- [ ] Every item in the final checklist below

## Receive and give

| | What | Who | Due | Stand-in until then | Status 11/16 |
| --- | --- | --- | --- | --- | --- |
| Receive | Original frames `frames/orig/` | B | 11/8 | Plate photos from the web, a few frames from own clips | Not in repo; developed on 10 web photos |
| Receive | Label schema and 3 examples | B | 11/8 | – | Not in repo; plate format proposed ([docs/ocr_evaluation.md](../ocr_evaluation.md), #16) |
| Receive | Final labels `data/labels/` | All | 11/16 | D's fake labels (`tests/fixtures/`) | Not in repo; tests use their own fake labels |
| Receive | Fixed frames `frames/fixed/` | A | 11/15 | Original frames | Not in repo |
| Receive | Adaptive frames `frames/adaptive/` | B | 11/18 | Fixed frames | Due 11/18 |
| Receive | VLM scores `results/vlm/score.csv`, `timing.csv` | D | 11/21 (final after 11/22) | Fake CSV | Due 11/21; format proposed in [docs/aggregation.md](../aggregation.md) |
| Give | `detect_plates` | D (runner) | 11/16 | Stub returning `[]` (11/8) | Merged (#14) |
| Give | OCR results and crops `results/ocr/` | B (package), D | 11/16 | – | `python -m src.plate.run orig` once frames exist |
| Give | `eval_ocr` | B (sensitivity) | 11/19 | – | Merged (#16) |
| Give | `summary.csv`, comparison, worse-case list | All (report, slides) | 11/24 | – | Code merged (#24, #26); numbers after real results |
| Give | "Pretrained vs own" table for the README | D | 11/25 | – | Ready below |

`detect_plates` always returns a list of `{"bbox", "crop_path", "text", "conf", "status"}` dicts, or an empty list when there is no plate. `cond` and `frame_id` are optional extra arguments (to confirm on 11/17).

## How to run

```bash
pip install -r requirements-plate.txt
python -m pytest tests/
python tools/model_check.py <samples>          # C-01: compare detector and OCR on samples
python tools/preprocess_check.py <samples>     # C-04: OCR with and without preprocessing
python -m src.plate.run orig                   # C-08: data/frames/orig → results/ocr/orig.csv
python -m src.plate.run clear                  # #79: clear reference frames → results/ocr/clear.csv
python -m src.eval.ocr --labels data/labels    # C-09: results/ocr/<cond>.csv → ocr_summary.csv
python -m src.eval.aggregate                   # C-10: ocr_summary.csv, vlm/score.csv, timing.csv → summary.csv
python -m src.eval.compare                     # C-11: compare.csv, worse_cases.csv (labels: data/labels)
python -m src.eval.vehicles                    # C-02: vehicle detection rate per condition → vehicles.csv (#83), vehicle_compare.csv (#86)
python tools/label_draft.py draft              # ALL-02: box drafts in scenes.json + check images
python tools/pick_frames.py scan <clear>       # ALL-01: vehicle boxes, then `pick` for the window and timestamps (#77)
python tools/synth_fog.py make <clear> <out>   # ALL-01: foggy clip from a clear-day clip
python tools/compare_images.py                 # C-11: plate, frame and vehicle images for slides (--hide 2)
python tools/plate_report.py                   # C-08 to C-11 in one run: OCR on every condition, then evaluation to images (#81)
python tools/aihub_vehicles.py <labels> ...    # #90: AI Hub vehicle labels → data/annotations/aihub_vehicles.json
python tools/env_report.py                     # #92: plate_report results per environment condition → results/by_env/
```

With several vehicle label files, give them together to `--scenes`, e.g. `--scenes data/annotations/scenes.json data/annotations/aihub_vehicles.json`.

US plates: list their frames in `data/plate_countries.json`, e.g. `{"us": ["bdd_*"]}` ([plate_recognition.md](../plate_recognition.md#us-plates)).

`<samples>` has `full/`, `crops/` and `labels.csv` (`file,text`). Keep sample photos outside the repo.

## What was built

Detection and OCR use pretrained models. Preprocessing, candidate search, status rules and evaluation are our own, and that is C's contribution (the course FAQ asks what was added beyond pretrained models).

### C-01 Model selection — [docs/model_selection.md](../model_selection.md)

10 Korean plate photos from the web (5 day, 5 night or far), hand-cropped plates for OCR.

| Step | Choice | Result |
| --- | --- | --- |
| Vehicle detection | YOLOv8n (Ultralytics 8.4.208, COCO, AGPL-3.0) | Vehicles found in 10/10, 19 ms per image on CPU |
| Plate detection | No pretrained plate detector (unknown public weights are pickle files that can run code) | Own candidate search (C-03) |
| OCR | PaddleOCR 3.7.0 `korean` (PP-OCRv5, Apache-2.0) | 7/10 exact vs EasyOCR 3/10 |

Main OCR error: the middle Hangul read as a digit or dropped. The plate format check caught every such error.

### C-02, C-03 Detection — `src/plate/detect.py`, `src/plate/candidates.py`

- `detect_vehicles`: car, truck, bus, motorcycle with `conf` ≥ 0.4, bbox `(x, y, w, h)`, largest first, one box per vehicle: YOLO gave a vehicle seen as both car and truck two boxes, now the more confident one is kept (#88).
- Ground truth of the vehicle detection rate: B's `scenes.json` for own frames, and for AI Hub frames a file of boxes made from the vehicle polygons (`tools/aihub_vehicles.py`, #90, [notes](../aihub_vehicles.md)). Frames with a group label (cargroup and similar) are left out. Both files go to `--scenes` together; a frame in both stops the run (#92).
- `detect_plate_candidates` (own): search below 35% of each vehicle box; score every window by vertical edge density and brightness minus a ring around it (integral images); 8 widths × 3 aspect ratios (2:1, 3:1, 4.5:1); grow the best window while the edge profile stays dense; NMS; top 4 per vehicle (3 until #71).
- Real photos: plate in the top 3 for 10/10, first for 8/10. The brightness term found a plate next to a busy grille; growing fixed boxes that covered only the middle characters.

### C-04 to C-06 Recognition — [docs/plate_recognition.md](../plate_recognition.md)

- `preprocess_plate` (own): gray, bilinear resize to 64 px height, contrast stretch, dark text on a light background, deskew ±10° (most concentrated row projection), optional Otsu. Resize differs from OpenCV by ≤ 1; Otsu matches exactly (tests only).
- Preprocessing comparison: hand crops read 7/10 with raw, gray and deskew, but only 2/10 with Otsu. On automatic candidate crops, gray + stretch + deskew read as many plates as raw (7/10) with fewer confident reads on non-target crops (0 vs 2). Default: no binarization.
- `recognize`: PaddleOCR, lines joined top to bottom, `O`→`0`, `I`/`l`→`1`, digits and Hangul only, conf = lowest box score.
- `judge` (own): readable / uncertain / unreadable; one fix marks `?`; ambiguous fixes become unreadable; conf < 0.5 is always unreadable. Returns `(status, text)` instead of only status.

### C-07, C-08 Integration — `src/plate/detect.py`, `src/plate/run.py`

- One result per vehicle: read its candidates in order, stop at the first readable one, keep the best (status, then conf).
- Crops in `results/ocr/crops/<cond>/<frame_id>_<n>.png` (ignored by git).
- `results/ocr/<cond>.csv` columns: `frame, plate, x, y, w, h, crop_path, text, conf, status, ocr_ms`. A frame with no plate keeps one row, so all conditions list the same frames.
- Real photos end to end: 7/10 readable and exact, 3/10 uncertain, 0 wrong readable, about 1.6 s per frame.
  3 of the 10 are carmaker advertising plates (케, 차); with the plate character check (#34) they are uncertain, and 5 of the 7 real plates are readable and exact.

### C-09 Evaluation — `src/eval/ocr.py`, [docs/ocr_evaluation.md](../ocr_evaluation.md)

- One-to-one matching when the boxes overlap by ≥ 0.5 of the smaller box, highest IoU first; detection rate, exact match, char accuracy over readable standard labels. Non-standard plates (advertising, military) are counted apart (#52).
- Unreadable labels counted apart with `overconfident`; also `readable_wrong` and `missing_frames`.
- `frame_char_accuracy` gives per-frame scores for C-11.
- Three hand-computed cases in `tests/test_ocr_eval.py`.

### C-10 Aggregation — `src/eval/aggregate.py`, [docs/aggregation.md](../aggregation.md)

- `summary.csv`: one row per condition with plates, detection rate, exact match, char accuracy, overconfident, readable_wrong, VLM scene accuracy, hallucination rate, uncheckable claims, mean ms per step.
- VLM counts are pooled over clips when `score.csv` has them, else the row rates are averaged. A missing file leaves its columns empty, so it runs before all results exist.
- Per environment condition (#92, [notes](../env_report.md)): `tools/env_report.py` splits the `plate_report` results by the condition in `eval_set.csv` (or an `--envs` CSV) and reruns evaluation, aggregation and comparison per condition without new OCR or detection. Plate labels are split too, so plates of another condition are not counted as missed. The combined tables are `results/by_env/summary.csv` and so on, with an `env` column first. On the 48 own fog frames (one condition) they matched the pooled tables in every value.
- Hand-computed cases in `tests/test_aggregate.py`.

### C-11 Comparison — `src/eval/compare.py`, [docs/comparison.md](../comparison.md)

- `orig` → `fixed` and `fixed` → `adaptive`. A frame is better if its mean char accuracy goes up, worse if it goes down, unchanged otherwise. Frames without a readable label or missing from a CSV are counted apart, so the three counts add up to the compared frames. `sign_p` is the exact sign test on better and worse (#84): 5 to 0 gives 0.0625, so with 13 frames the results show directions.
- `compare.csv` adds metric changes from `summary.csv`. `worse_cases.csv` lists each plate that got worse with both crop paths, largest drop first. The proposal promised not to assume enhancement always helps, so these are the strongest slides.
- Hand-computed cases in `tests/test_compare.py`.
- Vehicles (#86, #87): the same pairs per labeled vehicle, gained, lost, found in both or in neither, with the sign test → `vehicle_compare.csv`, and `vehicles_*.png` for the slides. On the own clips fixed gains 4 vehicles and loses 10 of 222 (p 0.18).

## Pretrained vs own implementation (for the README)

| Part | Pretrained | Own implementation |
| --- | --- | --- |
| Vehicle detection | YOLOv8n, Ultralytics 8.4.208, COCO weights, AGPL-3.0 | Class and confidence filter, camera car filter (dashboard and reflections), one box per vehicle across classes, box conversion and ordering |
| Plate detection | – | Candidate search: vertical edges, brightness, center-surround scores with integral images, box growing, NMS, 4 candidates per vehicle |
| Crop preprocessing | – | Gray conversion, bilinear resize, contrast stretch, polarity, deskew, Otsu |
| OCR | PaddleOCR 3.7.0, `korean` PP-OCRv5 models (they also read Latin letters, used for US plates), Apache-2.0 | Line joining, O/I fix, text normalization; for US plates only the plate number line |
| Status | – | readable / uncertain / unreadable rules: Korean plate format with use characters and regions, `?` marking; US standard format |
| Evaluation | – | Matching, detection rate, exact match, char accuracy, overconfident count, clear reference, aggregation, comparison, slide images |
| Timestamp pick (tool for picking frames, not part of the pipeline) | YOLOv8n boxes | Near-vehicle rule: width, side edges, side views, same view, best window |
| Synthetic fog (tool for making clips, not part of the pipeline) | YOLOv8n-seg, Ultralytics 8.4.208, COCO weights, AGPL-3.0: vehicle masks | Fog model (Koschmieder transmission, flat-road distance, vehicle mask distance), forward-scatter blur with A's Gaussian, sensor noise |

Weights: YOLO downloads to `weights/` on first run (ignored by git), YOLOv8n-seg too (a manual download link is in [synthetic_fog.md](../synthetic_fog.md)); PaddleOCR downloads to `~/.paddlex/official_models/`.

## Open items for Integration Check 2 (11/17)

- `detect_plates(frame, cond=None, frame_id=None)`: keep the optional arguments; the old call still works.
- Label schema: map its plate part to the format in [docs/ocr_evaluation.md](../ocr_evaluation.md), or change `load_labels`.
- Condition value for snow clips in `eval_set.csv`.
- Keep `data/clips/` and `data/frames/` out of git.
- `compare(results_dir, labels)` instead of `compare(summary)`: frame counts need the OCR CSVs and labels.
- `vlm/score.csv` columns with D: counts per condition and clip ([docs/aggregation.md](../aggregation.md)).
- Result CSVs with plate text (`results/ocr/<cond>.csv`, `worse_cases.csv`): keep real ones out of git.
- Run `python -m src.plate.run orig` as soon as original frames exist.

## Risks and outcomes

| Situation | When known | Plan | Outcome |
| --- | --- | --- | --- |
| OCR reads 3 or fewer of 10 | 11/8–11/9, C-01 | Try another OCR; if still bad, focus on char accuracy | Did not happen: PaddleOCR 7/10 (EasyOCR 3/10 was dropped) |
| Plate detector misses Korean plates | 11/10–11/12, C-03 | Own edge and ratio search in vehicle boxes; else labeled boxes + OCR only | Own search used: plate in top 3 for 10/10. In the foggy rehearsal a headlight and grille outscored the plate (4th), so 4 are kept (#72) |
| Dashcam plates too small | 11/17 on shrunk photos, then original results | Pick timestamps with bigger plates, ask B to add them | Measured ([plate_size_check.md](../plate_size_check.md)): read well from 80 px wide, Hangul lost below that. On the own clips (#78) readable plates were 62–92 px: 10 of 13 lost only the Hangul (`uncertain`), with and without fog; none was read confidently wrong |
| Install or GPU problems | 11/8 | CPU and small (n) models | CPU works. On one PC: `pandas==2.2.3`, `chardet==5.2.0` (Windows Application Control), `enable_mkldnn=False` (PaddlePaddle 3.3 CPU), antivirus HTTPS scanning needs the OS cert store |
| Labels late | 11/16 | Finish `eval_ocr` with fake labels, rerun numbers later | Schema and tools exist now (B's `tools/b_labels.py`, label drafts #55); eval, aggregation and comparison done with fake files (#16, #24, #26). Labels wait for clips |
| Enhancement does not help on dashcam frames | 11/19, first real run (#78) | Tell A and B; rerun when they change | Fixed: char accuracy 0.81 → 0.70, 5 frames worse, none better. Adaptive: no rule fired, frames equal the originals; with the dashboard left out, 22 of 48 frames would be below `CT_LOW` ([dashcam_results.md](../dashcam_results.md)) |
| No public fog footage with readable plates | 11/18–11/19 | Synthetic fog on own clear-day clips (#62); check AI Hub | AI Hub fog (630, Hazy): real fog, plates masked (11/19). Synthetic fog for OCR. AI Hub's policy forbids letting unapproved people view the data and needs an agreement to take it abroad |

## Final checklist before submission

When all of these hold before 11/25, C's part is done.

- [x] No cv2 processing functions in `src/plate/` and `src/eval/` (only `imdecode`, `imencode` for I/O)
- [x] No functions named `_stub`
- [x] `orig.csv`, `fixed.csv`, `adaptive.csv` list exactly the same frames — 48 each, `missing_frames` 0 (#78)
- [x] Every result row has `bbox`, `crop_path`, `text`, `conf`, `status`, and `text` is `None` when `unreadable` (tests)
- [x] `eval_ocr` matches 3 hand-computed cases (#16)
- [x] Better + worse + unchanged = compared frames in the comparison (#26, tests)
- [x] Model name, version, weight source and license of the detector and OCR in the selection memo
- [ ] "Pretrained vs own" table given to D for the README — table ready above (updated 11/19)
- [ ] README explains how weights are downloaded — automatic in code; README is D's
- [x] 3 better and 3 worse crop images for the slides — on the own clips no plate read better in fixed or adaptive than in orig, so the better cases are vehicles: `vehicles_better.png` (4 vehicles fixed found and orig missed) and `vehicles_worse.png` (#87); `worse.png` (5 plates) and `better_vs_fixed.png` (#78)
