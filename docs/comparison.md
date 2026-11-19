# Comparison (C-11)

[한국어](comparison.ko.md)

`compare(results_dir, labels)` compares `orig` → `fixed` and `fixed` → `adaptive` frame by frame.
`write_compare` (or the CLI) writes `results/compare.csv` and `results/worse_cases.csv`.

```
python -m src.eval.aggregate                       # C-10: results/summary.csv (for metric changes)
python -m src.eval.compare --labels data/labels    # C-11: compare.csv, worse_cases.csv
```

## Better, worse, unchanged

A frame's score is the mean char accuracy of its readable labeled plates, the same value as
`frame_char_accuracy` in [ocr_evaluation.md](ocr_evaluation.md). A missed plate counts as 0.

- **better / worse:** the score went up / down in the target condition
- **unchanged:** the same score (difference ≤ 1e-9)
- Not compared, counted apart:
  - `no_readable_label`: no plate, or only plates not readable by eye
  - `missing`: the frame is not in one of the two OCR CSVs

So `better + worse + unchanged = frames`. VLM scores are per clip, not per frame, so they appear only in the metric changes.

## `compare.csv`

One row per pair.

| Column | Meaning |
| --- | --- |
| `base`, `target` | `orig` → `fixed`, `fixed` → `adaptive` |
| `frames`, `better`, `worse`, `unchanged` | compared frames and their split |
| `no_readable_label`, `missing` | frames left out |
| `delta_detection_rate`, `delta_exact_match`, `delta_char_accuracy` | target − base, from `summary.csv` |
| `delta_vlm_scene_acc`, `delta_hallucination_rate`, `delta_total_ms` | target − base, from `summary.csv` |

Counts are empty when an OCR CSV of the pair is missing. A change is empty when either value
is missing, or when there is no `summary.csv` (C-10, #24).

## `worse_cases.csv`

One row per plate whose char accuracy dropped in a worse frame, largest drop first.
Both crops are listed, so the two reads can be checked side by side.

| Column | Meaning |
| --- | --- |
| `base`, `target`, `frame` | pair and frame (file name without `.png`) |
| `label` | labeled plate text |
| `base_text`, `base_status`, `base_char_acc`, `base_crop` | read in the base condition |
| `target_text`, `target_status`, `target_char_acc`, `target_crop` | read in the target condition; empty text and crop if missed |

A frame where one plate got better and another got worse by the same amount is unchanged and not listed.
Like `results/ocr/<cond>.csv`, this file contains plate text.

## Images for slides

`tools/compare_images.py` draws the plates and frames behind these numbers.

```bash
python tools/compare_images.py                      # results/figures/: better.png, worse.png, *_vs_fixed.png, frames/
python tools/compare_images.py --hide 2             # last 2 characters of every labeled plate covered
python tools/compare_images.py --frames fog_01_3500 # frame images for chosen frames
python tools/plate_report.py                       # OCR, evaluation, aggregation, comparison and these images in one run (#81)
```

| Image | What it shows |
| --- | --- |
| `better.png` | labeled plates read better in `fixed` or `adaptive` than in `orig`, largest gain first (`--top`, default 6) |
| `worse.png` | labeled plates read worse in `fixed` or `adaptive` than in `orig`, largest loss first |
| `better_vs_fixed.png` | labeled plates read better in `adaptive` than in `fixed`, like the `fixed → adaptive` row of `compare.csv` (when both exist) |
| `worse_vs_fixed.png` | labeled plates read worse in `adaptive` than in `fixed` |
| `frames/<frame>.png` | the whole frame in each condition side by side with its labeled plate boxes, for the frames in the lists or `--frames` |

With `results/ocr/clear.csv` (#79) every image starts with a `clear` column: the clear frame the
fog was made from and what OCR read there. A frame without a clear frame says `no clear frame`.
The lists still compare only `orig`, `fixed` and `adaptive`.

- Each plate row has the label, then the plate area in every condition with what OCR read, the
  char accuracy and the status: green exact, orange partly right, red wrong or missed (`missed` =
  no box matched).
- A read judged `readable` with the wrong text says `readable, wrong` and is red, whatever its char
  accuracy: it is a confident wrong answer (`readable_wrong` in the metrics). The lists are ordered
  by char accuracy, so such a read can still be in a better list, e.g. `24어8197` (0.86) against an
  uncertain `240?1974` (0.57).
- The plate area is cut at the label box plus 10 % on each side from each condition's frame, so all
  columns show the same place, also where OCR missed the plate. Small plates are enlarged without
  smoothing, so their real resolution shows.
- The plates are the readable standard labeled plates found in every condition's OCR CSV, like
  `plate_details`. `orig` and at least one other condition are needed; a missing one is left out.
- Frames come from `data/frames/<cond>/` (`--frames-dir`), labels from `data/labels` (`--labels`).

The images show real plates and go to `results/figures/`, which git ignores. For slides, use
`--hide N` to cover the last N characters in the images and texts. It covers only labeled plates,
by the share of characters across the label box, so check every image by eye before using it.

## Checked by hand

`tests/test_compare.py` works out the counts in the docstrings: one better, one worse and one
unchanged frame with frames left out for each reason, a missed plate, a two-plate frame that stays
unchanged, and the order of worse cases.
