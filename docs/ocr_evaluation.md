# OCR Evaluation (C-09)

[한국어](ocr_evaluation.ko.md)

`eval_ocr(results, labels)` scores one condition. `python -m src.eval.ocr` scores every
`results/ocr/<cond>.csv` and writes `results/ocr/ocr_summary.csv`.

## Plate label format (proposal)

Until the team label schema is fixed, plates are read from JSON files in `data/labels/`
that map each frame file name to its plates. `text: null` means the plate is not readable by eye.
A frame with no plate is an empty list.

```json
{
  "fog_01_3500.png": [
    {"bbox": [412, 380, 96, 28], "text": "12가3456"},
    {"bbox": [120, 402, 40, 12], "text": null}
  ],
  "fog_01_7000.png": []
}
```

When the real schema arrives, only `load_labels` in `src/eval/ocr.py` needs to change.

## Matching

Per frame, predicted and labeled plates are paired one-to-one with IoU ≥ 0.5, highest IoU first.

## Metrics

Readable labeled plates (`text` is not null):

| Metric | Definition |
| --- | --- |
| `detection_rate` | matched plates / plates |
| `exact_match` | matched plates with exactly the labeled text / plates |
| `char_accuracy` | mean of max(0, 1 − edit distance / label length); 0 if missed or no text |
| `readable_wrong` | matched plates judged readable but with wrong text |

Unreadable labeled plates are left out of the rates above:

| Metric | Definition |
| --- | --- |
| `unreadable_labels` | count |
| `overconfident` | judged readable anyway (would show made-up characters) |

Also: `frames` (labeled frames), `plates`, `missing_frames` (labeled but not in the CSV).
Rates are empty when there is no readable labeled plate.

`frame_char_accuracy(results, labels)` gives the mean char accuracy per frame for the
condition comparison (C-11). Frames without a readable labeled plate get `None`.

## Checked by hand

`tests/test_ocr_eval.py` has three cases worked out by hand in the docstrings:
mixed reads with one overconfident answer, a missed box with a wrong read, and one-to-one matching.
