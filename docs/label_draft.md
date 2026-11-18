# Label Drafts and Check Images (ALL-02, ALL-03)

[한국어](label_draft.ko.md)

`tools/label_draft.py` speeds up labeling with B's label template. It fills in boxes and draws
them on the frames. People still decide every label.

## Workflow

```bash
python -m tools.b_labels init        # B: template data/annotations/scenes.json from data/frames/orig
python tools/label_draft.py draft    # vehicle and plate boxes for untouched entries, plus check images
# edit scenes.json (table below), then redraw to check your edits
python tools/label_draft.py check    # all frames, or --only day_01_3500.png
python -m tools.b_labels export      # B: data/labels/plates.json for the OCR evaluation
```

Paths default to `data/...`. `--annotations`, `--frames` and `--check` change them.
`--only` limits `draft` and `check` to frame names or quoted patterns such as `"fog_*"`.
Synthetic fog frames can be drafted from their clear frames:
`draft --frames data/frames/clear --only "fog_*"` ([synthetic fog](synthetic_fog.md)).

## What the draft fills

| Field | Draft | Labeler |
| --- | --- | --- |
| `vehicles` | YOLO boxes with `class` (car, truck, bus, motorcycle) | fix, delete or add boxes |
| `plates` | one box per vehicle from `detect_plates`; `status` and `text` are `null` | fix boxes, delete boxes that are not plates, add missed plates; set `status` to `readable` (with every character in `text`, no `?`) or `unreadable` (`text` stays `null`) |
| `events`, `visibility_notes` | not touched | fill in |
| `annotator`, `annotation_status` | not touched | your name; `complete` when done |

- Only untouched entries are drafted: `pending`, with no vehicles and no plates. An entry someone
  edited is never changed, so running `draft` again is safe. Edits saved while it runs are kept.
- Plate text is never filled in, so OCR output cannot leak into the labels.
- A plate with an empty `status` fails B's validator, so a draft cannot be exported by mistake.

## Check images

| Color | Box |
| --- | --- |
| Blue | vehicle, `V0`, `V1`, ... |
| Red | plate whose `status` is still empty |
| Green | `readable` plate, with its text |
| Yellow | `unreadable` plate |

The numbers are the positions in the `vehicles` and `plates` lists of `scenes.json`.
Images go to `data/annotations/check/`, which git ignores because they show real plates.

## Watch out

- The draft only has the plates the pipeline found. Look at every vehicle without a plate box and
  add its plate if one is visible. Missed plates left out of the labels would make the detection
  rate look better than it is.
- Draft boxes may include the plate border or be a little loose. Draw the box along the plate edge.
  The evaluation pairs boxes by the overlap of the smaller box ([OCR evaluation](ocr_evaluation.md)),
  so a few pixels do not change the result.
- Some draft plates are not plates (mirrors, lights, background). Delete them.

## Sample run

10 sample photos: about 2 s per photo on CPU, including model loading. The draft had
19 vehicles and 16 plate boxes. Every real plate got a box, and 6 of the 16 boxes were not plates.
