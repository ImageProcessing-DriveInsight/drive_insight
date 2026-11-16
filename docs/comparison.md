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

## Checked by hand

`tests/test_compare.py` works out the counts in the docstrings: one better, one worse and one
unchanged frame with frames left out for each reason, a missed plate, a two-plate frame that stays
unchanged, and the order of worse cases.
