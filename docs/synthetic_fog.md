# Synthetic Fog Clips (ALL-01)

[한국어](synthetic_fog.ko.md)

No public Korean fog footage with readable plates was found. AI Hub's driving videos blur the
plates, and its adverse-weather sets are still images. So the fog clips are made from clear-day
clips with `tools/synth_fog.py`. Snow is not synthesized.

The report and slides must say that the fog is synthetic and give the settings below.

## Model

```text
I = J·t + A·(1 − t)      t = exp(−β·d)      β = 3.912 / visibility
```

`J` is the clear frame, `A` the fog brightness, `d` the distance in meters. At the visibility
distance, 2 % of the contrast is left (Koschmieder).

| Part | How |
| --- | --- |
| Distance `d` | Flat road seen by a level camera: `d = near·(H − 1 − y_h) / (y − y_h)` below the horizon row `y_h`, `far` (300 m) from the horizon up. The bottom row is `near` (4 m). |
| Vehicles | YOLOv8n-seg masks on the clear frame, with the pipeline's vehicle classes and threshold. Inside a mask, `d` is the road distance of the mask's bottom row, where the vehicle meets the road. Masks are shrunk by 2 px so their edge does not carry the background. |
| Blur | Light scattering softens far parts: Gaussian σ = 1.5 px at 1080 rows (A's `gaussian`), mixed in by `1 − t`. |
| Noise | Sensor noise σ = 2 (8-bit levels), new in every frame, drawn from the seed. |

All frames of a clip share the same settings. Only the noise and the vehicle masks change.

Why not one fog level for the whole frame: that is a global linear change of brightness, and a
global histogram equalization undoes it almost exactly. B's adaptive rule `CT_LOW` turns that on
when the contrast falls below 35, so adaptive would look much better than on real fog. Fog that grows with distance cannot be
undone that way (`test_fog_thickens_with_distance_so_hist_eq_cannot_undo_it`).

## Densities

| `--density` | Visibility | Light kept at 10 m | 20 m | 40 m |
| --- | --- | --- | --- | --- |
| `light` | 300 m | 0.88 | 0.77 | 0.59 |
| `medium` (default) | 150 m | 0.77 | 0.59 | 0.35 |
| `heavy` | 75 m | 0.59 | 0.35 | 0.12 |

`--visibility` sets any other value. Fix the density of each clip before looking at any
results, and never change it based on OCR or VLM scores.

## Workflow

Keep the clear source clips in `data/clear/` (ignored by git), not in `data/clips/`.

```bash
# 1. one frame, clear and foggy side by side; the red line is the horizon row
python tools/synth_fog.py preview data/clear/day_01.mp4 --at 5000 --horizon 0.45
# 2. foggy clip (10-30 s) and its settings file data/clips/fog_01.fog.json
python tools/synth_fog.py make data/clear/day_01.mp4 data/clips/fog_01.mp4 --horizon 0.45 --start-ms 12000 --end-ms 37000
# 3. manifest rows for fog_01.mp4 -> B merges them and extracts data/frames/orig/fog_01_<ms>.png
# 4. clear frames with the same names, data/frames/clear/fog_01_<ms>.png (timestamps from data/eval_set.csv)
python tools/synth_fog.py reference data/clips/fog_01.mp4
# 5. label drafts from the clear frames (same boxes, better detection)
python tools/label_draft.py draft --frames data/frames/clear --only "fog_*"
```

- Put the horizon row where the road meets the sky or vanishes. Too low makes the near road foggy;
  too high leaves the far road clear.
- `make` takes about 0.33 s per 1080p frame on CPU, so a 30 s clip at 30 fps takes about 5 minutes.
  It refuses to overwrite an existing clip or settings file.
- Manifest row: `condition` `fog`, `source` like `own dashcam, synthetic fog (tools/synth_fog.py, medium)`,
  `license` like `own footage`.
- Label `status` by the foggy frame, the same rule as for the other conditions: `readable` only if a
  person can read the plate in the foggy frame or its neighbors. Use the clear frame to spell the text.

## Settings file

`<clip>.fog.json` sits next to the foggy clip. It holds the model, every setting (`visibility`,
`horizon`, `near`, `far`, `airlight`, `blur`, `noise`, `seed`, `vehicles`), the source path and
its SHA-256, the frame range, fps, size and codec. `reference` checks the source against the hash.
Share the file with the clip and quote the settings in the report.

## Watch out

- Hills, curves and a tilted camera break the flat-road assumption.
- A vehicle the mask model misses gets the road distance of each row, so its top fades like the
  background. Masks are found per frame, so vehicle edges can shimmer a little.
- The weights `weights/yolov8n-seg.pt` (7 MB, ignored by git) download on first use. If the
  download fails with a certificate error, save
  <https://github.com/ultralytics/assets/releases/download/v8.4.0/yolov8n-seg.pt> to `weights/`.
  `--no-vehicles` skips the masks.
- The clip is written as H.264 (`avc1`) when OpenCV can, else MPEG-4 (`mp4v`). OpenCV may print an
  H.264 or `Failed to initialize VideoWriter` error while it tries; if the run ends with
  `wrote N frames`, the clip is fine. The codec used is in the settings file.

## Sample run

A 10 s, 1080p test clip made from a sample photo with a slow zoom (not dashcam footage), `medium`,
horizon 0.45: 300 frames in 98 s, written as H.264. The car kept its outline, the sky and
background faded to gray, and the road fog thickened toward the horizon.
