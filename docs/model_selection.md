# Model Selection (C-01)

[한국어](model_selection.ko.md)

Pick a pretrained model for vehicle detection, plate detection and Korean OCR.
Test set: 10 Korean plate images (5 clear daytime, 5 night or far).

## Candidates

| Step | Model | Version | Weights source | License |
| --- | --- | --- | --- | --- |
| Vehicle detection | YOLOv8n (COCO) | ultralytics 8.4.208 | `yolov8n.pt`, github.com/ultralytics/assets release v8.4.0 | AGPL-3.0 |
| Plate detection | No pretrained model; own search inside the vehicle box (C-03) | - | - | - |
| OCR | EasyOCR (`ko`) | easyocr 1.7.2, torch 2.15.0 (CPU) | `craft_mlt_25k.pth`, `korean_g2.pth`, EasyOCR GitHub releases | Apache-2.0 |
| OCR | PaddleOCR (`korean`) | paddleocr 3.7.0, paddlepaddle 3.3.1 (CPU) | `PP-OCRv5_server_det`, `korean_PP-OCRv5_mobile_rec`, Hugging Face (PaddleX default) | Apache-2.0 |

Weights download automatically on first run:
YOLO to `weights/` (ignored by git), EasyOCR to `~/.EasyOCR/model/`, PaddleOCR to `~/.paddlex/official_models/`.

No pretrained plate detector is used. Public weights are pickle files from unknown sources, which can run code when loaded.

## Test set

| Group | Count | Source |
| --- | --- | --- |
| Clear daytime | 5 | Web images (internet search) |
| Night or far | 5 | Web images (internet search) |

Used only for model selection. Images and plate text are not in the repo.

## Results

Vehicle detection (full images, `conf >= 0.4`):

| Model | Found | ms/img (CPU) |
| --- | --- | --- |
| YOLOv8n | 10/10 | 19 |

OCR (hand-cropped plates):

| Model | Read (exact) | Day | Night | Char accuracy | Format OK | Mean conf | ms/img (CPU) |
| --- | --- | --- | --- | --- | --- | --- | --- |
| EasyOCR | 3/10 | 1/5 | 2/5 | 0.91 | 3/10 | 0.65 | 50 |
| PaddleOCR | 7/10 | 4/5 | 3/5 | 0.95 | 7/10 | 0.96 | 304 |

- Main error is the middle Hangul read as a digit or dropped: all 3 PaddleOCR misses and 6 of 7 EasyOCR misses.
- PaddleOCR gave conf ≥ 0.94 on all 3 misses, so conf alone cannot catch them.
  All 3 failed the plate format check, and every read that passed the check was correct. C-06 must use both.

## Pipeline tests (not real results)

These only check that the script runs. Do not report them as model performance.

**3 rendered plates** (crops only):
EasyOCR read 1/3. It read the middle Hangul as a digit on one-line plates (`12가3456` → `1273456`), once with conf 0.998.
PaddleOCR read 3/3 but was about 7x slower (~700 ms vs ~95 ms).

**10 AI-generated images** (5 day, 5 night).
All images are AI-generated. night_02–05 are darkened day images with plate text added digitally.

| Model | Result | Char accuracy | Format OK | Mean conf | ms/img (CPU) |
| --- | --- | --- | --- | --- | --- |
| YOLOv8n | vehicles found in 10/10 | - | - | - | 19 |
| EasyOCR | read 9/10 | 0.97 | 9/10 | 0.86 | 69 |
| PaddleOCR | read 10/10 | 1.00 | 10/10 | 0.98 | 424 |

EasyOCR missed one night plate with a 3-digit prefix (conf 0.557).

## Decision

- Vehicle detection: YOLOv8n. Found vehicles in 10/10 at 19 ms/img on CPU.
- Plate detection: own candidate search inside the vehicle box (C-03). On the 10 real photos the plate was in the top 3 candidates for 10/10 and first for 8/10.
- OCR: PaddleOCR. Read 7/10 vs 3/10 for EasyOCR. ~0.3 s/img is fine for 30–50 eval frames.

If OCR reads 3 or fewer of 10, try another OCR or focus on char accuracy.

## How to run

```
python tools/model_check.py <samples>
```

`<samples>` has `full/` (full images), `crops/` (hand-cropped plates) and `labels.csv` (`file,text`).
Keep it outside the repo. Results go to `<samples>/out/`.

## Install notes

```
pip install ultralytics==8.4.208 easyocr==1.7.2 paddlepaddle==3.3.1 paddleocr==3.7.0 pandas==2.2.3 chardet==5.2.0 truststore
```

- `pandas` 3.1.1 and `chardet` 7.7.0 (pulled in by PaddleOCR) were blocked by Windows Application Control on one PC. `pandas==2.2.3` and `chardet==5.2.0` (pure Python) work.
- PaddleOCR needs `enable_mkldnn=False` on CPU with paddlepaddle 3.3.1, otherwise it fails with `NotImplementedError`.
- PaddleOCR installs `opencv-contrib-python` 4.10, which replaces the `cv2` from `opencv-python` 5.0. Install order matters.
- `truststore` makes Python use the Windows cert store. Needed if antivirus scans HTTPS (pip and weight downloads fail with `CERTIFICATE_VERIFY_FAILED`).
