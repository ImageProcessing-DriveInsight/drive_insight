# A 비·야간 60장 중간 통합 (#114)

## 범위와 결정

이미 검증된 비 30장(#110)과 야간 30장(#112)만 중앙 원본·fixed 폴더와
`results/params/fixed.json`에 합친다. 전체 조건 통합 완료를 의미하지 않는다.
기존 PNG를 덮어쓰지 않고 비 전용 JSON을 먼저 백업한다.
기존 프레임별 파라미터·측정 시간을 그대로 보존하며 재보정·재튜닝하지 않는다.

검증은 두 전달물의 보고서·해시, 파일명 충돌, 설정·코드 호환성,
60장 파일·로그 일치에 한정한다. 전체 pytest·전체 소스 검사·최종 통합 점검,
OCR/VLM·적응형 실행·타 팀원 브랜치 병합은 제외한다.

C의 기존 `tools/eval_lists.py`로 이번 두 조건만의 이름·조건 CSV를 만든다.
비 원본 대응표에는 clip/scene 열이 없으므로 clip은 빈칸으로 유지한다.
VLM 장면 ID를 추정하거나 팀의 전역 목록을 덮어쓰지 않는다.

## 전달 계획

로컬 기록과 전달 ZIP은 Git 제외 경로
`data/annotations/interim_fixed_60_20261124/`에 보관한다.
전달물은 fixed PNG 60장, 병합 로그, 두 조건만의 CSV, 검증 보고서,
README와 체크섬이다. 원본 PNG는 기존 비·야간 전달물을 사용한다.
수신자가 더 많은 조건을 가진 로그를 보유한다면 이 부분 로그로 덮어쓰면 안 된다.

## 실행 결과

2026-11-24 실행 완료. 중앙 `data/frames/orig/`, `data/frames/fixed/`는 각각
60장이고 `results/params/fixed.json`은 60개 기록이다. 비 30장 파일을 그대로 두고
격리 보관한 야간 결과 30장을 추가했다. 두 조건 원본·fixed 120개 파일의 해시가
기존 검증 보고서와 일치한다. 기존 파라미터·프레임별 시간 기록은 변경하지 않았다.
이번 작업은 새로운 성능 측정이 아니다.

비 전용 기존 로그는 다음 위치에 백업했다.
`data/annotations/interim_fixed_60_20261124/backups/rain_fixed_before_merge.json`
기존 비·야간 개별 ZIP과 야간 격리 폴더도 보존했다.

두 조건을 생성한 `ops.py`, `color.py`, `fixed.py`의 SHA-256이 서로 같고 현재 코드와도
일치한다. 로그 설정은 기존 FIXED_PARAMS와 같으며, 모든 측정값이 유한한 음이 아닌 수이고
total_ms ≥ enhance_ms다. 이는 지정한 파일만의 호환성 확인이며 전체 소스 검사가 아니다.
로그는 백업 후 임시 파일로 준비해 원자적으로 교체했다. PNG는 배타적 신규 생성으로
기존 파일 덮어쓰기를 방지했다.

### 전달물

`data/annotations/interim_fixed_60_20261124/interim_fixed_rain_night_60_20261124.zip`

- fixed PNG 60장 + `results/params/fixed.json`
- `eval_names_rain_night.csv`: source,frame 60행
- `envs_rain_night.csv`: frame,env,clip 60행; rain 30행, low_light 30행
- `evaluation_frames_rain_night.csv`: source,frame,condition,scene 60행
- `interim_fixed_validation.json`, README.txt, SHA256SUMS.csv

CSV·검증 보고서는 ZIP 안에서도 `data/annotations/interim_fixed_60_20261124/` 아래에 있다.
C는 조건 분리에 `envs_rain_night.csv`를 --envs로, 원본 대응에
`eval_names_rain_night.csv`를 --names로 사용할 수 있다. 도구의 메타데이터 build 함수만
호출했으며 OCR/VLM 평가 실행은 하지 않았다. 기존 팀 전역 CSV도 변경하지 않았다.

ZIP 67개 항목의 구성·CRC·SHA-256을 확인했다. ZIP SHA-256:
`bba9247eada2f9b2ff3d4960aa9eed33cc923d80b0160fbe99379a690c8d74a6`
병합 fixed.json SHA-256:
`6798226d4b73ef7f9b39bbc3d34872c4d15cfc5d267f170953b65cc25868fa0c`
상세 검증과 전달 해시는 로컬 `interim_fixed_validation.json`, `delivery_receipt.json`에 있다.
이미지·JSON·CSV·ZIP이 모두 Git 제외 대상임도 확인했다.

### 수신자 주의와 남은 범위

원본 PNG는 이 ZIP에 중복 포함하지 않았다. 앞서 전달한 비 원본 30장과 야간 원본 30장을
동일한 파일명으로 사용한다. 비는 1920×1080, 야간은 1920×1200을 유지한다.
비 clip은 원본 대응표에 없으므로 30행 모두 빈칸이다. VLM 연계에 필요한 장면 ID는
담당자가 확정한 대응표를 받기 전까지 추정하지 않는다.

**이 ZIP은 두 조건만의 중간 산출물이다.** 더 많은 조건이 있는 수신자의 fixed.json을
통째로 덮어쓰지 않는다. 파일명 기준으로 충돌을 확인해 합치고 다른 조건을 보존해야 한다.
다른 조건의 고정 보정은 해당 최종 입력을 받은 뒤 진행한다. 전체 조건 최종 통합,
적응형 비교, OCR/VLM, 전체 테스트·소스 검사 완료로 표시하지 않는다.
