# NumPy 영상처리 성능 측정·최적화 (A-10)

이슈 [#50](https://github.com/ImageProcessing-DriveInsight/drive_insight/issues/50), 2026-11-17.
픽셀 결과와 FIXED_PARAMS를 유지하면서 연산·메모리 비용을 줄였다.
OpenCV 연산·GPU·해상도 축소·평가 프레임 수 축소로 속도를 맞추지 않았다.

## 재현 방법

프로젝트 루트의 가상환경에서 실행한다.

```bash
python -m tools.benchmark_dip --output results/benchmarks/dip.json
python -m tools.benchmark_dip --cases median5 fixed --warmups 2 --repeats 10 --output results/benchmarks/recheck.json
python -m tools.benchmark_dip --image data/frames/orig/clip_1000.png --output results/benchmarks/real.json
```

- 기본 입력은 NumPy `default_rng(29)`의 균일 무작위 uint8 BGR `(1080,1920,3)`이다.
  실제 영상이 아니다. `--image`는 PNG를 읽으며 리사이즈하지 않는다.
  파일 입력은 `kind=png_file`로 구분하며 사진인지 합성 이미지인지는 자동 판정하지 않는다.
- 기본 전체 크기 워밍업 2회·측정 5회. warmup/repeat 수, 원시 시간, 중앙값, p95를 JSON에 저장한다.
  횟수와 p95 계산 방식은 구현자가 정한 측정 정책이며 p95는 NumPy의 기본 선형 보간이다.
- 연산 호출과 반환 출력 해제를 측정한다. 입력 생성·디코딩·JSON I/O는 제외한다.
  Median의 작업자 생성·종료 비용은 포함한다. 동시에 테스트나 다른 벤치마크를 돌리지 않는다.
- 1080p에서만 목표 판정한다. 작은 smoke test는 `--width 32 --height 24` 등으로 실행할 수 있지만
  이 경우 `target_applicable=false`, `target_met=null`이다. 실제 PNG의 해상도는 width/height 인자로 바꾸지 않는다.
- JSON에는 Python/NumPy/OS/CPU 식별 정보·논리 CPU 수, 커밋, ops/color/fixed 소스 SHA256,
  입력 종류·크기·픽셀 SHA256, 설정과 목표값도 기록한다.
  Git이 없는 소스 ZIP에서는 commit=null로 남기고 소스 해시로 구분한다.

## 이번 측정 결과

동일 입력(seed=29)·1080p·워밍업 2회·측정 5회·동일한 여섯 설정을 순서대로 실행했다.
환경은 Windows 11, Python 3.12.14, NumPy 2.3.5, 논리 CPU 16개다.
구체적인 CPU 식별 문자열과 원시 시간은 아래 JSON에 있다.
전원 모드·CPU 주파수·다른 프로그램의 부하는 기록·통제하지 못했다.
표는 같은 컴퓨터에서 순차 실행한 결과이며 모든 차이를 코드 변경의 효과로 분리했다고 주장하지 않는다.

- [최적화 전 원시 결과](benchmarks/dip_before_50.json): 기준 코드 `28c4007`.
- [최적화 후 원시 결과](benchmarks/dip_after_50.json): 코드 `8480638`.

단위는 초다. 이전 대화의 단일 측정값과 구분한다.

| 연산 | 이전 중앙값 | 이후 중앙값 | 이후 p95 | 목표 |
| --- | ---: | ---: | ---: | ---: |
| Gaussian 3×3, sigma=1.0 | 0.387 | 0.157 | 0.219 | ≤0.5 |
| Gaussian 5×5, sigma=1.0 | 0.292 | 0.188 | 0.197 | ≤0.5 |
| Gaussian 9×9, sigma=1.5 | 0.425 | 0.193 | 0.213 | ≤0.5 |
| Median 3×3 | 1.328 | 0.673 | 0.684 | ≤1.5 |
| Median 5×5 | 3.606 | 1.048 | 1.089 | ≤1.5 |
| fixed_enhance 전체 | 1.929 | 0.869 | 0.995 | ≤2.0 |

이번 실행에서는 중앙값과 p95가 모두 목표 이내다. 도구의 `target_met`는 **중앙값**으로 판정하고,
p95는 별도 보고한다. 5회 p95가 최악 시간이나 미래 실행의 상한을 보장하지는 않는다.
실제 평가 프레임이 없어 실제 영상에서는 미측정이다. 다른 컴퓨터·NumPy 빌드·병렬 작업 부하에서는 재측정한다.

## 구현 결정과 유지한 계약

### Gaussian

정규화·정수 계수·반사 패딩·최종 반올림은 그대로 유지했다.
대칭 커널의 두 탭을 짝지어 누적하고, float32 변환 버퍼를 scratch로 재사용한다.
소유한 결과 배열에서 floor/clip을 수행해 큰 임시 배열을 줄였다.
음수가 없는 1/256 고정소수점 계수의 두 패스 합은 8 정수 비트+16 소수 비트 범위이므로
float32에서 덧셈 순서를 바꿔도 정확히 표현된다.

### Median

`sliding_window_view + np.median`, 경계 복제와 채널별 처리는 그대로다.
uint8 윈도우를 **소유 int32 버퍼**에 복사해 NumPy의 선택 연산 경로를 사용한다.
값 0~255와 홀수 크기 중앙값은 int32에서 정확하게 표현되므로 출력은 바뀌지 않는다.
이 환경에서는 uint8보다 빨랐지만 모든 NumPy 빌드에서 같은 차이를 보장하지 않는다.

스케줄링 값은 구현자가 시험을 통해 정한 값이며 보정 파라미터가 아니다.

| 항목 | 값 | 이유·영향 |
| --- | --- | --- |
| 블록 높이 | 32행 | int32 복사 버퍼를 제한하면서 큰 영상 처리 |
| 작업자 상한 | 4 | `min(4, CPU 수, 블록 수)`로 제한 |
| 병렬 기준 | 픽셀 수 ≥512×512, 작업자 >1 | 작은 입력의 스레드 생성 비용 회피 |

각 작업자는 독립된 버퍼와 겹치지 않는 출력 행만 쓴다. 예외를 모두 회수한 뒤 반환하며 원본은 수정하지 않는다.
표준 ThreadPoolExecutor를 쓰며 새 외부 의존성은 없다. NumPy의 네이티브 연산을 병렬로 실행한다.
1080p 5×5 버퍼는 작업자당 약 17.6 MiB, 4개 합계 약 70.3 MiB다(배열·패딩·결과·내부 비용 별도).
이전 uint8 64행 버퍼보다 임시 메모리는 늘어난다. 상위 실행기가 여러 프레임을 동시에 처리하면
중첩 병렬화로 부하가 커질 수 있으므로 통합 환경에서 작업자 정책을 다시 점검한다.

### Unsharp·색 변환·실행기

- Unsharp 차이는 범위 -255~255를 보존하는 int16으로 계산하고, amount 곱과 덧셈은 기존처럼 float64다.
  threshold·커널 산정·클리핑 동작을 바꾸지 않았다.
- BGR/YCrCb 변환은 float64 수식의 연산 순서를 유지하면서 채널별 버퍼를 사용한다.
  전체 영상 float 변환·채널 stack·전체 영상 크기의 중복 반올림 버퍼를 없앴다.
- apply_ops는 입력 보존이 보장된 연산에 원본을 전달하고, 항등 경로에서만 마지막에 복사한다.
  빈 dict가 새 배열을 반환하는 계약과 연산 사이 uint8 반올림은 유지한다.
- gamma 정의, 평활화 방식, 모든 파라미터 범위, FIXED_PARAMS, 출력 해상도는 변경하지 않았다.

## 정확도 검증

기존 OpenCV 기준·경계·읽기 전용/strided 입력·직렬/병렬 블록 테스트를 실행한다.
추가로 기준 커밋의 코드를 별도 네임스페이스로 읽어 일회성 old/new 비교를 수행했다.

- Gaussian/Unsharp의 작은 영상·다양한 커널/강도/threshold 192개 조건: 완전 일치.
- seed=29의 1080p Median 3/5, Gaussian 9, BGR→YCrCb 및 YCrCb→BGR: 완전 일치.
- 기존 색 변환까지 포함한 전체 fixed 파이프라인: 1080p에서 완전 일치.
- 이 확인은 테스트한 입력에 대한 결과다. 실험용 기준 코드는 제출 src에 복제하지 않았다.

```bash
python -m pytest -q
```

실제 영상 속도·품질 평가와 상위 실행기 부하 검증은 남아 있다. 금지 함수 검사 도구(A-12)는 후속 작업이다.

최종 검증 기록: **480 passed, 2 skipped**. 생략은 기존 모델/OCR 환경 의존 항목이다.
전후 JSON의 입력 해시·설정·warmup/repeat 일치와 최종 소스 해시 일치도 확인했다.
