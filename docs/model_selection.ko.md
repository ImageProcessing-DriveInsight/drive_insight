# 모델 선정 (C-01)

[English](model_selection.md)

차량 검출, 번호판 검출, 한국어 OCR에 쓸 사전학습 모델을 고릅니다.
테스트 세트: 한국 번호판 이미지 10장(맑은 주간 5장, 야간·원거리 5장).

## 후보

| 단계 | 모델 | 버전 | 가중치 출처 | 라이선스 |
| --- | --- | --- | --- | --- |
| 차량 검출 | YOLOv8n (COCO) | ultralytics 8.4.208 | `yolov8n.pt`, github.com/ultralytics/assets 릴리스 v8.4.0 | AGPL-3.0 |
| 번호판 검출 | 사전학습 모델 없음, 차량 박스 안에서 직접 탐색(C-03) | - | - | - |
| OCR | EasyOCR (`ko`) | easyocr 1.7.2, torch 2.15.0 (CPU) | `craft_mlt_25k.pth`, `korean_g2.pth`, EasyOCR GitHub 릴리스 | Apache-2.0 |
| OCR | PaddleOCR (`korean`) | paddleocr 3.7.0, paddlepaddle 3.3.1 (CPU) | `PP-OCRv5_server_det`, `korean_PP-OCRv5_mobile_rec`, Hugging Face (PaddleX 기본값) | Apache-2.0 |

가중치는 처음 실행할 때 자동으로 내려받습니다.
YOLO는 `weights/`(git 제외), EasyOCR은 `~/.EasyOCR/model/`, PaddleOCR은 `~/.paddlex/official_models/`에 저장됩니다.

번호판 전용 사전학습 검출기는 쓰지 않았습니다. 공개된 가중치는 출처가 불분명한 pickle 파일이라 불러올 때 코드가 실행될 수 있습니다.

## 테스트 세트

| 그룹 | 장수 | 출처 |
| --- | --- | --- |
| 맑은 주간 | 5 | 웹 이미지(인터넷 검색) |
| 야간·원거리 | 5 | 웹 이미지(인터넷 검색) |

모델 선정에만 썼습니다. 이미지와 번호판 글자는 저장소에 올리지 않습니다.

## 결과

차량 검출(전체 이미지, `conf >= 0.4`):

| 모델 | 검출 | ms/장 (CPU) |
| --- | --- | --- |
| YOLOv8n | 10/10 | 19 |

OCR(손으로 자른 번호판):

| 모델 | 완전히 읽음 | 주간 | 야간 | 문자 정확도 | 형식 통과 | 평균 conf | ms/장 (CPU) |
| --- | --- | --- | --- | --- | --- | --- | --- |
| EasyOCR | 3/10 | 1/5 | 2/5 | 0.91 | 3/10 | 0.65 | 50 |
| PaddleOCR | 7/10 | 4/5 | 3/5 | 0.95 | 7/10 | 0.96 | 304 |

- 주된 오류는 가운데 한글을 숫자로 읽거나 빠뜨리는 것입니다. PaddleOCR 오답 3건 모두, EasyOCR 오답 7건 중 6건이 여기에 해당합니다.
- PaddleOCR은 오답 3건에서도 conf ≥ 0.94를 냈으므로 conf만으로는 걸러낼 수 없습니다.
  3건 모두 번호판 형식 검사에서 떨어졌고, 형식 검사를 통과한 결과는 모두 정답이었습니다. 그래서 C-06은 둘을 함께 씁니다.

## 파이프라인 시험(실제 결과 아님)

스크립트가 돌아가는지만 확인한 것입니다. 모델 성능으로 보고하지 마세요.

**렌더링한 번호판 3장**(크롭만):
EasyOCR은 1/3을 읽었습니다. 한 줄 번호판에서 가운데 한글을 숫자로 읽었고(`12가3456` → `1273456`), 그중 한 번은 conf 0.998이었습니다.
PaddleOCR은 3/3을 읽었지만 약 7배 느렸습니다(약 700 ms 대 약 95 ms).

**AI로 생성한 이미지 10장**(주간 5장, 야간 5장).
모두 AI 생성 이미지입니다. night_02–05는 주간 이미지를 어둡게 만들고 번호판 글자를 디지털로 넣은 것입니다.

| 모델 | 결과 | 문자 정확도 | 형식 통과 | 평균 conf | ms/장 (CPU) |
| --- | --- | --- | --- | --- | --- |
| YOLOv8n | 10/10에서 차량 검출 | - | - | - | 19 |
| EasyOCR | 9/10 읽음 | 0.97 | 9/10 | 0.86 | 69 |
| PaddleOCR | 10/10 읽음 | 1.00 | 10/10 | 0.98 | 424 |

EasyOCR은 앞자리가 3자리인 야간 번호판 하나를 놓쳤습니다(conf 0.557).

## 결정

- 차량 검출: YOLOv8n. CPU에서 장당 19 ms로 10/10 검출.
- 번호판 검출: 차량 박스 안에서 직접 구현한 후보 탐색(C-03). 실제 사진 10장 모두 번호판이 상위 3개 후보 안에 들었고, 8장은 1순위였습니다.
- OCR: PaddleOCR. EasyOCR 3/10에 비해 7/10을 읽었습니다. 장당 약 0.3초는 평가 프레임 30–50장에 충분합니다.

OCR이 10장 중 3장 이하만 읽으면 다른 OCR을 시험하거나 문자 정확도 위주로 보고합니다.

## 실행 방법

```
python tools/model_check.py <samples>
```

`<samples>`에는 `full/`(전체 이미지), `crops/`(손으로 자른 번호판), `labels.csv`(`file,text`)가 있어야 합니다.
이 폴더는 저장소 밖에 두세요. 결과는 `<samples>/out/`에 저장됩니다.

## 설치 메모

```
pip install ultralytics==8.4.208 easyocr==1.7.2 paddlepaddle==3.3.1 paddleocr==3.7.0 pandas==2.2.3 chardet==5.2.0 truststore
```

- PaddleOCR이 끌어오는 `pandas` 3.1.1과 `chardet` 7.7.0이 한 PC에서 Windows 애플리케이션 제어에 막혔습니다. `pandas==2.2.3`과 `chardet==5.2.0`(순수 Python)은 동작합니다.
- paddlepaddle 3.3.1의 CPU 환경에서는 PaddleOCR에 `enable_mkldnn=False`를 줘야 합니다. 안 주면 `NotImplementedError`로 실패합니다.
- PaddleOCR은 `opencv-contrib-python` 4.10을 설치하며, 이것이 `opencv-python` 5.0의 `cv2`를 덮어씁니다. 설치 순서에 따라 결과가 달라집니다.
- `truststore`는 Python이 Windows 인증서 저장소를 쓰게 합니다. 백신이 HTTPS를 검사하는 환경에서 필요합니다(pip와 가중치 다운로드가 `CERTIFICATE_VERIFY_FAILED`로 실패하는 경우).
