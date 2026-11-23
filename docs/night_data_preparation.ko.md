# A 야간 데이터 준비: 선정 전 검사 (#96)

## 범위와 보류 사항

A는 야간 목록 선정과 고정 보정 결과를 담당한다. 원본 PNG 준비·전체 평가표 병합은 B,
차량 라벨 변환·검출·OCR·집계는 C, VLM은 D 담당이다. 이 문서는 그 인터페이스를
준비하며 B/C의 평가기를 변경하지 않는다.

2026-11-23 C 답변으로 아래 선정 규칙이 확정됐다(#98). 기존 clips.csv의 추천값
(폭 150, 밝기 20)은 사용하지 않는다. 후보 수 41/137을 재현하지 못하면 멈추고 확인한다.

## 데이터 보관

- `/team_data/`, `/team_data.zip`은 Git 제외. 원본을 이동·덮어쓰기·수정하지 않는다.
- 실제 이미지·라벨·파생 PNG·상세 검사 결과도 Git에 포함하지 않는다.
- 안내 PDF는 별도 검토 없이 커밋하지 않는다. 데이터 공유·원격 VLM 전송 권한은
  각 자료의 조건과 팀 승인을 별도로 확인한다.
- 실행은 로컬에서 하며 이 도구는 데이터를 네트워크로 전송하지 않는다.

## 무결성 검사

```bash
python -m tools.audit_night_data --decode-images \
  --output data/annotations/a_night_audit_20261123.json
```

기본 입력은 `team_data/A_night/71588_night_highway_front`다. 상대 경로는 저장소 루트 기준이다.
기본 보고서는 Git이 무시하는 `data/annotations/`에 저장한다. 기존 보고서를 덮어쓰지 않으므로
재실행 시 새 출력 이름을 사용한다. 출력은 원본 폴더 밖에 둬야 한다.

검사 사항:

- images/labels 아래 상대 경로의 확장자를 제외한 이름으로 일대일 대응.
  대소문자만 다른 중복도 Windows에서 충돌할 수 있어 보고한다.
- 누락 쌍, 손상 JSON, 라벨 이미지 이름, 양수 해상도, 유한 좌표 검사.
- C의 `tools.aihub_vehicles.scene_entry`를 재사용한다. 묶음 라벨이 있는 프레임은
  `group`으로 남기고 폭 100px 이상 차량 보유 프레임 집계에서 제외한다.
- `--decode-images`를 주면 전체 이미지를 디코딩하고 라벨 해상도와 비교한다.
  생략하면 라벨·파일 대응만 검사하므로 이미지 손상 여부는 검증하지 않은 것이다.
- 결과에 장면·프레임별 상태와 라벨 SHA-256을 남기지만 무작위 추출·밝기 계산·보정은 하지 않는다.
  `selection_status=not_selected`, `capture_timing=unknown`을 명시한다.

종료 코드: 0은 검사 항목 무오류, 1은 개별 자료 문제 발견, 2는 잘못된 입력·출력 등 실행 실패다.
이미지 디코딩은 OpenCV 입출력만 사용한다. 실제 촬영 시각·FPS·주행 길이를 추정하지 않는다.
검사 통과는 연속 영상 요구 충족이나 라벨 정답의 사람 검수를 뜻하지 않는다.

## 검증

합성 이미지·라벨로 원본 불변, 한글 경로, 누락 쌍·이름 불일치·손상 입력,
묶음 라벨·차량 폭 경계, 출력 덮어쓰기 방지를 검사한다.
실제 자료의 상세 결과는 로컬 보고서로 보관하며 공개 PR에는 집계값만 기록한다.

## C가 확정한 야간 선정 규칙 (#98)

```bash
python -m tools.select_night_frames
```

도구는 원본·라벨 대응을 다시 검사하고, C와 같은 차량 판정을 적용한다.
장면 6장 이상, complete이면서 폭 100px 이상인 차량이 있는 프레임 수 ×2가
장면 전체 프레임 수 이상이어야 후보이다. 묶음 라벨이 있는 프레임은 분자에서만 빠진다.
밝기는 clips.csv의 mean_gray(기존 요약 방식)를 그대로 쓰며 다시 계산하지 않는다.
5 이상 일반, 미만 어려운 후보다. 41/137이 아니면 목록을 쓰지 않는다.

- 각각 문자열 이름순으로 정렬한 뒤 `random.Random(2026).sample(normal, 5)`와
  `random.Random(2026).sample(hard, 2)`를 **새 생성기 두 개**로 수행한다.
- 추출 순서를 유지해 일반 앞 4개·어려운 첫 1개는 evaluation,
  일반 마지막 1개·어려운 마지막 1개는 tuning이다. 장면 중복은 없다.
- 프레임은 파일명 끝 숫자순으로 정렬하고 `round(i*(n-1)/5)` (i=0..5)로 뽑는다.
  20장이면 0,4,8,11,15,19번째다. 뽑힌 묶음 라벨·차량 없는 프레임도 바꾸지 않는다.
  후보 여부와 프레임 선택은 서로 다른 단계다. 영상·보정·OCR 결과를 보고 다시 고르지 않는다.

기본 출력은 Git 제외된 `data/manifests/a_night/`다.

- `evaluation_frames.csv`(30행), `tuning_frames.csv`(12행):
  `split,condition,scene,difficulty,source,frame,tags,sequence_index,mean_gray`
- `evaluation_names.csv`, `tuning_names.csv`: C의 변환기에 맞춘 `source,frame` 두 열.
- `COMPLETE.json`: 규칙, 후보 수, 추출 순서, CSV·clips.csv·선정 원본/라벨 SHA-256.
  이 파일을 마지막에 쓴다. 없으면 불완전한 출력으로 취급한다.

## A → B 전달 형식: 이번 구현에서 정한 사항

이 파일들은 **A의 전달 목록**이다. B의 기존 video/timestamp 기반 eval_set.csv를
교체하거나 확장하지 않는다. source는 `--root` 기준 `images/Clip_xxx/원본.jpg` 상대경로,
frame은 원본 stem+.png다. C의 변환기는 source의 basename을 사용하므로 호환된다.
출력 frame 이름은 evaluation/tuning 전체에서 대소문자 구분 없이 유일해야 한다.
sequence_index는 **원본 이름의 순번이며 밀리초가 아니다**. timestamp_ms/FPS/길이는 쓰지 않는다.
대표 condition은 low_light, clips.csv에서 tunnel_polygons>0이면 tags=tunnel이다.

B는 evaluation 목록만 `data/frames/orig/`에 PNG로 만들고 tuning은 별도 폴더로 준비한다.
원본 해상도·BGR 픽셀을 유지하고 공간 변환을 하지 않는다. 실제 캡처 시간은 알 수 없으므로
B의 공통 평가표 연결 방식은 별도 합의 대상이다. A가 video timestamp를 만들어 넣지 않는다.
PNG 준비와 C의 차량 라벨 변환을 이 도구가 대신 실행하지 않는다.

출력 폴더가 이미 있으면 재선정·덮어쓰기를 거부한다. 중간 실패로 불완전한 폴더가 남으면
검사 후 별도로 보관하고 재시도한다. 최종 목록 변경은 팀 합의 후 별도 이력으로 남긴다.
