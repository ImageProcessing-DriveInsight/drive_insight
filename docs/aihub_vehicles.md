# Vehicle detection rate on AI Hub vehicle labels (#90)

[한국어](aihub_vehicles.ko.md)

AI Hub plates are masked, so AI Hub cannot be used for OCR evaluation, but every vehicle has a region
label (polygon). `tools/aihub_vehicles.py` turns these labels into the scenes file that the vehicle
detection rate (`src/eval/vehicles.py`) reads. The rate then shows how many labeled vehicles orig,
fixed and adaptive find in night, rain and tunnel frames.

```
python tools/aihub_vehicles.py <labels dir> [<labels dir> ...] [--out data/annotations/aihub_vehicles.json] [--names names.csv]
python -m src.eval.vehicles --frames <frames dir> --scenes data/annotations/aihub_vehicles.json
```

To evaluate together with own frames, give both label files:
`--scenes data/annotations/scenes.json data/annotations/aihub_vehicles.json` ([#92](env_report.md)).

## Label formats

| Format | Data | Classes counted as vehicles |
| --- | --- | --- |
| labelme (`shapes`, `points`) | 71588 night highway, 630 weather | car, truck, bus, motorcycle, trailer, caravan |
| polygon (`annotations`, flat coordinates) | 71570 day highway, 71930 upcycling | vehicle, truck, bus, ambulance, schoolBus, otherCar, policeCar |

- A vehicle box is the bounding box of its polygon, clipped to the image.
- Only classes of the kinds the vehicle detector (YOLO) finds (car, bus, truck, motorcycle) count.
  The own car's hood (ego vehicle), people, bicycles, trains, signs and road classes are left out.
- A frame with a group label (cargroup, busgroup and so on) is written as `annotation_status: "group"`
  and left out of the evaluation. The vehicles inside a group have no box of their own, so the detector
  finding one of them would count as a detection with no label (`unmatched`).
- A frame with no vehicle is evaluated with an empty list, and its detections count as `unmatched`.

## Frame names

- Default: the image file name written in the label, with `.png` in place of its extension (`a.jpg` → `a.png`).
  A label with no file name uses its JSON file name.
- When the evaluation frames get other names, pass a CSV with columns `source,frame` as `--names`.
  `tools/eval_lists.py` builds `data/annotations/eval_names.csv` from the members' frame lists
  ([#108](eval_lists.md)); labels of frames not in it, such as tuning frames, are skipped.
  `source` is the original image file name. Labels not in the CSV are skipped, so the CSV can also
  keep only the frozen evaluation list.
- Two labels that map to the same frame name stop the run.

## Counts on the team data (11/22)

Labels only; no detection was run, so that no result is seen before the evaluation list is frozen.

| Data | Frames | Frames evaluated | Vehicles | Width <100 px | 100–199 px | ≥200 px |
| --- | --- | --- | --- | --- | --- | --- |
| 71588 night (A) | 10,000 | 8,552 (1,448 with a group label left out) | 21,287 | 15,524 | 3,287 | 2,476 |
| 630 rain (B) | 3,000 | 3,000 | 5,640 | 1,637 | 1,830 | 2,173 |
| 71570 tunnel and bright sky (D) | 320 | 320 | 1,813 | 1,534 | 184 | 95 |
| 71930 tunnel (D) | 176 | 176 | 759 | 541 | 132 | 86 |

- Many vehicles are far away (under 100 px wide), so read the rate by size (`size` column) rather than overall.
- A vehicle split into several polygons would give several boxes. In 71588 and 630 no two vehicle
  polygons in one frame share an `object_id`. About half of the 71588 vehicle polygons and all of the
  630 ones have no `object_id`, so those could not be checked.

## Data handling

- The scenes file spells no plate, but it is derived from AI Hub labels, so it stays in
  `data/annotations/`, which git ignores.
- The tests (`tests/test_aihub_vehicles.py`) use synthetic labels only.
