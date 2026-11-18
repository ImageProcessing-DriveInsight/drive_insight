# OCR Evaluation (C-09)

[한국어](ocr_evaluation.ko.md)

`eval_ocr(results, labels)` scores one condition. `python -m src.eval.ocr` scores every
`results/ocr/<cond>.csv` and writes `results/ocr/ocr_summary.csv`.

## Plate label format

Plates are read from JSON files in `data/labels/` that map each frame file name to its plates.
B's label tool writes this format: `python -m tools.b_labels export` turns the filled
`data/annotations/scenes.json` into `data/labels/plates.json`.
`text: null` means the plate is not readable by eye. A frame with no plate is an empty list.

```json
{
  "fog_01_3500.png": [
    {"bbox": [412, 380, 96, 28], "text": "12가3456"},
    {"bbox": [120, 402, 40, 12], "text": null}
  ],
  "fog_01_7000.png": []
}
```

## Matching

Per frame, predicted and labeled plates are paired one-to-one. A pair qualifies when the boxes
overlap by at least half of the smaller box (`overlap` ≥ 0.5); qualifying pairs are taken highest
IoU first, so the box closest in size wins.

Plain IoU ≥ 0.5 was used before. In an end-to-end run on 10 sample frames, 4 plates in the
fixed condition read the same text as in the original but had a tighter or looser box
(IoU 0.07–0.32) and were counted as missed. The detection rate then measured how tight the box
was, not whether the plate was found.

## Metrics

Readable standard labeled plates (`text` is not null and is a standard plate):

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

Labels that are not standard plates are left out of the rates too. A standard plate is what the
judge can call readable ([status rules](plate_recognition.md)): plate characters only, with an optional
region name. Carmaker advertising plates (123케4567, 12차3456), military and diplomatic plates are
real, but a read of them can never be right, so they would always count as wrong.

| Metric | Definition |
| --- | --- |
| `nonstandard_labels` | count |
| `readable_wrong` | also counts a readable answer on one of these |

Also: `frames` (labeled frames), `plates`, `missing_frames` (labeled but not in the CSV).
Rates are empty when there is no readable standard labeled plate.

`frame_char_accuracy(results, labels)` gives the mean char accuracy per frame for the
condition comparison (C-11). Frames without a readable standard labeled plate get `None`.

## Checked by hand

`tests/test_ocr_eval.py` has three cases worked out by hand in the docstrings:
mixed reads with one overconfident answer, a missed box with a wrong read, and one-to-one matching.
More tests cover tighter and looser boxes, the closest box winning, and non-standard labels.
