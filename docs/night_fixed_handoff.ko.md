# A 야간 평가 원본·fixed 전달 (#112)

## 범위

2026-11-24 원격 fetch/prune와 develop pull로 확인했다. develop은 최신이며,
D의 실행기·VLM 작업은 `feature/31-shared-utilities-experiment-runner`의 미병합 코드다.
그 브랜치는 읽기만 했고 병합·실행·통합 검증하지 않았다.

이번 작업은 A가 이미 확정한 **야간 평가 30장**만 대상으로 한다. 원본 JPG와 고정 목록이
로컬에 있으므로, 지정한 파일명·원본 해상도로 PNG를 준비하고 기존 A로 고정 보정한다.
B의 전체 원본 통합을 대신하지 않으며, 팀이 정한 source/frame 규칙에 맞춘 단일 조건 전달물이다.
다른 조건의 최종 선정 목록을 A가 새로 고르지 않는다.

**사용자 요청으로 제외:** 전체 pytest, 전체 소스 금지 함수 검사, 전체 조건 통합 점검,
타 팀원 브랜치 병합, OCR/VLM 실행, 전역 로그 합치기. 후보 10,000장 재점검·재추출도 하지 않는다.
아래 검증은 이번 야간 30장 산출물에 한정된다.

## 입력과 설정

- `data/manifests/a_night/evaluation_frames.csv` 및 `evaluation_names.csv`, `COMPLETE.json` 사용.
- 고정 CSV·선정 JPG의 해시와 장면별 6장, 5장면/30장을 확인한다.
  튜닝 메타데이터는 중복 배제에만 사용하고 튜닝 이미지·라벨을 처리하지 않는다.
- 원본은 `team_data/A_night/71588_night_highway_front/images/`에 있다.
- 1920×1200·uint8 BGR 디코딩 픽셀을 PNG로 보존한다. 크롭·리사이즈·촬영 시각 추정은 없다.
- 기존 A: Gaussian 3×3·σ1.0, gamma 0.75, hist_eq=False,
  Unsharp amount 0.8·σ1.0·threshold 5.0. FIXED_PARAMS는 변경하지 않는다.
  일반/어려운 장면에 서로 다른 설정을 적용하지 않고 평가 결과로 설정을 고르지 않는다.

## 독립 처리와 전달

실제 작업 폴더는 `data/frames/night_eval_20261124/orig/`, `fixed/`다.
야간 로그·스냅샷·검증 보고서는 `data/annotations/night_fixed_20261124/`에 보관한다.
기존 중앙 `data/frames/orig/`, `fixed/`, `results/params/fixed.json`의 비 결과를 합치거나 덮어쓰지 않는다.

처리 단계:

1. 확정 목록과 원본 해시를 확인한 후 지정 이름으로 PNG 30장을 준비한다.
2. 그 PNG만 원본 스냅샷을 만들고 기존 enhance_fixed_frames로 처리한다.
3. 야간 orig/fixed/로그의 이름·크기·params·시간, 원본 보존과 저장 픽셀을 검증한다.
4. 원본 30장·fixed 30장·야간 로그·source/frame 대응표·평가 목록·검증·안내문을 ZIP으로 묶는다.
5. 그 ZIP의 CRC와 모든 페이로드 해시를 확인한다. 실제 자료는 모두 Git 제외 경로에 둔다.

전달 ZIP 내부는 표준 `data/frames/orig/`, `data/frames/fixed/`, `results/params/fixed.json` 구조다.
별도 폴더에 먼저 풀어 확인하고, 다른 조건과 통합할 때 기존 원본·결과·fixed.json을 무조건 덮어쓰지 않는다.
특히 ZIP의 fixed.json은 **야간 30장만**의 로그이며 전체 조건 최종 로그가 아니다.

이 전달로 B는 A가 선정한 야간 PNG와 대응표를 받을 수 있고 C·D는 같은 이름의 fixed를 사용할 수 있다.
최종 조건 목록 합치기·다른 조건 처리·전체 점검은 이번 요청 범위 밖에 남긴다.
