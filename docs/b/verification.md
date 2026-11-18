# 검증 결과

2026-11-17 제공된 develop 스냅샷과 B 추가 코드를 통합하여 실행했다.

- `python -m pytest -q -rs`: **171 passed, 2 skipped**, 실패 0건.
- 스킵 1: YOLO 가중치가 없어 실제 차량 모델 테스트 생략.
- 스킵 2: 한글 폰트가 없어 글자 렌더링을 사용하는 OCR 관련 테스트 생략.
- 기존 환경 anyio pytest 플러그인의 deprecated API 경고 1건.
- 기존 develop 파일의 바이트 비교 결과: 변경/삭제 0건. B 파일만 추가했다.
- Python 3.12 / NumPy 2.3.5 / OpenCV 4.14.0 / pytest 9.2.0 / Linux.
- b_cli, b_labels, sensitivity 도움말 및 b_status 실행 성공.

B 테스트: I/O round trip·최근접 타임스탬프·원본 보호, NumPy 품질 측정, 규칙 경계값,
A 함수 주입 계약, 일괄 프레임, 보정 영상 메타데이터, 라벨 pending 차단·범위 검사·C 평가 입력,
C CSV 좌표·미검출·누락 구분, HTML 이스케이프, 원본 SHA-256,
배율별 C run_ocr/eval_ocr 재실행과 출력 경로 격리, OpenCV 연산 제한.

C run_ocr/eval_ocr 통합 테스트는 실제 제공 코드를 사용하되 모델 호출만 대역으로 치환했다.
실제 비 영상, 실제 정답 라벨, A의 apply_ops/fixed_enhance, D VLM이 없어 실제 처리 성능/인식 개선/전체 실행기 통합은 미검증이다.
형식 도구만 준비했으며 실제 정답 라벨과 평가표를 생성했다고 주장하지 않는다.
