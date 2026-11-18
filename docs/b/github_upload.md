# GitHub 업로드 순서

통합본 전체를 GitHub에 덮어 올리지 않는다. `upload_groups`에서 해당 기능 폴더 안의 src/tools/docs/tests 및 requirements 파일만 저장소 루트로 드래그한다.
01_io_reference는 기존 #5/#6 작업 확인용이다. 이미 같은 파일이 있으면 다시 올릴 필요 없다.
각 그룹은 이슈 생성 → develop 기준 기능 브랜치 → 업로드 → PR → 리뷰 → rebase merge 순서로 진행한다.
브랜치 번호는 실제 생성된 이슈 번호를 사용한다. 이후 그룹은 앞 그룹이 병합된 develop에서 시작한다.

| 그룹 | 이슈 제목 | 커밋/PR 제목 |
|---|---|---|
| 02_data_labels | [Feature] Add evaluation manifests and label export | [feat] Add evaluation manifests and label export |
| 03_adaptive | [Feature] Implement adaptive enhancement pipeline | [feat] Implement adaptive enhancement pipeline |
| 04_package | [Feature] Build review packages from OCR results | [feat] Build review packages from OCR results |
| 05_sensitivity | [Feature] Add threshold sensitivity experiments | [feat] Add threshold sensitivity experiments |
| 06_cli_docs | [Feature] Add B module commands and readiness checks | [feat] Add B module commands and readiness checks |

## PR 본문 공통 작성법

Related Issue에는 해당 이슈 번호를 적는다. Changes에는 그룹별 변경 내용을 적고,
Checklist의 테스트는 실제 해당 브랜치에서 실행한 결과에 따라 체크한다.
A 연동과 모델 검증이 안 된 상태는 Notes에 명시한다. 모듈 테스트 성공과 실제 영상 성능 검증을 구분한다.

## 그룹별 확인

- 02: `py -m pytest -q tests/test_video_io.py tests/test_b_data.py`
- 03: `py -m pytest -q tests/test_b_adaptive.py`
- 04: `py -m pytest -q tests/test_b_package.py`
- 05: `py -m pytest -q tests/test_b_sensitivity.py`
- 06: `py -m pytest -q`, `py -m tools.b_status`

먼저 `py -m pip install -r requirements-b.txt`로 B 테스트 의존성을 설치한다.
requirements-b.txt는 02 그룹에 포함되어 있으며 기존 requirements-plate.txt 등은 덮어쓰지 않는다.
기존 headless OpenCV 환경과 충돌을 피하려면 새 가상환경에 설치한다.

A/C/D 기존 파일이나 다른 팀원의 테스트 파일은 업로드 그룹에 포함하지 않았다.
실제 팀 develop이 제공된 ZIP 이후 바뀌었다면 새 파일과 충돌 여부를 확인하고 적용한다.
