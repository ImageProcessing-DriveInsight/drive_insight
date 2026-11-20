# Feature Spec by Member

DriveInsight · Team 16 Black Box · **updated Nov 16, 2026**

[한국어](feature_spec.ko.md) · [Team plan](team_plan.md) · [Member C guide](member_c_guide.md)

Features for members A–D with ID, input → output, requirements and checks. Frames are always `uint8` BGR `(H, W, 3)`; conditions are `orig`, `fixed`, `adaptive`. Numbers (speed, thresholds) are starting points, tuned at Integration Check 1 (11/10).

Status reflects the repository on 11/16 (C's rows: 11/20). **—** means nothing in the repo yet (work may exist outside it).

## Member A · Image processing ops

The core graded ops, implemented in NumPy. `cv2` is used only in tests to compare results. Files: `src/dip/`, `tests/`, `tools/check_forbidden.py`.

| ID | Feature | Input → output | Requirements | Check | Status |
| --- | --- | --- | --- | --- | --- |
| A-01 | Color space conversion | `bgr_to_ycrcb(img)`, `ycrcb_to_bgr(img)` | Own conversion matrices. Brightness ops only on Y to avoid color shifts | Round trip differs from the original by ≤ 2 | — |
| A-02 | Histogram equalization | `hist_eq(img) -> img` | Own 256-bin histogram and CDF normalization. Constant image returned as is | Mean absolute difference vs `cv2.equalizeHist` ≤ 1 | — |
| A-03 | Gamma correction | `gamma(img, g) -> img` | Own 256-entry LUT. `g` in 0.3–3.0, else `ValueError` | `g=1` returns the input | — |
| A-04 | Gaussian filter | `gaussian(img, ksize, sigma) -> img` | Own kernel (sums to 1), two separable 1D convolutions, reflect padding. `ksize` odd 3–9 | Difference vs `cv2.GaussianBlur` ≤ 1 | — |
| A-05 | Median filter | `median(img, ksize) -> img` | `ksize` ∈ {3, 5}. `sliding_window_view` + `np.median` | Removes salt-and-pepper noise, matches `cv2.medianBlur` | — |
| A-06 | Unsharp masking | `unsharp(img, amount, sigma, threshold) -> img` | `out = img + amount × (img − blur)`, clipped to 0–255. Skip pixels whose difference is below `threshold` to avoid noise boost | `amount=0` returns the input | — |
| A-07 | Op runner | `apply_ops(img, params) -> img` | Fixed order: denoise → gamma → equalization → unsharp. Missing keys skipped, unknown keys `ValueError`, `rules` ignored | Empty dict returns the input | — |
| A-08 | Fixed pipeline | `fixed_enhance(img) -> (img, params)` | One constant `FIXED_PARAMS` for every frame | `params` identical for two frames | — |
| A-09 | Batch fixed frames | `frames/orig/` → `frames/fixed/`, `params/fixed.json` | Keep file names, log time per frame | Same file list in both folders | — |
| A-10 | Speed-up | All ops | No Python loops, vectorized. Fast enough for B's enhanced videos | 1080p frame: Gaussian ≤ 0.5 s, median ≤ 1.5 s, full fixed pipeline ≤ 2 s | — |
| A-11 | Unit tests | `tests/test_ops.py` | Normal, edge and error inputs for A-01–A-08 | All `pytest` pass | — |
| A-12 | Forbidden-function check | `check_forbidden.py src/` → list | Finds cv2 calls other than I/O and `_stub`, prints file and line | 0 hits at Integration Check 3 and on 11/25 | — |

## Member B · Adaptive enhancement + video I/O + package

Video and file handling plus the adaptive rules. The ops themselves come from A's `apply_ops`. Files: `src/io/`, `src/adaptive/`, `src/package/`, `tools/sensitivity.py`.

| ID | Feature | Input → output | Requirements | Check | Status |
| --- | --- | --- | --- | --- | --- |
| B-01 | Frame extraction | `extract_frames(clip, timestamps) -> [png_path]` | `frames/orig/<clip>_<ms>.png` from `eval_set.csv` timestamps. OpenCV I/O only, lossless PNG | Timestamp error ≤ 1 frame, row count = file count | In review (#6) |
| B-02 | Video I/O | `read_video(path)`, `get_meta(path)`, `write_video(frames, fps, path)` | Iterator yielding one frame at a time (not the whole video in memory). fps, frame count, duration, resolution | A read-and-write copy has the same fps and frame count | In review (#6) |
| B-03 | Quality measures | `measure_quality(img) -> dict` | `brightness` (Y mean), `contrast` (Y std), `noise` (Laplacian-based σ), `sharpness` (Laplacian variance). Own convolution | Values move the right way on bright/dark and sharp/blurred samples | — |
| B-04 | Rule selection | `select_params(quality) -> params` | Rule table picking ops and strengths by metric range (e.g. brightness < 60 → `gamma 0.5`). Same input, same output. Rule IDs in `params["rules"]`, table also in `docs/rules.md` | Unit test per rule, rule IDs match between docs and code | — |
| B-05 | Adaptive pipeline | `adaptive_enhance(img) -> (img, params, quality)` | `apply_ops(img, select_params(measure_quality(img)))`. `apply_ops_stub` until 11/17 | Same rule IDs after switching from the stub | — |
| B-06 | Batch adaptive frames | `frames/orig/` → `frames/adaptive/`, `params/adaptive.json` | Log quality, params, rule IDs and time per frame | Same file list as `orig` | — |
| B-07 | Enhanced videos | `enhance_video(clip, mode) -> mp4` | `mode` is `fixed` or `adaptive`. Read and write with B-02, enhance each frame, show progress | Same fps and frame count as the original | — |
| B-08 | Review package | `build_package(clip_id) -> package/<clip>/` | Original video (copy), 2 enhanced videos, key frames per condition, plate crops and `plates.csv`, `params.json`, `vlm_summary.json`, `summary.html`. Missing results shown as "none", never stops | Original hash equals the copy; folder made for every clip | — |
| B-09 | Sensitivity script | `sensitivity.py --scale 0.8 1.2` → change table | Rebuild adaptive frames with thresholds ±20% and call C's `eval_ocr` | OCR metric table per threshold | — |

## Member C · Plate recognition + evaluation

Detection and OCR use pretrained models; crop preprocessing, candidate search, status rules and evaluation are our own. Characters that were not read are never filled in. At the end, all results are combined into a comparison between conditions. Files: `src/plate/`, `src/eval/`.

| ID | Feature | Input → output | Requirements | Check | Status |
| --- | --- | --- | --- | --- | --- |
| C-01 | Model selection | → selection memo | Compare vehicle detector, plate detector and Korean OCR on 10 Korean plate photos. Record model, version, weight source, license | Plates read out of 10 | Done (#4, #8): YOLOv8n found vehicles in 10/10; PaddleOCR read 7/10, EasyOCR 3/10. [Memo](../model_selection.md) |
| C-02 | Vehicle detection | `detect_vehicles(img) -> [{bbox, cls, conf}]` | car, truck, bus, motorcycle. `conf` ≥ 0.4. bbox `(x, y, w, h)`, largest first | Share of labeled vehicles with IoU ≥ 0.5 | Done (#10). #78: the camera car's dashboard and cars reflected on it are dropped (`own_car`). Rate on own dashcam frames (#83): 0.52 in fog, 0.12 under 100 px, relative to the clear frames |
| C-03 | Plate candidates | `detect_plate_candidates(img, vehicles) -> [bbox]` | Own: search the lower part of each vehicle box; score windows by vertical edge density and brightness against a surrounding ring (integral images); grow the best window to the full plate; top 4 per vehicle; whole frame if no vehicle | Detection rate of labeled plates | Done (#10): plate in top 3 for 10/10 real photos, first for 8/10. #71: 4 kept, since in fog the plate was 4th |
| C-04 | Crop preprocessing | `preprocess_plate(crop, binarize=False, deskew=True) -> gray crop` | Own: gray (weighted sum), resize to 64 px height (bilinear), contrast stretch, dark-text polarity, deskew ±10°, optional Otsu | OCR accuracy with and without | Done (#12): default gray + stretch + deskew; Otsu dropped reads to 2/10. [Notes](../plate_recognition.md) |
| C-05 | Text recognition | `recognize(crop) -> (text, conf)` | PaddleOCR `korean`. Join lines top to bottom for two-line plates; `O`→`0`, `I`/`l`→`1`; keep digits and Hangul; conf = lowest box score. Format `^([가-힣]{2})?\d{2,3}[가-힣]\d{4}$` (region name allowed) | Compare with labeled text | Done (#12). US plates (#69): `recognize(crop, country)` keeps letters and digits of the number line. [Notes](../plate_recognition.md#us-plates) |
| C-06 | Status | `judge(text, conf) -> (status, text)` | `readable`: format + `conf` ≥ 0.8. `uncertain`: `conf` ≥ 0.5 and either format with `conf` < 0.8, or one fix fits the format with `?` at that position. `unreadable`: anything else, `text = None`. Returns text too, since uncertain needs `?` | Unit test per status | Done (#12): no wrong read judged readable on real photos. US plates (#69): `judge(text, conf, country)`, 5–7 letters and digits with a digit |
| C-07 | Integration | `detect_plates(frame, cond=None, frame_id=None) -> [PlateResult]` | Common interface keys. One result per vehicle: read candidates in order, stop at the first readable, keep the best. Crops in `results/ocr/crops/<cond>/<frame_id>_<n>.png` | 0 missing fields | Done (#14). Optional args to confirm 11/17 |
| C-08 | Run per condition | `run_ocr(cond)`, `python -m src.plate.run <cond>`: `frames/<cond>/` → `results/ocr/<cond>.csv` | `orig`, `fixed`, `adaptive` on the same frame list. A frame with no plate keeps one empty row | Frame lists of the three CSVs match | Done (#14). Ran on 48 own dashcam frames in all three conditions, plus the `clear` reference (#78, #79). [Results](../dashcam_results.md) |
| C-09 | OCR evaluation | `eval_ocr(results, labels) -> dict`; `python -m src.eval.ocr` → `ocr_summary.csv` | Detection rate (one-to-one; overlap ≥ 0.5 of the smaller box, highest IoU first), exact match, char accuracy (1 − edit distance / length). Unreadable labels counted apart with `overconfident`; non-standard plates (advertising, military) counted apart as `nonstandard_labels`. Also `readable_wrong`, `frame_char_accuracy` for C-11. Callable from B's sensitivity script | Matches 3 hand-computed cases | Done (#16, #52). Label format in [notes](../ocr_evaluation.md), written by B's label export The `clear` reference is scored on its own frames only (#79) |
| C-10 | Aggregation | `aggregate(results_dir, labels=None) -> summary.csv`; `python -m src.eval.aggregate` | Combine OCR metrics, D's VLM scores and `timing.csv` per condition | Numbers match the source CSVs | Done (#24): VLM counts pooled over clips; a missing file leaves its columns empty. `score.csv` format proposed in [notes](../aggregation.md) Without a timing file, step times come from the OCR and enhancement logs (#78) |
| C-11 | Comparison | `compare(results_dir, labels) -> (table, cases)`; `write_compare` → `compare.csv`, `worse_cases.csv` | `orig` vs `fixed` and `fixed` vs `adaptive`: count better and worse frames. List worse cases with crop paths | Better + worse + unchanged = total frames | Done (#26): frames without a readable label or missing from a CSV are counted apart. Signature to confirm 11/17. Images for slides: `tools/compare_images.py` (#63), also adaptive against fixed, confident wrong reads in red (#73). [Notes](../comparison.md) `clear` column first in the images (#79). First real results (#78). Sign test `sign_p` (#84) |

## Member D · Experiment runner + VLM + environment

Makes sure all three conditions run on the same frames with the same settings, plus the VLM summary and scoring and an environment that runs on the grader's computer. Files: `src/common/`, `src/pipeline/`, `src/vlm/`, `main.py`.

| ID | Feature | Input → output | Requirements | Check | Status |
| --- | --- | --- | --- | --- | --- |
| D-01 | Common utils | `load_frame`, `save_frame`, `get_logger`, `Timer`, `paths` | All paths relative to the project root | Works when run from another folder | — |
| D-02 | Entry point | `main.py --condition --steps --clip` | Runner, package and aggregation from one place. No arguments runs all three conditions | `python main.py` once runs to the end | — |
| D-03 | Experiment runner | `run_experiment(condition, steps) -> results/` | `steps` from enhance, OCR, VLM. Stop with an error if the frame lists differ. Save model versions and prompt hash in `config_snapshot.json` each run | Two runs on the same input give the same result | — |
| D-04 | Timing | → `timing.csv` (frame, condition, enhance_ms, ocr_ms, vlm_ms, total_ms) | Time each step | 0 missing rows | — |
| D-05 | VLM summary | `summarize_scene(frames) -> dict` | One fixed VLM, temperature 0. Schema: `vehicles`, `events` (order, content, frame), `visibility_notes`, `uncertain`. Prompt tells the VLM not to claim plate text. On schema violation retry once, then log the failure | 100% schema pass rate | — |
| D-06 | VLM cache | → `results/vlm/<cond>/<clip>.json` | Save every response. Without an API key or with `--offline`, read the cache and still score and package | Full flow without a key | — |
| D-07 | Claim extraction | `extract_claims(vlm_json) -> verify_sheet.csv` | Split responses into checkable claims. Hide condition names and shuffle | Claims ≥ response items | — |
| D-08 | VLM scoring | `score_vlm(verify_sheet, labels) -> score.csv` | Scene accuracy = labeled facts mentioned correctly / labeled facts. Hallucination rate = unsupported / checkable claims × 100. Uncheckable claims left out and shown apart; N/A if the denominator is 0 | Matches 3 hand-computed cases | — |
| D-09 | VS project | `.sln`, `.pyproj`, `requirements.txt` | Start file `main.py`, venv linked, weights downloaded automatically or explained, no API key included | Runs with F5 in VS | — |
| D-10 | README | `README.md` | Install, run commands, offline mode, table of pretrained models vs own code | Someone outside the team runs it from the README alone | — |
| D-11 | Reproduction and submission | → `Team16_BlackBox_Src.zip` | Unzip and run in a fresh environment; check absolute paths and missing files | Runs in a fresh environment; submitted before 11/28 22:00 | — |

## All members · Data work

Three tasks that need human judgment are split by clip. Each member labels their own clips; label review and VLM fact checks go to someone else's clips. Assignments follow the data work table in the [team plan](team_plan.md).

| ID | Feature | Input → output | Requirements | Check | Status |
| --- | --- | --- | --- | --- | --- |
| ALL-01 | Clip collection | → `data/clips/`, sources and timestamps | 2–3 clips for your condition, 10–30 s each. Public datasets or own footage only. 3–5 timestamps, at least half with a visible plate. Due the morning of 11/8 | 0 missing entries when B merges `eval_set.csv` | C: 11 own clear-day clips with synthetic fog, 48 timestamps picked by vehicle size (#77, #78) |
| ALL-02 | Labeling | Own clips' original frames → `labels/*.json` | Only vehicles and events visible by eye. Plate text only when clearly readable in the frame or nearby frames, else unreadable | Passes B's schema check | C: 48 frames, 66 plates (13 readable), schema check passes; kept outside git (#78) |
| ALL-03 | Label cross review | Partner's labels → comments | A↔B, C↔D. Disagreements settled at Integration Check 2 (11/17) | Every label file marks its reviewer | — |
| ALL-04 | VLM fact check | Someone else's `verify_sheet.csv` → filled verdicts | A→B→C→D→A. Each claim correct / unsupported / uncheckable, judged against original frames and labels, condition hidden | A second person judges a 10% sample; report agreement | — |
