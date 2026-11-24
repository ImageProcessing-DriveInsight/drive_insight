# A 비 조건 fixed 산출물 전달 (#110)

## 이번 평가의 설정 결정

2026-11-24 사용자 지시에 따라 **기존 고정값 A를 변경하지 않고** B가 제공한 비 평가 30장에 적용한다.
추가 튜닝 자료는 기존 고정값을 실행하기 위한 필수 입력이 아니다. 다른 조건에 대한 추가 튜닝과
A/B 최적값 선택은 이번 전달을 막지 않는다. 기존값 유지와 최적값 검증 완료를 혼동하지 않는다.
평가 자료로 후보를 고르거나 설정을 바꾸지 않는다. 장면별로 A/B를 바꾸지도 않는다.

적용값: Gaussian 3×3·sigma=1.0 → gamma=0.75 → hist_eq 생략 →
Unsharp amount=0.8·sigma=1.0·threshold=5.0. `src/dip/fixed.py`의 FIXED_PARAMS는 수정하지 않는다.

## 입력과 처리 범위

B의 `rain_eval_handoff.zip`은 평가 PNG 30장과 `rain_orig_mapping.csv`(source,frame 30행)로 구성된다.
낮 4구간·24장, 밤 1구간·6장이다. 튜닝 자료와 통합 eval_set.csv, adaptive 결과는 포함하지 않는다.
목록을 다시 고르거나 source 파일명 숫자를 촬영 시각·timestamp_ms로 해석하지 않는다.

ZIP 경로·중복·심볼릭 링크·CRC, PNG 형식·디코딩, 대응표 유일성과 PNG 목록 일치를 검사한다.
로컬 `team_data/B_rain/630_rain_front/images/`의 source JPG와 해상도·디코딩 픽셀도 대조한다.
검증된 PNG 바이트를 그대로 `data/frames/orig/`에 준비하며, 원본·기존 산출물은 덮어쓰지 않는다.
입력 ZIP·원본 JPG·전달 PNG의 해시를 남긴다. 실제 프레임·매핑·실행 보고서는 Git에 올리지 않는다.

## 실행과 검증

```bash
python -m tools.verify_fixed_batch snapshot \
  --snapshot data/annotations/rain_fixed_20261124/orig_snapshot.json
python -m src.dip.batch
python -m tools.verify_fixed_batch verify \
  --snapshot data/annotations/rain_fixed_20261124/orig_snapshot.json
```

이 명령은 orig에 비 평가 30장만 준비된 상태를 전제로 한다. 다른 조건 원본이 이미 들어 있으면
파일 목록과 범위를 먼저 확인하고 실행한다. fixed와 JSON 로그의 파일명·개수·해상도·고정 params,
시간의 유한성, 원본 바이트 보존을 검사한다. 저장 PNG의 픽셀도 같은 고정 함수 출력과 대조한다.
이 대조는 산출물 재현·저장 검증이며 화질·OCR 개선을 평가하거나 파라미터를 고르는 절차가 아니다.

## 전달 및 나머지 조건

전달 ZIP에는 `data/frames/fixed/`, `results/params/fixed.json`, source/frame 대응표,
검증 기록·파일 해시 목록·안내문을 담는다. 원본 PNG는 B가 이미 가지고 있으므로 중복 포함하지 않는다.
**비 조건 30장만의 중간 전달물**이며 모든 조건의 최종 결과라고 표현하지 않는다.

다른 조건을 합칠 때 기존 fixed.json을 이 파일로 덮어쓰지 않는다. 파일명 충돌·파라미터 동일성을
확인해 기록을 합치거나, A가 전체 orig 목록을 기준으로 최종 로그를 다시 생성한다.
통합 eval_set.csv와의 최종 대조는 B가 평가표를 제공한 뒤 수행한다.
이후 전달되는 야간·안개·터널·역광 평가 원본에도 같은 기준값을 적용해야 한다.

원본 생성·통합 평가표·adaptive는 B, OCR·차량 검출·집계는 C, VLM은 D 담당으로 유지한다.
이번 작업으로 그 업무나 A의 전체 조건 fixed 전달·최종 통합 점검까지 완료된 것은 아니다.
