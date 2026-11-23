# Results per environment condition (#92)

[한국어](env_report.ko.md)

`tools/plate_report.py` pools every frame under `data/frames/<cond>/`. With fog, night, rain and tunnel
frames together, the differences between conditions are lost in the average. `tools/env_report.py`
runs after `plate_report`: it splits the results by the environment condition of each frame and reruns
only the evaluation, aggregation and comparison per condition, without new OCR or vehicle detection.

```
python tools/plate_report.py --scenes data/annotations/scenes.json data/annotations/aihub_vehicles.json
python tools/env_report.py --scenes data/annotations/scenes.json data/annotations/aihub_vehicles.json [--envs envs.csv]
```

## Output

| Path | Content |
| --- | --- |
| `results/by_env/<env>/` | Results of that condition's frames only: `summary.csv`, `compare.csv`, `vehicles.csv`, `vehicle_compare.csv`, `figures/` |
| `results/by_env/summary.csv`, `compare.csv`, `vehicles.csv`, `vehicle_compare.csv` | The tables of every condition in one, with an `env` column first |

## Environment condition of a frame

- `data/eval_set.csv`: `<clip name>_<timestamp_ms>.png` (B's frame names) takes the row's `condition`.
  The row's `clip` is used to split the VLM scores.
- `--envs`: a CSV with columns `frame`, `env` (optional: `clip`), for frames named otherwise, such as AI Hub
  frames without a timestamp. It wins over `eval_set.csv`.
- A frame whose condition is unknown stops the run, so no frame drops out of every condition unseen.

## How it splits

- OCR results, vehicle detections, enhancement logs (`params/<cond>.json`) and timing files are split
  by frame. Keys of `params` that are not frame names, such as `global`, stay.
- Plate labels are split by the same frames, in memory only. A label of another condition's frame would
  count as a missed plate.
- VLM scores (`vlm/score.csv`) are split by `clip`. A row with no `clip` cannot be split and is left out.
- Vehicle labels need no split, since only frames with detections count.

## Several vehicle label files

`--scenes` takes several files and merges them (`src.eval.vehicles`, `tools/plate_report.py`,
`tools/compare_images.py`, `tools/env_report.py`), e.g. B's `scenes.json` for the own frames and the AI Hub
conversion ([#90](aihub_vehicles.md)). A frame in two files stops the run. Without the option,
`data/annotations/scenes.json` is used as before.

## Checked

- On the 48 own fog frames (one condition), the per-condition table matched the pooled one in every OCR
  metric, step time and vehicle rate (11/23).
- The tests (`tests/test_env_report.py`) use hand-made fog, rain and night results. Pooled, orig reads 1 of
  2 plates; per condition it must be 0 of 1 (fog) and 1 of 1 (rain). They also check times, enhancement
  logs, VLM scores, two vehicle label files, a frame with no condition and old files removed on a rerun.

## Data handling

`results/by_env/` holds OCR results with plate texts and crops of real plates, so git ignores it.
A rerun rewrites the folder of every condition it finds.
