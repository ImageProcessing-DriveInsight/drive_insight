# Aggregation (C-10)

[한국어](aggregation.ko.md)

`aggregate(results_dir)` merges OCR metrics, VLM scores and step times into
`results/summary.csv`, one row per condition.

```
python -m src.eval.ocr --labels data/labels     # C-09: results/ocr/ocr_summary.csv
python -m src.eval.aggregate                    # C-10: results/summary.csv
python -m src.eval.aggregate --labels data/labels   # score results/ocr/<cond>.csv again instead
```

## Inputs

All paths are under `results/`. Every file needs a `condition` column (except per-condition timing files). A missing file leaves its columns empty, so the summary can be built before all results exist.

| File | From | Used columns |
| --- | --- | --- |
| `ocr/ocr_summary.csv` | C-09 `python -m src.eval.ocr` | `plates`, `detection_rate`, `exact_match`, `char_accuracy`, `overconfident`, `readable_wrong` |
| `vlm/score.csv` | D-08 `score_vlm` | see below |
| `timing.csv`, `<cond>/timing.csv` | D-04 runner | `frame`, `enhance_ms`, `ocr_ms`, `vlm_ms`, `total_ms` |
| `ocr/<cond>.csv`, `params/<cond>.json` | C-08 OCR run; A's fixed batch, B's adaptive batch | `ocr_ms`; `enhance_ms`, only for a condition without a timing file |

Timing can be one `timing.csv` or one file per condition folder, as D's runner writes it
(`results/fixed/timing.csv`). In a per-condition file the `condition` column may be missing or
empty; the folder name is used. The same condition and frame in two files stops the summary,
so no frame is counted twice.

Until D's runner writes timing files, a condition without one takes its step times from the stage
logs (#78): `ocr_ms` from `ocr/<cond>.csv` (once per frame) and `enhance_ms` from
`params/<cond>.json`. `orig` has no enhancement step, and `total_ms` stays empty because the VLM
step is not in these logs. The first OCR frame includes loading the models (about 6.5 s), so it raises
the mean a little.

### `vlm/score.csv` (proposal for D)

One row per condition and clip. Empty or `N/A` means not available.

| Column | Meaning |
| --- | --- |
| `condition`, `clip` | `orig`, `fixed` or `adaptive`; clip ID |
| `facts`, `facts_correct` | labeled facts; those the VLM mentioned correctly |
| `checkable_claims`, `unsupported_claims` | claims that could be checked; those not supported by the frames |
| `uncheckable_claims` | claims left out of the rates |
| `scene_acc`, `hallucination_rate` | rates of this row (optional when the counts are there) |

- With the four counts in every row, they are pooled over clips:
  scene acc = Σ `facts_correct` / Σ `facts`, hallucination rate = 100 × Σ `unsupported_claims` / Σ `checkable_claims`.
  A clip with more facts weighs more, the same as scoring all clips as one sheet.
- Without them, the `scene_acc` and `hallucination_rate` of the rows are averaged, skipping `N/A`.
- A rate with a denominator of 0 is empty.

## `summary.csv`

| Column | Meaning |
| --- | --- |
| `condition` | `orig`, `fixed`, `adaptive` first, then any other value found |
| `plates` | readable labeled plates (denominator of the OCR rates) |
| `detection_rate`, `exact_match`, `char_accuracy` | 0–1, see [ocr_evaluation.md](ocr_evaluation.md) |
| `overconfident`, `readable_wrong` | counts |
| `vlm_scene_acc` | 0–1 |
| `hallucination_rate` | percent |
| `uncheckable_claims` | count, shown apart from the rates |
| `enhance_ms`, `ocr_ms`, `vlm_ms`, `total_ms` | mean ms per frame; empty cells are skipped (e.g. `vlm_ms` on frames without a VLM call) |

Numbers are copied or pooled from the source files, rounded to 4 decimals. Nothing is filled in.

## Checked by hand

`tests/test_aggregate.py` works out the numbers in the docstrings: pooled VLM counts
(0.4 and 40.0, where the mean of the clip rates would give 0.375 and 37.5), mean times with an
empty cell, `N/A` handling, zero denominators, missing files and condition order.
