# Picking Evaluation Timestamps (ALL-01)

[한국어](frame_pick.ko.md)

Which frames of a clear-day clip go into the evaluation? `tools/pick_frames.py` picks them by the
size of the vehicles in front, before any fog is added. It never looks at the plate search or OCR,
so the choice does not favor frames the pipeline already reads (#77).

## Rule

| Step | Rule | Why |
| --- | --- | --- |
| Scan | YOLO vehicle boxes every 500 ms, with the pipeline's classes and threshold (`detect_vehicles`) | the same vehicles the pipeline sees |
| Near vehicle | widest box at least **280 px** wide at 1920 px (scaled with the frame width) | a plate (520 mm) is about 0.29 of a car's width (1.7–1.9 m), so about 80 px, where OCR reads well ([plate size check](plate_size_check.md)) |
| Not counted | boxes cut by the left or right frame edge; boxes wider than **2.5:1** | passing beside the camera; side views and oncoming cars. Rear three-quarter views up to about 2.4:1 still showed the plate |
| Camera car | its own dashboard, which YOLO calls a car, is dropped by `detect_vehicles` itself | see [plate recognition](plate_recognition.md#camera-car-78) |
| Frames | widest first, at least **3 s** apart, at most **5**; a frame whose widest box overlaps a kept one by IoU ≥ **0.7** is skipped | neighboring frames of one car repeat its plate; in a jam the car ahead stands still for seconds |
| Window | the **20 s** window with the most such frames, then the largest total width, then the earliest | foggy clips are 10–30 s |

Timestamps are written in the foggy clip's time and land on the scanned frame when the frames are
extracted (nearest frame, like `src.io.video.extract_frames`).

## Workflow

```bash
# 1. vehicle boxes, saved as data/clear/day_01.vehicles.json (boxes only, no images)
python tools/pick_frames.py scan data/clear/day_01.mp4
# 2. window and timestamps; adds rows to data/manifests/member_c.csv and prints the make command
python tools/pick_frames.py pick data/clear/day_01.mp4 --clip fog_01.mp4 --density medium
# 3. the foggy clip of that window
python tools/synth_fog.py make data/clear/day_01.mp4 data/clips/fog_01.mp4 --start-ms 12000 --end-ms 32000 --density medium --horizon 0.54
```

Then continue with step 3 of the [synthetic fog workflow](synthetic_fog.md#workflow): merge the
manifests, extract the frames, save the clear reference frames and draft the labels.

| Option | Default | |
| --- | --- | --- |
| `--step-ms` (scan) | 500 | sampling step |
| `--clip` | – | foggy clip name, e.g. `fog_01.mp4` |
| `--density` | – | `light`, `medium` or `heavy`; fix it before any results ([densities](synthetic_fog.md#densities)) |
| `--length-ms` | 20000 | window length |
| `--gap-ms` | 3000 | least time between two frames |
| `--max-frames` | 5 | frames per clip |
| `--min-width` | 280 | vehicle box width in px at 1920 wide |
| `--manifest` | `data/manifests/member_c.csv` | rows are added; a clip already listed is refused |

`pick` refuses a scan made from another file (SHA-256). A scan takes about 10 s per minute of
1080p video on CPU.

## What the own clips showed (11/19)

11 own front-camera clips, 1 min each, 1920×1080 at 30.3 fps, overcast daytime on 11/17 and 11/18.

- **The camera car's dashboard is a "car".** In 6 of 11 clips YOLO found boxes 0.84–0.99 of the
  frame wide ending at rows 1055–1066, just above the dashcam's text strip (53 sampled frames); it was the dashboard
  every time. It was the widest box, so it would have been picked, and it got plate candidates.
  `detect_vehicles` now drops it.
- **The files hold fewer frames than they list.** The first 0.96 s (29 frames) of a loop-recorded
  file does not decode; the rest is continuous. `scan` counts the frames that decode, so a window
  never reaches past them. Frame times are shifted by the same amount everywhere, so the foggy clip,
  its frames and the clear reference frames stay aligned.
- **Plates are small.** The wide lens makes a car 280 px wide only a few meters ahead. Of 1,313
  sampled frames, 521 had such a vehicle; in one clip (a jam) the same car filled most of them, and
  the same-view rule left 2 frames there.
- Result: 48 timestamps in 11 windows, 2–5 per clip.
