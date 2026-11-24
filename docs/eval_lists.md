# Frame lists for image frames (#108)

[한국어](eval_lists.ko.md)

AI Hub frames come from image sequences, not videos, so they have no timestamp and `data/eval_set.csv`
cannot give their condition. The members hand over their evaluation frames as CSV lists instead
(`source`: the original image, `frame`: the PNG name in `data/frames/orig/`). `tools/eval_lists.py` turns
all the lists into the two files C's tools read, so the final run can be redone the same way whenever
a list is added.

```
python tools/eval_lists.py --list data/manifests/a_night/evaluation_frames.csv low_light --list data/annotations/rain_orig_mapping.csv rain
python tools/aihub_vehicles.py <night labels> <rain labels> --names data/annotations/eval_names.csv
python tools/env_report.py --scenes data/annotations/scenes.json data/annotations/aihub_vehicles.json --envs data/annotations/envs.csv
```

A new list (tunnel, backlight) is one more `--list FILE CONDITION`; rerun all three commands. The
outputs are rewritten whole.

## Output

| File | Columns | Read by |
| --- | --- | --- |
| `data/annotations/envs.csv` | `frame`, `env`, `clip` | `tools/env_report.py --envs` ([notes](env_report.md)) |
| `data/annotations/eval_names.csv` | `source`, `frame` | `tools/aihub_vehicles.py --names` ([notes](aihub_vehicles.md)) |

The tool also prints the frames per condition and how many of them are in `data/frames/orig/` yet,
e.g. `low_light: 30 frames, 0 in data/frames/orig` while the night PNGs are still to come.

## Input

- Each list is given with its condition, since some lists have no condition column (B's rain list).
  A `condition` column, when there is one (A's night list), must agree with it.
- `clip` is the list's `clip` or `scene` column when there is one, else empty. `env_report` gives the
  VLM rows of that clip the frame's condition, so D's VLM rows for these frames need the same value.
- Only evaluation lists are given. Tuning lists are not evaluated.

The run stops on a list without `source` or `frame`, an empty list, a frame that is not a PNG name, a
frame listed twice, two sources with the same file name (`aihub_vehicles` matches labels by file
name), a `condition` column that disagrees, a condition name other than letters, digits, `_` or `-`,
or a clip with two conditions.

## Checked

- On A's night list (30 frames) and B's rain list (30 frames) on 11/24: the name list matched the one
  made by hand, the vehicle labels built from it were identical byte for byte (60 frames, 54 without a
  group label, 196 vehicles), and every one of the 78 frames in `data/frames/orig/` had a condition.
- The tests (`tests/test_eval_lists.py`) use hand-made lists in both forms, read the outputs back with
  `env_report` and `aihub_vehicles`, and check every stop.

## Data handling

The lists and outputs name AI Hub files and come from AI Hub labels. Keep them in
`data/manifests/a_night/` and `data/annotations/`, which git ignores, and pass them only to approved
members.
