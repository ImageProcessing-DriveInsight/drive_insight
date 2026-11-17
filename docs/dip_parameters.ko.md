# 역할 A: 파라미터·구현 결정·실험 및 연동 가이드

기준: 2026-11-17. A-01~06은 PR [#30](https://github.com/ImageProcessing-DriveInsight/drive_insight/pull/30),
apply_ops는 이슈 [#44](https://github.com/ImageProcessing-DriveInsight/drive_insight/issues/44)의 구현이다.
이 문서는 팀 공유용이다. 로컬 작업 메모 `dip.md`와는 별개다.
아래의 **현재 구현**, **명세 요구**, **미합의 제안**을 구분해서 읽는다.
아직 FIXED_PARAMS나 적응형 규칙을 선정한 상태가 아니다.

## 1. 현재 API와 입력 계약

```python
from src.dip import bgr_to_ycrcb, ycrcb_to_bgr, gamma, hist_eq
from src.dip import gaussian, median, unsharp

# frame: np.ndarray, uint8, (H, W, 3), BGR
smoothed = gaussian(frame, ksize=5, sigma=1.0)
denoised = median(frame, ksize=3)
sharpened = unsharp(frame, amount=1.2, sigma=1.0, threshold=5)
```

위 호출값은 사용 예시이며 추천값·기본값·최종 고정 설정이 아니다.
모든 인자는 함수 시그니처상 필수이며 기본값이 없다.

- 모든 영상 입출력은 비어 있지 않은 uint8 `(H, W, 3)`이다. 색 공간 변환 결과만 Y/Cr/Cb 순서다.
- 잘못된 배열 dtype/차원/빈 영상은 `ValueError`. 입력은 수정하지 않고 새 배열을 반환한다.
- 커널 크기는 정수만 허용하며 `3.0`, bool은 거부한다. 실수 파라미터는 유한한 실수만 허용하며 bool도 거부한다.
- Gaussian/Median/Unsharp는 BGR 채널마다 독립적으로 처리한다.
  감마/평활화만 Y에 적용한다. "모든 필터가 Y 전용"이라는 계약은 아니다.
- 구현: [color.py](../src/dip/color.py), [ops.py](../src/dip/ops.py),
  공개 함수: [__init__.py](../src/dip/__init__.py), 검증: [test_ops.py](../tests/test_ops.py).

| 함수 | 파라미터와 현재 허용 범위 | 특별 동작 |
| --- | --- | --- |
| `bgr_to_ycrcb(img)` | uint8 BGR | uint8 Y/Cr/Cb 반환 |
| `ycrcb_to_bgr(img)` | uint8 Y/Cr/Cb | BGR 복원 및 색역 클리핑 |
| `gamma(img, g)` | `0.3 <= g <= 3.0` | `g<1` 밝게, `g>1` 어둡게, `g=1` 정확한 원본 복사 |
| `hist_eq(img)` | 영상 외 파라미터 없음 | Y가 단일 값이면 정확한 원본 복사 |
| `gaussian(img, ksize, sigma)` | `ksize` ∈ {3,5,7,9}, `sigma>0` | 한 행·한 열·1×1 입력도 지원 |
| `median(img, ksize)` | `ksize` ∈ {3,5} | 경계 픽셀 복제, 채널 간 혼합 없음 |
| `unsharp(img, amount, sigma, threshold)` | `amount>=0`, `sigma>0`, `threshold>=0` | amount=0은 원본 복사. threshold>255는 모든 차이를 억제 |

Unsharp의 amount/threshold에는 현재 별도의 최대 허용값이 없다.
이는 큰 값이 화질에 적합하다는 뜻이 아니다. threshold 단위는 0~255 영상의 픽셀 강도 차이다.

## 2. 명세와 구현자가 결정한 내용

근거 문서: [기능 명세](plan/feature_spec.ko.md), [공통 인터페이스](plan/team_plan.ko.md).
원본 PDF의 오래된 날짜보다 사용자와 합의한 11/19 개별 개발·11/24 통합 완료 일정이 우선한다.

| 항목 | 명세에서 정한 내용 | 구현자가 선택한 세부 사항·이유 | 변경 시 영향 |
| --- | --- | --- | --- |
| 색 공간 | 행렬 직접 계산, 왕복 오차 ≤2 | full-range BT.601, Cr/Cb 중심 128, 아래 계수 선택 | B의 품질 지표와 감마/평활화 결과도 변함 |
| 감마 | LUT 256칸, g 범위 0.3~3.0, g=1 동일 | `255*(Y/255)**g`; 어두우면 gamma 0.5라는 명세 예시와 일관 | `1/g` 정의로 바꾸면 B 규칙의 효과가 반대가 됨 |
| 평활화 | 히스토그램/CDF 직접 계산, 단색 유지 | Y의 첫 유효 CDF를 뺀 후 정규화 | 화질·OCR 비교 및 저장된 결과 재생성 필요 |
| Gaussian | 커널 직접 생성·합 1, 분리형 두 패스, 반사 패딩 | 반사에서 경계 픽셀 제외(REFLECT_101), 대칭 정수 계수 합 256 | 가장자리 결과와 OpenCV 비교가 달라질 수 있음 |
| Median | 3/5 커널, sliding_window_view + np.median | OpenCV와 일치하도록 경계 복제, 64행 단위 처리 | 패딩은 결과 변경, 블록 크기는 성능·메모리에 영향 |
| Unsharp | img + amount*(img-blur), 클리핑, threshold 미만 미적용 | **BGR 채널별 마스크**, 아래 sigma→ksize 규칙, 반올림된 Gaussian 출력 사용 | 색 테두리·샤프닝 강도·임계값 적용 결과 변경 가능 |
| 숫자 처리 | 출력 uint8 | 색 변환/감마/평활화/Unsharp는 np.rint, Gaussian은 floor(x+0.5) | 0.5 경계의 반올림 차이, 회귀 테스트 필요 |

### 색 변환 수식

```text
Y  = 0.114*B + 0.587*G + 0.299*R
Cr = (R-Y)*0.713 + 128
Cb = (B-Y)*0.564 + 128
R  = Y + (Cr-128)/0.713
B  = Y + (Cb-128)/0.564
G  = (Y - 0.299*R - 0.114*B)/0.587
```

변환은 float64 계산 후 반올림·0~255 클리핑한다. Y만 바꾸어도 BGR 복원 시 색역을
벗어나 클리핑될 수 있어 최종 색감이 완전히 보존된다고 보장하지 않는다.

### Gaussian의 계수와 계산 정밀도

`exp(-0.5*(x/sigma)^2)`를 정규화한 뒤, 대칭성과 합 256을 유지하면서 정수 계수로 양자화한다.
이는 uint8 OpenCV 기준과의 차이를 줄이기 위해 선택한 방식이다. 수학적인 실수 Gaussian과는
양자화 차이가 있다. 특히 매우 작은 sigma에서는 계수가 중심에 집중되어 사실상 항등 연산이 될 수 있다.
버퍼는 float32이고 1/256 계수를 두 번 적용한 합은 8 정수 비트+16 소수 비트 범위로 표현한다.
픽셀별 루프 대신 작은 커널 탭만 순회한다. 마지막에 한 번만 uint8로 반올림한다.

### Unsharp에서 합의가 필요한 두 가지

1. **커널 결정:** `radius = clamp(ceil(3*sigma), 1, 4)`, `ksize = 2*radius+1`.
   따라서 sigma가 커져도 커널은 9를 넘지 않는다. 큰 sigma의 충분한 공간 범위를 보장하는 규칙은 아니다.
2. **threshold 단위:** `abs(img-blur) >= threshold`를 B/G/R 채널 각각에 적용한다.
   명세는 픽셀이라고만 하므로, Y 기반 또는 픽셀 공통 마스크와 어느 것이 맞는지 A·B가 검토해야 한다.

| sigma 예시 | Unsharp 내부 ksize |
| ---: | ---: |
| 0.1 | 3 |
| 0.5 | 5 |
| 1.0 | 7 |
| 1.5 이상 | 9 |

이 규칙들은 현재 동작을 기록한 것이며 팀이 최종 합의한 설정으로 간주하지 않는다.
변경하면 A의 비교 테스트, B의 규칙·로그, 생성된 보정 프레임과 C/D의 평가 결과를 함께 재검토한다.

## 3. 다양한 파라미터 실험 계획 (아직 실행하지 않음)

아래 후보는 **검증용 제안**이다. 입력 검증의 허용 범위와 실험 후보 범위는 다르다.
조합 전체를 바로 돌리지 말고, 한 연산씩 범위를 좁힌 뒤 유망한 조합을 비교한다.

| 대상 | 1차 실험 후보 | 관찰할 것 |
| --- | --- | --- |
| 감마 g | 0.3, 0.5, 0.7, 1.0, 1.3, 2.0, 3.0 | 어두운 영역 회복, 하이라이트 손실, 번호판 대비 |
| Gaussian | ksize 3/5/7/9 × sigma 0.5/1.0/1.5/2.0 | 노이즈 감소와 문자 획 소실의 균형 |
| Median | ksize 3/5 | 점 노이즈 제거, 작은 문자·윤곽 소실, 속도 |
| Unsharp | amount 0/0.5/1.0/1.5/2.0, sigma 0.5/1.0/1.5, threshold 0/3/5/10/20 | halo, 색 테두리, 노이즈 재증폭, OCR 악화 |
| 평활화 | 적용/미적용 | 잡음 증폭, 명암 과장, 색역 클리핑 |

실제 평가 목록의 같은 프레임으로 orig/fixed/adaptive를 비교한다.
튜닝용 프레임과 최종 평가 프레임을 가능하면 구분하고 목록을 고정한다.
최종 평가만 보고 반복 튜닝했다면 그 사실도 기록한다.
fixed는 프레임별로 설정을 바꾸지 않고 하나의 설정을 전체에 적용해야 한다.

### 실험 기록 양식

한 실행의 원본·파라미터·출력을 역추적할 수 있도록 다음 필드를 남긴다.
저장 위치 예시는 `results/experiments/dip/`이며 **아직 작성기·스키마가 구현된 것은 아니다**.

```text
run_id, code_commit, config_id, clip, frame, condition,
operation_order, params_json, input_hash, output_path,
height, width, dtype, warmups, repeats, enhance_ms_median, enhance_ms_p95,
brightness, contrast, noise, sharpness,
ocr_detection_rate, ocr_exact_match_rate, ocr_char_accuracy,
artifact_notes, decision, decision_reason
```

- B 지표·C OCR 평가 함수가 준비되면 연결한다. 없는 값은 0으로 채우지 말고 미측정으로 표시한다.
- 개선뿐 아니라 악화 프레임·크롭 경로도 남기며, 시각적으로 밝아졌다는 이유만으로 채택하지 않는다.
- 테스트 입력값은 운영 설정과 분리한다. 최종 채택한 값·근거·변경 이력을 기록하고 그때 FIXED_PARAMS를 확정한다.

## 4. 성능 현황과 개선 순서

구현 커밋 `0d995ce`에서 측정한 합성 1080p BGR 1장 기준이다.
원본은 NumPy `default_rng(29).integers(0,256,(1080,1920,3),dtype=np.uint8)`이며 실제 영상 출처는 없다.
당시 환경은 Python 3.12, NumPy 2.3.5, OpenCV 4.14.0, pytest 9.2.0.
CPU 모델·전원 모드·부하는 기록하지 않았으므로 정식 벤치마크로 간주하지 않는다.

| 연산 | 단일 측정 | 명세 목표 | 목표 시간 대비 |
| --- | ---: | ---: | ---: |
| Gaussian 5×5, sigma=1.0 | 0.557초 | ≤0.5초 | 1.11배 |
| Gaussian 9×9, sigma=1.5 | 0.963초 | ≤0.5초 | 1.93배 |
| Median 3×3 | 2.609초 | ≤1.5초 | 1.74배 |
| Median 5×5 | 6.827초 | ≤1.5초 | 4.55배 |

**기능 정확도 통과와 속도 목표 달성은 별개다. A-10은 미완료이고 고정 파이프라인 2초 목표도 미측정이다.**
하드웨어 한계라고 단정할 수 없다. GPU를 사용하지 않는 CPU NumPy 구현이다.

1. 실제 프레임과 무작위 프레임을 동일 조건에서 비교한다. CPU/메모리, OS, 라이브러리 버전,
   해상도, 커널, 전원 모드, 다른 작업의 부하를 기록한다.
2. 전체 1080p 크기로 워밍업하고 예를 들어 2회 워밍업·10회 반복한다.
   median/p95 및 원시 시간을 저장한다. 기존 1회 수치와 구분하고, 비교할 버전은 같은 조건에서 재측정한다.
3. I/O를 제외한 연산 시간과 I/O 포함 일괄 처리 시간을 분리한다. CPU에서는 perf_counter로 측정한다.
4. Median의 창 복사·partition 비용부터 프로파일링한다. 64행 블록의 후보(16/32/64/128),
   메모리 배치, 임시 배열 수를 검토한다. Gaussian은 패딩·누적 배열 생성 비용을 점검한다.
5. 구현 변경 뒤 정확도·입력 보존·경계 테스트를 재실행한다.
   OpenCV 연산으로 대체하거나 해상도를 조용히 낮춰 목표를 맞춘 것으로 보고하지 않는다.
   해상도 변경이 필요하면 팀 합의 및 실험 조건에 명시한다.

## 5. 다른 팀원과 연결할 계약·미결 사항

### B: 적응형 보정과 영상 I/O

- 현재 제공 가능: 기존 7개 연산과 `src.dip.fixed:apply_ops` (또는 `from src.dip import apply_ops`).
  `fixed_enhance`와 `FIXED_PARAMS`는 **아직 미구현**이다.
- 구현 계약: `apply_ops(frame, params) -> out`. 예정 계약: `fixed_enhance(frame) -> (out, params)`.
- 명세 순서: 노이즈 제거 → 감마 → 평활화 → Unsharp.
  키 누락은 해당 연산 생략, 모르는 키는 ValueError, `rules` 키는 무시한다.
- 계획 문서의 `{"gamma":0.6,"denoise":"median","ksize":5,"unsharp":1.2,"rules":[...]}`는
  이슈 #44부터 실제 지원하는 형식이다. B의 현재 select_params 출력도 그대로 지원한다.
- 평활화 키·비활성 값은 B의 현재 코드에 맞췄다. A가 추가한 기본값/확장 키는 아래 7절에 기록한다.
  Gaussian sigma와 Unsharp sigma/threshold의 기본값, 마스크 단위·커널 산정 규칙은 팀 리뷰 대상이다.
- JSON에는 파이썬 기본 타입을 사용한다. NumPy 스칼라를 그대로 저장하지 않는다.
  현재 B의 실제 규칙 7종, 기본 동적 호출 및 PNG 일괄 생성·로그 연동을 테스트한다.
- B의 밝기·대비 측정 Y 계수와 A의 정의가 일치하는지도 확인한다.

### C: OCR 비교

- `data/frames/orig/`에서 고정 보정한 PNG를 `data/frames/fixed/`에 같은 `<clip>_<ms>.png` 이름으로 전달할 예정이다.
  일괄 생성기는 아직 미구현이다. orig/fixed/adaptive 파일 목록을 일치시키고 원본은 수정하지 않는다.
- 채널 순서 BGR과 원래 해상도를 유지한다. 영상 크기를 바꾸면 bbox 평가 기준도 달라진다.
- 동일 모델·라벨·프레임으로 평가하고 밝기 개선과 OCR 개선을 구분한다.
  호출 규격은 실제 `src/eval/` 함수와 연결 시 확인한다.

### D: 실행기·시간 측정·패키지

- 반환 영상은 uint8 BGR, params는 JSON 가능 dict로 맞춘다. 함수에서 파일 I/O를 강제하지 않는다.
- 예정 파라미터 로그는 `results/params/fixed.json`이다. 프레임 키·단위·스키마는 B·D와 합의 후 구현한다.
- D의 `timing.csv`에 필요한 enhance_ms와 A의 일괄 로그 시간이 어떤 범위를 재는지 명시해 중복·누락을 막는다.
- 설정과 코드 커밋을 실행 스냅샷에 기록하고 기존 출력과 캐시를 다른 설정의 결과로 재사용하지 않는다.

## 6. 검증 현황과 후속 체크리스트

```bash
python -m pip install -r requirements-dip.txt
python -m pytest tests/test_ops.py -q
python -m pytest -q
```

커밋 `0d995ce` 기준 DIP 263 passed, 전체 318 passed/2 skipped.
실제 모델·폰트 의존 테스트 생략은 실제 영상 검증 완료를 의미하지 않는다.

- [ ] B와 params 형식, 기본값 및 Unsharp 세부 동작 합의
- [x] apply_ops 구현과 순서·예외·빈 dict·B 연동 테스트 (이슈 #44)
- [ ] fixed_enhance/FIXED_PARAMS 구현 및 테스트
- [ ] 평가 프레임 확보 후 일괄 생성·로그·파일 목록 검증
- [ ] 파라미터 실험과 채택/기각 근거 기록
- [ ] 실제 영상의 색 테두리·halo·잡음·번호판 획 소실 확인
- [ ] 반복 벤치마크와 A-10 속도 목표 검증
- [ ] C/D 통합 및 금지 함수 검사 도구 실행

결정을 바꾸면 날짜, 관련 이슈/커밋, 이전 값→새 값, 이유, 비교 프레임 및 지표,
재생성해야 할 출력, 영향을 받는 팀원을 이 문서 또는 연결된 실험 기록에 추가한다.

## 7. apply_ops 파라미터 계약 v0.1 (이슈 #44)

```python
from src.dip import apply_ops

out = apply_ops(frame, {
    "denoise": "gaussian", "ksize": 3, "sigma": 1.0,
    "gamma": 0.75, "hist_eq": False,
    "unsharp": 0.8, "unsharp_sigma": 1.0, "unsharp_threshold": 5.0,
    "rules": ["EXAMPLE"],
})
```

이 값들은 호출 예시다. 최종 FIXED_PARAMS를 뜻하지 않는다.
모든 키는 선택 사항이다. 실행 순서는 dict 삽입 순서와 무관하게
**denoise → gamma → hist_eq → unsharp**다. 연산 사이에 uint8 출력이 전달되며 각 연산을
독립 호출한 결과와 같다. Y 변환을 합쳐 중간 반올림을 생략하는 최적화는 하지 않았다.

| 키 | 현재 계약 | 생략 시 | 근거 |
| --- | --- | --- | --- |
| denoise | `"none"`, `"gaussian"`, `"median"` | `"none"`, 생략 | B의 기존 출력 지원 |
| ksize | 정수 3/5/7/9, median일 때 3/5 | 3 | B 기본값 3을 재사용 |
| sigma | Gaussian용 유한 실수 >0 | **1.0** | A의 연동 기본값, 미튜닝 |
| gamma | 유한 실수 0.3~3.0 | 1.0, 생략 | 명세 범위·B 항등 설정 |
| hist_eq | Python bool만 허용 | False, 생략 | B가 이미 사용하는 키·타입 |
| unsharp | 유한 실수 >=0, amount로 사용 | 0.0, 생략 | B가 이미 사용하는 숫자 강도 |
| unsharp_sigma | 유한 실수 >0 | **1.0** | A의 연동 기본값, 미튜닝 |
| unsharp_threshold | 유한 실수 >=0 | **5.0** | A가 선택한 초기 노이즈 억제값, 미튜닝 |
| rules | 메타데이터, 값에 접근하지 않고 무시 | 없음 | 명세·B 계약 |

**명세에서 확정하지 않은 결정과 변경 영향:**

- sigma=1.0: B의 Gaussian 분기에 sigma가 없어서 명시적인 연동 기본값을 넣었다.
  현재 B의 NS_MEDIUM은 Gaussian(3,1.0)이 된다. 1.0의 우수성을 실험으로 확인한 것은 아니다.
- unsharp_sigma=1.0, threshold=5.0: B가 amount만 보내므로 기존 함수의 필수 인자를 보완했다.
  현재 SH_LOW는 Unsharp(0.8,1.0,5.0)이 된다. 5.0은 미세한 강도 차이의 증폭을 줄이려는 초기 선택이다.
  값이 달라지면 B의 규칙 ID가 같아도 영상이 달라지므로 프레임·OCR/VLM 결과를 재생성해야 한다.
- 확장 키는 `sigma`, `unsharp_sigma`, `unsharp_threshold`로 정했다. 한 sigma가 두 필터에
  암묵적으로 적용되지 않도록 구분했다. 새 키 이름은 팀 리뷰 대상이며 별칭은 지원하지 않는다.
- 비활성은 키 생략 또는 위의 명시적인 항등 설정으로 표현한다. None/False를 denoise 값으로 쓰지 않는다.
  gamma=1 또는 unsharp=0은 실제 연산 호출도 생략하여 불필요한 계산을 피한다.
- ksize/sigma만 전달해도 노이즈 제거가 켜지지 않는다. Unsharp 보조 키만 전달해도 샤프닝이 켜지지 않는다.
  B가 항상 ksize를 포함하는 구조와 호환된다.
- **알려진 비활성 옵션도 검증**한다. 예를 들어 `{"unsharp":0,"unsharp_sigma":0}`은 오류다.
  잘못된 설정이 나중에 연산을 켤 때까지 숨지 않도록 정한 정책이다.
- 모든 키와 값은 첫 연산 전에 검증한다. 알 수 없는 키나 잘못된 타입/범위는 ValueError다.
  rules의 내용은 검사하지 않는다. 프레임과 params를 수정하지 않고 빈 dict도 새 배열을 반환한다.
- `hist_eq=1`/`"true"`/NumPy bool, bool인 수치 파라미터는 거부한다. JSON에서 복원한 bool은 지원한다.

### B 문서와 연산 순서의 차이

B의 이전 rules.md에는 "평활화 → 감마"가 제안되어 있었다.
원래 명세 A-07의 "감마 → 평활화"를 우선하여 구현했고 rules.md에도 실제 순서를 표시했다.
B의 규칙 임계값·규칙 ID·select_params 코드는 바꾸지 않았다.
순서를 바꾸려면 A·B가 합의하고 비가환성 테스트, 튜닝 및 결과 생성을 함께 변경해야 한다.

### 이번 범위의 완료·미완료

- A-07 실행기와 B의 실제 규칙/동적 호출/PNG 일괄 생성 연동 테스트를 추가했다.
- A-08 fixed_enhance와 FIXED_PARAMS, A-09 고정 프레임 생성, A-10 성능 목표는 이번 범위가 아니다.
- 실제 평가 데이터로 이 기본값들을 검증한 상태가 아니며, 실제 영상 비교·튜닝은 여전히 필요하다.

검증 기록(2026-11-17): 기존 연산+실행기 단위 테스트 316 passed,
B 연동+기존 B 테스트 32 passed, 최종 전체 테스트 **429 passed, 2 skipped**.
생략된 테스트는 기존 YOLO 가중치/실제 OCR 환경 의존 항목이며 실제 데이터 검증을 대체하지 않는다.
