# DriveInsight

Digital Image Processing Team Project 02 · Team 16 Black Box · [한국어](README.ko.md)

DriveInsight enhances dashcam frames taken in hard conditions (night, rain, fog, backlight, tunnels) and
checks whether the enhancement helps a machine, not only the eye. Every frame is processed in three
conditions and scored the same way:

| Condition | Meaning |
| --- | --- |
| `orig` | the original frame |
| `fixed` | fixed enhancement: one parameter set for every frame (h1gyeon9) |
| `adaptive` | adaptive enhancement: image quality is measured and the parameters are chosen per frame (leojuho) |

The three conditions are compared by license plate recognition and vehicle detection (sangwon5579) and by
scene summaries from a vision language model (callmeaein). The image processing operations are written in
NumPy by the team; pretrained models are used only for vehicle detection, character recognition
and the scene summaries (see [Pretrained models and own implementation](#pretrained-models-and-own-implementation)).

```text
clips / image sequences ──► original PNG frames (leojuho) ──┬─► orig
                                                             ├─► fixed enhancement (h1gyeon9) ────► fixed
                                                             └─► quality → rules → ops (leojuho) ─► adaptive
each condition ──► vehicles → plate candidates → crop preprocessing → OCR → status (sangwon5579)
               ──► scene summary (callmeaein)
all conditions ──► evaluation, aggregation, comparison, per environment condition (sangwon5579) ──► review package (leojuho)
```

## Team and modules

| Member | Module | Work |
| --- | --- | --- |
| [h1gyeon9](https://github.com/h1gyeon9) | `src/dip/` | Color conversion, histogram equalization, gamma, Gaussian and median filters, unsharp masking (NumPy), `apply_ops`, `fixed_enhance`, fixed frame batches, night data checks and frame lists |
| [leojuho](https://github.com/leojuho) | `src/io/`, `src/adaptive/`, `src/package/` | Frame and video I/O, quality measures, rule-based parameters, `adaptive_enhance`, evaluation set and labels, review packages, sensitivity runs |
| [sangwon5579](https://github.com/sangwon5579) | `src/plate/`, `src/eval/` | Vehicle and plate detection, crop preprocessing, OCR and status, OCR evaluation, aggregation, comparison, vehicle detection rate, results per environment condition |
| [callmeaein](https://github.com/callmeaein) | `src/common/`, `src/pipeline/`, `src/vlm/` | Experiment runner and timing, VLM summaries and scoring, `main.py`, project files, submission (#38) |

Interfaces, folders and the schedule are in the [team plan](docs/plan/team_plan.md), which calls the
members A, B, C and D in the order above; features and their status are in the
[feature spec](docs/plan/feature_spec.md); all notes are listed in [docs/](docs/README.md).

## Setup

Python 3.12 on Windows (the team's machines). Run every command from the repository root.

```bat
python -m venv .venv
.venv\Scripts\activate
python -m pip install -r requirements.txt
```

`requirements.txt` holds the same pins as `requirements-plate.txt`, `requirements-b.txt` and
`requirements-dip.txt` together, plus `requests` for the VLM client.

**Visual Studio:** open `DriveInsight.sln`. The project uses the `.venv` made above and starts `main.py`,
so F5 runs the whole experiment. Arguments go in Project → Properties → Debug → Script Arguments.

**VLM (scene summaries):** install [Ollama](https://ollama.com) 0.12.7 or newer, then download the model once
(about 3.3 GB) and keep Ollama running while the `vlm` step runs:

```bat
ollama pull qwen3-vl:4b-instruct
```

The model runs on the local PC, so no API key is needed or included. Another Ollama address can be set
with the `OLLAMA_URL` environment variable (default `http://localhost:11434`). Without Ollama, use
`--offline` (see [Run](#run)).

- Use one fresh virtual environment. Do not add `requirements-video-io.txt` to it: it pins
  `opencv-python-headless`, and mixing OpenCV builds can break `cv2`.
- `requirements-plate.txt` pins `pandas` and `chardet` for one team PC where newer builds were blocked.
- Model weights are downloaded on the first run: YOLO to `weights/` (ignored by git), PaddleOCR to
  `~/.paddlex/official_models/`.
- On Windows, leojuho's notes use `py` in place of `python`; both work.
- PaddleOCR installs `opencv-contrib-python` next to `opencv-python`, so `cv2` comes from the contrib
  build. This is expected; all tests pass with it.

## Data

Real clips, frames, labels and results are **not in git**: they show or spell real license plates,
and the AI Hub data may be used only by approved members. They are handed over directly between members.

```text
data/clips/                        original videos (never modified)
data/eval_set.csv                  clip, timestamp_ms, condition, source, license (leojuho merges the members' lists)
data/frames/orig/ fixed/ adaptive/ the same <clip>_<ms>.png in every condition folder
data/frames/clear/                 clear frames the synthetic fog was made from (sangwon5579's fog clips only)
data/annotations/scenes.json       labels per frame: vehicles, plates, events (leojuho's label tool)
data/annotations/aihub_vehicles.json  AI Hub vehicle labels converted for the vehicle rate (sangwon5579)
data/annotations/envs.csv          condition of each image frame, e.g. AI Hub (sangwon5579)
data/labels/plates.json            plate labels for the OCR evaluation (exported from scenes.json)
data/plate_countries.json          frames with US plates, if any
results/                           outputs, see below
package/<clip>/                    review packages
```

Frames are always `uint8` BGR arrays of shape `(H, W, 3)`. File names are identical in the three
condition folders; that is how every condition is scored on the same frames.

## Run

### One command

```bat
python main.py
```

`main.py` runs the three conditions with the steps `enhance`, `ocr` and `vlm`, then writes
`results/summary.csv`. It first stops with an error if the three condition folders do not hold the same
frame names. Existing outputs are never overwritten: OCR results, VLM files, filled sheets and packages are
kept, and only the missing ones are made.

| Command | What it does |
| --- | --- |
| `python main.py --condition fixed --steps vlm` | one condition, one step (repeat `--condition` for more) |
| `python main.py --clip <clip> --clip <clip>` | the VLM step on these clips only |
| `python main.py --offline` | never calls the VLM: reuses `results/vlm/<cond>/<clip>.json` and lists clips with no cached file |
| `python main.py --no-run --make-sheets` | blinded fact-check sheets `results/vlm/verify/s001.csv`, … with no condition names; the key is `results/vlm/verify_key.csv` |
| `python main.py --no-run --score` | scores every filled sheet (`label` = `correct`, `unsupported` or `uncheckable`) into `results/vlm/score.csv` |
| `python main.py --no-run --package <clip>` | review package `package/<clip>/summary.html` |

The enhancement step reuses the frames in `data/frames/fixed/` and `data/frames/adaptive/` (steps 4 and 5
below); it does not make them again. Give the fact checkers only the `verify/` folder, not the key.

### Steps by owner

The steps in order. Each owner runs their own step and hands over the files.

| Step | Owner | Command | Output |
| --- | --- | --- | --- |
| 1. Merge the members' lists | leojuho | `python -m tools.prepare_data member_a.csv member_b.csv member_c.csv member_d.csv` | `data/eval_set.csv` |
| 2. Extract original frames | leojuho | `python -m tools.b_cli extract` | `data/frames/orig/` |
| 3. Labels | leojuho, each owner | `python -m tools.b_labels init`, fill `scenes.json` (drafts: `python tools/label_draft.py draft`), then `python -m tools.b_labels export --require-review` | `data/annotations/scenes.json`, `data/labels/plates.json` |
| 3a. Lists of image frames | sangwon5579 | `python tools/eval_lists.py --list <member's list> <condition> ...` | `data/annotations/envs.csv`, `eval_names.csv` |
| 3b. AI Hub vehicle labels | sangwon5579 | `python tools/aihub_vehicles.py <label folders> --names data/annotations/eval_names.csv` | `data/annotations/aihub_vehicles.json` |
| 4. Fixed enhancement | h1gyeon9 | `python -m src.dip.batch` | `data/frames/fixed/`, `results/params/fixed.json` |
| 5. Adaptive enhancement | leojuho | `python -m tools.b_cli frames --apply-ops src.dip.fixed:apply_ops` | `data/frames/adaptive/`, `results/params/adaptive.json` |
| 6. Plates, vehicles, evaluation, comparison | sangwon5579 | `python tools/plate_report.py --scenes data/annotations/scenes.json data/annotations/aihub_vehicles.json` | `results/` |
| 7. Results per environment condition | sangwon5579 | `python tools/env_report.py --scenes data/annotations/scenes.json data/annotations/aihub_vehicles.json --envs data/annotations/envs.csv` | `results/by_env/` |
| 8. Scene summaries, fact check, scores | callmeaein | `python main.py --steps vlm`, then `--no-run --make-sheets`, fill the sheets, `--no-run --score` | `results/vlm/<cond>/<clip>.json`, `results/<cond>/timing.csv`, `results/<cond>/config_snapshot.json`, `results/vlm/score.csv` |
| 9. Review package | leojuho | `python -m tools.b_cli package <clip>` | `package/<clip>/summary.html` |

More tools:

```bash
python -m tools.b_cli video data/clips/<clip>.mp4 --mode adaptive   # enhanced video (also --mode fixed)
python -m tools.sensitivity --scale 0.8 1.2 --labels data/labels    # leojuho: adaptive thresholds scaled
python -m tools.audit_night_data --decode-images --output data/annotations/<report>.json   # h1gyeon9: check the night data
python -m tools.select_night_frames                                 # h1gyeon9: night frame lists by the shared rule
python -m tools.verify_fixed_batch snapshot --snapshot data/annotations/fixed_orig_snapshot.json   # h1gyeon9: before the batch
python -m tools.verify_fixed_batch verify --snapshot data/annotations/fixed_orig_snapshot.json     # h1gyeon9: after the batch
python tools/synth_fog.py make <clear clip> <out>                   # sangwon5579: synthetic fog from a clear clip
python tools/pick_frames.py scan <clip>                             # sangwon5579: timestamps by vehicle size
python tools/compare_images.py --hide 2                             # sangwon5579: slide images, last two characters hidden
```

## Outputs

| File | Content |
| --- | --- |
| `results/ocr/<cond>.csv` | one row per plate: box, crop, text, confidence, status (`readable`, `uncertain`, `unreadable`), OCR time |
| `results/ocr/ocr_summary.csv` | detection rate, exact match, character accuracy, readable but wrong, unreadable but answered readable |
| `results/summary.csv` | OCR metrics, VLM scores and step times per condition |
| `results/vlm/<cond>/<clip>.json` | VLM scene summary per clip: `vehicles`, `events` (order, content, frame), `visibility_notes`, `uncertain` |
| `results/vlm/score.csv` | one row per condition and clip: facts, correct facts, checkable, unsupported and uncheckable claims, scene accuracy, hallucination rate |
| `results/<cond>/timing.csv` | time per frame and step (`enhance_ms`, `ocr_ms`, `vlm_ms`, `total_ms`) |
| `results/<cond>/config_snapshot.json` | steps, model versions and the SHA-256 hash of the VLM prompt of the last run |
| `results/compare.csv`, `worse_cases.csv` | frames that got better or worse from `orig` to `fixed` and `fixed` to `adaptive`, with a sign test; plates that got worse |
| `results/vehicles.csv`, `vehicle_compare.csv` | vehicle detection rate by vehicle size; vehicles found or lost between conditions |
| `results/by_env/` | the same tables per environment condition (fog, low light, rain, tunnel, backlight) |
| `results/figures/` | slide images of plates and vehicles |
| `package/<clip>/summary.html` | review package: key frames, OCR, VLM, file list |

`results/ocr/`, `worse_cases.csv`, `results/vehicles/`, `results/figures/` and `results/by_env/` hold
plate texts or images of real plates and are ignored by git.

## Results so far

Fog, night and rain, 108 frames in orig, fixed and adaptive ([details](docs/eval_results.md)):

- Fog, own dashcam clips with synthetic fog (11 clips, 48 frames, 13 readable labeled plates, 222 labeled
  vehicles; [details](docs/dashcam_results.md)):
  - Character accuracy 0.81 in the foggy frames, 0.70 after fixed enhancement and 0.81 after adaptive
    enhancement. Fixed made 5 frames worse and none better (sign test p 0.0625, a direction, not proof).
  - No adaptive rule fired on these frames, so adaptive equals the original.
  - Vehicle detection rate 0.54 in fog (0.12 for vehicles under 100 px wide), 0.51 after fixed enhancement.
- Night, AI Hub (30 frames, 114 labeled vehicles in 24 of them): vehicle detection rate 0.25 in orig and
  fixed, 0.22 in adaptive. Adaptive fired on every frame.
- Rain, AI Hub (30 frames, 82 labeled vehicles): vehicle detection rate 0.10 in orig, 0.11 after fixed
  and 0.10 after adaptive.
- At night and in rain, enhancement changes 1–4 vehicles and no difference is significant. AI Hub has
  no plate text, so the plate metrics cover fog only; no night or rain plate was read.

The tunnel and backlight results follow when their frames exist, the VLM results with callmeaein's scores.

## Pretrained models and own implementation

| Part | Pretrained | Own implementation |
| --- | --- | --- |
| Image enhancement (h1gyeon9) | – | Color conversion, histogram equalization, gamma, Gaussian and median filters, unsharp masking in NumPy; fixed parameter set |
| Adaptive enhancement (leojuho) | – | Brightness, contrast, noise and sharpness measures; rule-based parameter choice |
| Frame and video I/O (leojuho) | OpenCV for reading and writing only | Timestamp extraction, output checks |
| Vehicle detection (sangwon5579) | YOLOv8n, Ultralytics 8.4.208, COCO weights, AGPL-3.0 | Class and confidence filter, camera car filter (dashboard and reflections), one box per vehicle |
| Plate detection (sangwon5579) | – | Candidate search: vertical edges, brightness, surround contrast on integral images, box growth, NMS, 4 candidates per vehicle |
| Crop preprocessing (sangwon5579) | – | Gray conversion, bilinear resize, contrast stretch, polarity, deskew, Otsu |
| OCR (sangwon5579) | PaddleOCR 3.7.0, `korean` PP-OCRv5, Apache-2.0 | Line joining, O/I fixes, normalization; US plates: number line only |
| Plate status (sangwon5579) | – | `readable` / `uncertain` / `unreadable` rules on the Korean and US plate formats |
| Evaluation (sangwon5579) | – | Matching, metrics, aggregation, comparison, sign test, results per condition, slide images |
| Scene summaries (callmeaein) | Qwen3-VL 4B Instruct (`qwen3-vl:4b-instruct`) on local Ollama, temperature 0, Apache-2.0 | Prompt, JSON schema check with one retry, merge per clip, cache, blinded claim sheets, scoring |
| Timestamp picking, synthetic fog (sangwon5579, tools only) | YOLOv8n boxes, YOLOv8n-seg masks | Near-vehicle rules; Koschmieder fog model, scattering blur with h1gyeon9's Gaussian, sensor noise |

OpenCV is used only for image and video input and output. `python tools/check_forbidden.py src/`
fails if an OpenCV processing function or a `_stub` function is left in `src/`.

## Tests

```bash
python -X utf8 -m pytest -q
python tools/check_forbidden.py src/
```

In a fresh environment: 736 passed, 3 skipped (YOLO weights not downloaded yet, Korean and Arial fonts
missing on non-Windows machines).

The tests use synthetic frames, synthetic labels and model stand-ins, so they need no data or model
download. On a Korean Windows locale, `-X utf8` is needed: two of leojuho's package tests read text with the
default encoding.

## Data sources and licenses

| Data | Use | Terms |
| --- | --- | --- |
| Own dashcam clips | fog clips (synthetic fog) and OCR | team members' own footage |
| AI Hub 71588 (night highway), 630 (driving in various weather: rain), 71570 (day highway), 71930 (upcycled from 71570: tunnel images) | enhancement, vehicle detection (vehicle polygons), scene summaries. Plates are masked, so not OCR | AI Hub terms: approved members only, not redistributed, not uploaded outside the team |
| GLARE (backlight clips) | backlight enhancement and summaries | CC BY 4.0. N. Gray et al., "GLARE: A Dataset for Traffic Sign Detection in Sun Glare," IEEE T-ITS 24(11):12323–12330, 2023, doi:10.1109/TITS.2023.3294411 |
| BDD100K (night and dusk images, if used) | OCR at night and dusk | F. Yu et al., "BDD100K: A Diverse Driving Dataset for Heterogeneous Multitask Learning," CVPR 2020; BDD100K license terms |

Model licenses are in the table above and in [docs/model_selection.md](docs/model_selection.md).
