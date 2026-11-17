# 고정 PNG 프레임 일괄 생성 (A-09)

이슈 [#48](https://github.com/ImageProcessing-DriveInsight/drive_insight/issues/48).
`src/dip/batch.py`가 B의 PNG 입출력과 A의 `fixed_enhance`를 연결한다.
FIXED_PARAMS 값은 바꾸지 않으며 모든 프레임에 같은 설정을 적용한다.
설정 근거는 [DIP 파라미터 가이드 8절](dip_parameters.ko.md#8-fixed_enhance-초기-기준-설정-v01-이슈-46)을 참조한다.

## 실행

프로젝트 루트에서 설치한 가상환경을 사용한다.

```bash
python -m pip install -r requirements-dip.txt
python -m src.dip.batch
```

기본 경로는 실행 위치가 아닌 프로젝트 루트 기준이다.
단, `python -m`으로 모듈을 찾으려면 프로젝트 루트에서 실행하거나 PYTHONPATH 등을 설정해야 한다.

| 용도 | 기본값 |
| --- | --- |
| 입력 | `data/frames/orig/` |
| 출력 | `data/frames/fixed/` |
| 로그 | `results/params/fixed.json` |

```bash
python -m src.dip.batch --input-dir data/frames/orig --output-dir data/frames/fixed --params-path results/params/fixed.json
```

```python
from src.dip.batch import enhance_fixed_frames

records = enhance_fixed_frames()  # 위 기본 경로 사용
records = enhance_fixed_frames(input_dir, output_dir, params_path)
```

반환값은 저장한 JSON과 같은 dict이다. `.png`와 `.PNG`를 구분하지 않고 입력 디렉터리의
바로 아래 파일만 이름순으로 처리한다. 이름과 확장자 대소문자, 해상도를 그대로 유지한다.
PNG 외 파일과 하위 폴더는 순회하지 않는다. PNG 이름을 가진 디렉터리는 잘못된 입력으로 거부한다.
프레임은 하나씩 읽고 처리하므로 전체 영상을 메모리에 올리지 않는다. 로그 dict는 프레임 수에 비례한다.

## 로그 형식과 시간 측정 결정

아래 시간은 **형식 예시**이며 실측 결과가 아니다.

```json
{
  "night_1000.png": {
    "params": {
      "denoise": "gaussian",
      "ksize": 3,
      "sigma": 1.0,
      "gamma": 0.75,
      "hist_eq": false,
      "unsharp": 0.8,
      "unsharp_sigma": 1.0,
      "unsharp_threshold": 5.0
    },
    "enhance_ms": 10.0,
    "total_ms": 15.0
  }
}
```

- 파일명 전체가 키다. `params`는 fixed_enhance의 실제 반환 dict이며 모든 적용 옵션을 포함한다.
- `enhance_ms`: `perf_counter`로 fixed_enhance 호출 전후 측정. PNG 디코딩·저장은 제외한다.
- `total_ms`: 해당 프레임 읽기부터 PNG 저장·교체까지. 배치 사전 검사와 최종 JSON 저장은 제외한다.
- 단위는 모두 밀리초다. 측정에는 실행 환경의 스케줄링 지연도 포함된다.
- 이 분리는 **명세에 없는 구현 결정**이다. B adaptive 배치의 현재 `enhance_ms`는 읽기·쓰기도
  포함하므로 양쪽 필드를 그대로 비교하면 안 된다. D의 timing.csv는 측정 범위를 맞춘 후 집계한다.
- B의 로그처럼 파일명 기반 dict를 사용하되 fixed에는 quality/rules를 넣지 않는다.
  코드 버전과 실행 스냅샷은 D의 실행기 등 상위 호출자에서 관리한다.

## 경로·재실행·실패 정책

명세의 원본 보존과 파일 목록 일치를 구체화한 구현 결정이다.

1. 입력·출력 폴더는 같거나 서로의 상위/하위가 될 수 없다. 경로를 해석한 뒤 검사하므로
   `..` 또는 폴더 링크로 같은 위치를 가리키는 경우도 중복으로 처리한다.
2. 로그는 두 프레임 폴더 밖의 `.json` 파일이어야 한다. 입력이 없거나 비어 있으면 실패한다.
3. 출력에 입력 목록에 없는 PNG가 있으면 변경 전에 실패한다. 자동으로 삭제하지 않는다.
   같은 이름의 기존 출력은 재생성하며, 프레임 파일 심볼릭 링크는 거부한다.
4. PNG와 JSON은 같은 폴더의 임시 파일에 완성한 뒤 `os.replace`로 개별 교체한다.
   저장 실패 시 해당 기존 PNG는 유지하고 임시 파일을 정리한다.
5. 사전 검사를 통과해 실행을 시작하면 기존 JSON 로그를 제거한다. 전체 처리와 파일 목록 확인이
   성공한 뒤에만 새 JSON을 발행한다. 실패한 배치를 이전 로그와 혼동하지 않도록 한 결정이다.
6. **전체 디렉터리 단위 원자적 처리는 아니다.** 중간 실패 시 이미 처리한 PNG는 남을 수 있으며,
   이때 성공 로그는 없다. 원인을 해결한 후 같은 명령으로 전체를 재실행한다.
   최종 JSON이 없는 출력은 C/D에 완료 산출물로 넘기지 않는다.
7. 동시 쓰기·입력 수정은 지원하지 않는다. 마지막에 파일명 목록 변화를 검사하지만
   같은 파일명의 내용 변경까지 잠그거나 추적하지는 않는다. 실행 중 원본과 출력은 변경하지 않는다.

CLI는 실패하면 종료 코드 1과 오류 메시지를 출력한다. API는 ValueError/OSError를 호출자에 전달한다.
원본 영상과 프레임은 수정하지 않는다. 최종 원본·고정·적응형 목록 비교는 통합 실행기에서도 수행해야 한다.

## 검증 및 남은 작업

```bash
python -m pytest tests/test_fixed_batch.py tests/test_fixed_batch_cli.py -q
python -m pytest -q
```

합성 PNG로 픽셀 단위 결과·원본 바이트·고정 params·시간 범위·재실행·실패 복구와 실제 CLI를 검증한다.
현재 저장소의 기본 원본 프레임 폴더에는 평가 프레임이 없어 실제 fixed 평가 산출물은 아직 생성하지 않았다.
생성된 PNG·JSON을 소스 변경에 섞어 커밋하기 전에 팀의 데이터 공유 위치를 확인한다.
실제 데이터 튜닝, 1080p 전체 2초 목표(A-10), 금지 함수 검사 도구(A-12)는 별도 작업이다.

2026-11-17 검증: 배치·CLI 테스트 **17 passed**, 전체 **461 passed, 2 skipped**.
생략된 항목은 기존 모델/OCR 환경 의존 테스트다.
