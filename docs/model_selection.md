# Model Selection (C-01)

Pick a pretrained model for vehicle detection, plate detection and Korean OCR.
Test set: 10 Korean plate images (5 clear daytime, 5 night or far).

## Candidates

| Step | Model | Version | Weights source | License |
| --- | --- | --- | --- | --- |
| Vehicle detection | YOLOv8n (COCO) | ultralytics 8.4.208 | `yolov8n.pt`, github.com/ultralytics/assets release v8.4.0 | AGPL-3.0 |
| Plate detection | Not tested yet | - | - | - |
| OCR | EasyOCR (`ko`) | easyocr 1.7.2, torch 2.15.0 (CPU) | `craft_mlt_25k.pth`, `korean_g2.pth`, EasyOCR GitHub releases | Apache-2.0 |
| OCR | PaddleOCR (`korean`) | paddleocr 3.7.0, paddlepaddle 3.3.1 (CPU) | `PP-OCRv5_server_det`, `korean_PP-OCRv5_mobile_rec`, Hugging Face (PaddleX default) | Apache-2.0 |

Weights download automatically on first run:
YOLO to `weights/` (ignored by git), EasyOCR to `~/.EasyOCR/model/`, PaddleOCR to `~/.paddlex/official_models/`.

## Test set

| Group | Count | Source |
| --- | --- | --- |
| Clear daytime | 5 | TBD |
| Night or far | 5 | TBD |

## Results

Vehicle detection (full images, `conf >= 0.4`):

| Model | Found | ms/img (CPU) |
| --- | --- | --- |
| YOLOv8n | /10 | |

OCR (hand-cropped plates):

| Model | Read (exact) | Char accuracy | Format OK | Mean conf | ms/img (CPU) |
| --- | --- | --- | --- | --- | --- |
| EasyOCR | /10 | | /10 | | |
| PaddleOCR | /10 | | /10 | | |

Smoke test on 3 synthetic plates (not a real result):
EasyOCR read 1/3. It read the middle Hangul as a digit on one-line plates (`12가3456` → `1273456`), once with conf 0.998.
PaddleOCR read 3/3 but was about 7x slower (~700 ms vs ~95 ms).

## Decision

- Vehicle detection: TBD
- Plate detection: TBD
- OCR: TBD

If OCR reads 3 or fewer of 10, try another OCR or focus on char accuracy.

## How to run

```
python tools/model_check.py <samples>
```

`<samples>` has `full/` (full images), `crops/` (hand-cropped plates) and `labels.csv` (`file,text`).
Keep it outside the repo. Results go to `<samples>/out/`.

## Install notes

```
pip install ultralytics==8.4.208 easyocr==1.7.2 paddlepaddle==3.3.1 paddleocr==3.7.0 pandas==2.2.3 truststore
```

- `pandas` 3.1.1 (pulled in by PaddleOCR) was blocked by Windows Application Control on one PC. `pandas==2.2.3` works.
- PaddleOCR needs `enable_mkldnn=False` on CPU with paddlepaddle 3.3.1, otherwise it fails with `NotImplementedError`.
- PaddleOCR installs `opencv-contrib-python` 4.10, which replaces the `cv2` from `opencv-python` 5.0. Install order matters.
- `truststore` makes Python use the Windows cert store. Needed if antivirus scans HTTPS (pip and weight downloads fail with `CERTIFICATE_VERIFY_FAILED`).
