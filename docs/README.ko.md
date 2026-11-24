# 문서

[English](README.md)

## 계획

| 문서 | English | 한국어 |
| --- | --- | --- |
| 역할 분담, 인터페이스, 폴더 구조, WBS, 일정, 리스크 | [team_plan.md](plan/team_plan.md) | [team_plan.ko.md](plan/team_plan.ko.md) |
| 팀원별 기능 명세와 진행 상태 | [feature_spec.md](plan/feature_spec.md) | [feature_spec.ko.md](plan/feature_spec.ko.md) |
| 팀원 C 작업 가이드: 번호판 인식과 평가 | [member_c_guide.md](plan/member_c_guide.md) | [member_c_guide.ko.md](plan/member_c_guide.ko.md) |
| 팀원 C 발표 원고(5분) | — | [member_c_talk.ko.md](plan/member_c_talk.ko.md) |

## 기술 노트

A 데이터 준비: [야간 데이터 선정 전 검사와 담당 경계](night_data_preparation.ko.md).

A 튜닝 검토: [튜닝 전용 후보 비교·시각 검토와 피드백](night_tuning_review.ko.md).

A 비 조건 전달: [기존 고정값 적용·산출물 검증·전달 범위](rain_fixed_handoff.ko.md).

| 문서 | English | 한국어 |
| --- | --- | --- |
| A-01~09: 파라미터, 구현 결정, 실험·성능·연동 가이드 | — | [dip_parameters.ko.md](dip_parameters.ko.md) |
| A-09: 고정 PNG 일괄 생성, JSON 로그, 실패 복구 | — | [fixed_batch.ko.md](fixed_batch.ko.md) |
| A-10: 반복 벤치마크, 성능 개선, 메모리·병렬화 결정 | — | [dip_performance.ko.md](dip_performance.ko.md) |
| A-12: 금지 OpenCV·stub 검사, 허용 목록, 종료 코드와 정적 분석 한계 | — | [forbidden_check.ko.md](forbidden_check.ko.md) |
| C-01: 검출기·OCR 비교, 버전, 라이선스 | [model_selection.md](model_selection.md) | [model_selection.ko.md](model_selection.ko.md) |
| C-04\~C-08: 전처리 비교, 판정 규칙, 파이프라인, CSV 형식, 미국 번호판 | [plate_recognition.md](plate_recognition.md) | [plate_recognition.ko.md](plate_recognition.ko.md) |
| C-09: 평가 지표, 번호판 매칭, 라벨 형식 | [ocr_evaluation.md](ocr_evaluation.md) | [ocr_evaluation.ko.md](ocr_evaluation.ko.md) |
| C-10: 조건별 `summary.csv`, `score.csv` 형식 제안 | [aggregation.md](aggregation.md) | [aggregation.ko.md](aggregation.ko.md) |
| C-11: 조건 간 개선·악화 프레임, 악화 사례 목록, 발표용 이미지 | [comparison.md](comparison.md) | [comparison.ko.md](comparison.ko.md) |
| 번호판 크기·화질 한계, 타임스탬프 선정 기준 | [plate_size_check.md](plate_size_check.md) | [plate_size_check.ko.md](plate_size_check.ko.md) |
| ALL-02, ALL-03: 라벨 초안과 확인 이미지 | [label_draft.md](label_draft.md) | [label_draft.ko.md](label_draft.ko.md) |
| ALL-01: 맑은 날 영상으로 만드는 합성 안개 클립 | [synthetic_fog.md](synthetic_fog.md) | [synthetic_fog.ko.md](synthetic_fog.ko.md) |
| ALL-01: 차량 크기로 평가 타임스탬프 고르기 | [frame_pick.md](frame_pick.md) | [frame_pick.ko.md](frame_pick.ko.md) |
| 직접 찍은 블랙박스 클립 결과: 맑음, 안개, 고정, 적응형 (#78) | [dashcam_results.md](dashcam_results.md) | [dashcam_results.ko.md](dashcam_results.ko.md) |
| AI Hub 차량 라벨로 차량 검출률 재기 (#90) | [aihub_vehicles.md](aihub_vehicles.md) | [aihub_vehicles.ko.md](aihub_vehicles.ko.md) |
| 환경 조건별 결과, 차량 라벨 파일 여러 개 (#92) | [env_report.md](env_report.md) | [env_report.ko.md](env_report.ko.md) |
| 이미지 프레임의 조건·이름 목록 (#108) | [eval_lists.md](eval_lists.md) | [eval_lists.ko.md](eval_lists.ko.md) |

계획 문서는 2026-11-16 기준 저장소 상태를 반영합니다.
