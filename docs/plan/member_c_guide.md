# Member C Guide · Plate Recognition + Evaluation

DriveInsight · Team 16 Black Box · first version Nov 8, 2026 · **updated Nov 16, 2026**

[한국어](member_c_guide.ko.md) · [Team plan](team_plan.md) · [Feature spec](feature_spec.md)

C finds and reads vehicles and plates (`src/plate/`) and combines the three conditions' results into a comparison (`src/eval/`).

## Status (11/16)

| | |
| --- | --- |
| **Merged** | C-01 to C-08: #2, #4, #8, #10, #12, #14 |
| **In review** | C-09 OCR evaluation: #16 |
| **Ready to hand over** | `detect_plates` (D), `run_ocr` → `orig.csv` as soon as frames exist (B, D), `eval_ocr` (B) |
| **Waiting for** | Original frames and label schema (B), fixed frames (A), adaptive frames (B), VLM scores and `timing.csv` (D) |
| **Next** | C-10, C-11 with fake CSVs; labeling once the schema arrives |

## Schedule

Development and data work in one list. IDs from the feature spec in brackets. Data items are not tracked in the repo; tick them yourself.

**Weekend (11/7–11/8)**

- [ ] Upload 2–3 fog/snow clips with source, license and 3–5 timestamps; at least half with a visible plate (ALL-01)
- [x] Commit stubs: `detect_plates(frame) -> []`, `eval_ocr`, `aggregate` (#2)
- [x] Install detectors and OCR, test 10 Korean plate photos, write the selection memo (C-01, #4, #8)

**Week 1 (11/9–11/16): recognition on original frames**

- [x] 11/9–11/10 Vehicle detection `detect_vehicles` (C-02, #10)
- [ ] 11/9–11/14 Label own clips with B's schema (ALL-02) — blocked: no schema yet
- [ ] 11/10 Integration Check 1: the runner calls the stubs end to end
- [x] 11/10–11/12 Plate candidates `detect_plate_candidates` (C-03, #10)
- [x] 11/12–11/14 Own crop preprocessing `preprocess_plate` (C-04, #12)
- [x] 11/14–11/16 OCR and status `recognize`, `judge` (C-05, C-06, #12)
- [ ] 11/15–11/16 Review D's labels (ALL-03) — blocked: no labels yet
- [x] 11/16 `detect_plates` and `run_ocr` (C-07, C-08, #14)
- [ ] 11/16 `results/ocr/orig.csv`, share with D and B — waits for original frames

**Week 2 (11/17–11/24): evaluation and aggregation**

- [ ] 11/17 Integration Check 2: OCR on fixed frames, settle label disagreements (agenda below)
- [x] 11/17–11/19 OCR evaluation `eval_ocr`, callable from B's sensitivity script (C-09, #16 in review)
- [ ] 11/19–11/20 Run fixed and adaptive frames: `fixed.csv`, `adaptive.csv` (C-08)
- [ ] 11/20–11/22 VLM fact check of D's clips (ALL-04)
- [ ] 11/20–11/24 Aggregation `aggregate`, comparison `compare` (C-10, C-11); rerun VLM final scores after 11/22
- [ ] 11/24 Integration Check 3: results for three conditions fixed

**Last week (11/25–11/28)**

- [ ] Bug fixes; give D the "pretrained vs own" table below for the README
- [ ] Every item in the final checklist below

## Receive and give

| | What | Who | Due | Stand-in until then | Status 11/16 |
| --- | --- | --- | --- | --- | --- |
| Receive | Original frames `frames/orig/` | B | 11/8 | Plate photos from the web, a few frames from own clips | Not in repo; developed on 10 web photos |
| Receive | Label schema and 3 examples | B | 11/8 | – | Not in repo; plate format proposed (`docs/ocr_evaluation.md`, #16) |
| Receive | Final labels `data/labels/` | All | 11/16 | D's fake labels (`tests/fixtures/`) | Not in repo; tests use their own fake labels |
| Receive | Fixed frames `frames/fixed/` | A | 11/15 | Original frames | Not in repo |
| Receive | Adaptive frames `frames/adaptive/` | B | 11/18 | Fixed frames | Due 11/18 |
| Receive | VLM scores `results/vlm/score.csv`, `timing.csv` | D | 11/21 (final after 11/22) | Fake CSV | Due 11/21 |
| Give | `detect_plates` | D (runner) | 11/16 | Stub returning `[]` (11/8) | Merged (#14) |
| Give | OCR results and crops `results/ocr/` | B (package), D | 11/16 | – | `python -m src.plate.run orig` once frames exist |
| Give | `eval_ocr` | B (sensitivity) | 11/19 | – | In review (#16) |
| Give | `summary.csv`, comparison, worse-case list | All (report, slides) | 11/24 | – | To do |
| Give | "Pretrained vs own" table for the README | D | 11/25 | – | Ready below |

`detect_plates` always returns a list of `{"bbox", "crop_path", "text", "conf", "status"}` dicts, or an empty list when there is no plate. `cond` and `frame_id` are optional extra arguments (to confirm on 11/17).

## How to run

```bash
pip install -r requirements-plate.txt
python -m pytest tests/
python tools/model_check.py <samples>          # C-01: compare detector and OCR on samples
python tools/preprocess_check.py <samples>     # C-04: OCR with and without preprocessing
python -m src.plate.run orig                   # C-08: data/frames/orig → results/ocr/orig.csv
python -m src.eval.ocr --labels data/labels    # C-09: results/ocr/<cond>.csv → ocr_summary.csv (#16)
```

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

- `detect_vehicles`: car, truck, bus, motorcycle with `conf` ≥ 0.4, bbox `(x, y, w, h)`, largest first.
- `detect_plate_candidates` (own): search below 35% of each vehicle box; score every window by vertical edge density and brightness minus a ring around it (integral images); 8 widths × 3 aspect ratios (2:1, 3:1, 4.5:1); grow the best window while the edge profile stays dense; NMS; top 3 per vehicle.
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

### C-09 Evaluation — `src/eval/ocr.py`, `docs/ocr_evaluation.md` (#16)

- One-to-one matching with IoU ≥ 0.5, highest first; detection rate, exact match, char accuracy over readable labels.
- Unreadable labels counted apart with `overconfident`; also `readable_wrong` and `missing_frames`.
- `frame_char_accuracy` gives per-frame scores for C-11.
- Three hand-computed cases in `tests/test_ocr_eval.py`.

### C-10, C-11 Aggregation and comparison (to do)

- `summary.csv`: one row per condition with detection rate, exact match, char accuracy, overconfident, VLM scene accuracy, hallucination rate, mean time per step. Columns already fixed in `src/eval/aggregate.py`.
- Compare `orig` vs `fixed` and `fixed` vs `adaptive`. A frame is better if its char accuracy goes up, worse if it goes down, unchanged otherwise; the three counts must add up to the total.
- List worse cases with crop paths. The proposal promised not to assume enhancement always helps, so these are the strongest slides.

## Pretrained vs own implementation (for the README)

| Part | Pretrained | Own implementation |
| --- | --- | --- |
| Vehicle detection | YOLOv8n, Ultralytics 8.4.208, COCO weights, AGPL-3.0 | Class and confidence filter, box conversion and ordering |
| Plate detection | – | Candidate search: vertical edges, brightness, center-surround scores with integral images, box growing, NMS |
| Crop preprocessing | – | Gray conversion, bilinear resize, contrast stretch, polarity, deskew, Otsu |
| OCR | PaddleOCR 3.7.0, `korean` PP-OCRv5 models, Apache-2.0 | Line joining, O/I fix, text normalization |
| Status | – | readable / uncertain / unreadable rules, `?` marking |
| Evaluation | – | Matching, detection rate, exact match, char accuracy, overconfident count, aggregation, comparison |

Weights: YOLO downloads to `weights/` on first run (ignored by git); PaddleOCR downloads to `~/.paddlex/official_models/`.

## Open items for Integration Check 2 (11/17)

- `detect_plates(frame, cond=None, frame_id=None)`: keep the optional arguments; the old call still works.
- Label schema: map its plate part to the format in `docs/ocr_evaluation.md`, or change `load_labels`.
- Condition value for snow clips in `eval_set.csv`.
- Keep `data/clips/` and `data/frames/` out of git.
- Run `python -m src.plate.run orig` as soon as original frames exist.

## Risks and outcomes

| Situation | When known | Plan | Outcome |
| --- | --- | --- | --- |
| OCR reads 3 or fewer of 10 | 11/8–11/9, C-01 | Try another OCR; if still bad, focus on char accuracy | Did not happen: PaddleOCR 7/10 (EasyOCR 3/10 was dropped) |
| Plate detector misses Korean plates | 11/10–11/12, C-03 | Own edge and ratio search in vehicle boxes; else labeled boxes + OCR only | Own search used: plate in top 3 for 10/10 |
| Dashcam plates too small | 11/16, original results | Pick timestamps with bigger plates, ask B to add them | Unknown until frames arrive |
| Install or GPU problems | 11/8 | CPU and small (n) models | CPU works. On one PC: `pandas==2.2.3`, `chardet==5.2.0` (Windows Application Control), `enable_mkldnn=False` (PaddlePaddle 3.3 CPU), antivirus HTTPS scanning needs the OS cert store |
| Labels late | 11/16 | Finish `eval_ocr` with fake labels, rerun numbers later | Happening: no schema in the repo; eval done with fake labels (#16) |

## Final checklist before submission

When all of these hold before 11/25, C's part is done.

- [x] No cv2 processing functions in `src/plate/` and `src/eval/` (only `imdecode`, `imencode` for I/O)
- [x] No functions named `_stub`
- [ ] `orig.csv`, `fixed.csv`, `adaptive.csv` list exactly the same frames — needs frames
- [x] Every result row has `bbox`, `crop_path`, `text`, `conf`, `status`, and `text` is `None` when `unreadable` (tests)
- [x] `eval_ocr` matches 3 hand-computed cases (#16)
- [ ] Better + worse + unchanged = total frames in the comparison — C-11
- [x] Model name, version, weight source and license of the detector and OCR in the selection memo
- [ ] "Pretrained vs own" table given to D for the README — table ready above
- [ ] README explains how weights are downloaded — automatic in code; README is D's
- [ ] 3 better and 3 worse crop images for the slides — after C-11
