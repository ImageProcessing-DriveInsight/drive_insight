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
- CLI는 읽기 전용 작업자 4개를 사용한다(`--workers 1..8`). 선정의 라벨 검사도 4개를 쓴다.
  완료 순서와 관계없이 결과를 원본 경로순으로 정렬하며, 직렬·병렬 결과 동일성을 테스트한다.
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

## A 고정 보정 산출물 검증 (#99)

B가 모든 조건의 최종 evaluation PNG만 `data/frames/orig/`에 준비한 뒤 실행한다.
tuning은 별도 폴더에 두며 evaluation과 합치지 않는다. 이 명령은 아직 없는 B 산출물을
만들어낸 것으로 간주하지 않으며, C/D의 평가를 대신하지 않는다.

```bash
# 보정 전에 원본 파일명·SHA-256·해상도 기록 (새 파일만 허용)
python -m tools.verify_fixed_batch snapshot --snapshot data/annotations/fixed_orig_snapshot.json
# 기존 A-09 실행기: 모든 프레임에 동일 FIXED_PARAMS, 파일 I/O 포함 시간도 별도 기록
python -m src.dip.batch
# 실행 전 스냅샷과 대조: 원본 불변·파일 목록·크기·파라미터·시간 기록 확인
python -m tools.verify_fixed_batch verify --snapshot data/annotations/fixed_orig_snapshot.json
```

튜닝은 `--orig`, `--fixed`, `--params`, `--snapshot`으로 독립 경로를 주고,
batch에도 `--input-dir`, `--output-dir`, `--params-path`를 맞춰 준다.
원본 스냅샷을 보정 후에 만들어 원본 보존 증거로 사용하면 안 된다.

검증 범위는 PNG 목록 일치, 원본 바이트 보존, 원본/fixed 해상도 일치,
모든 로그의 동일 FIXED_PARAMS, 유한한 음이 아닌 enhance_ms/total_ms,
total_ms>=enhance_ms다. 변경·누락·오래된 출력·로그 누락을 실패로 처리한다.
현재 명령은 산출물 계약 검증이며 보정 화질, 프레임 선정의 정당성,
픽셀 연산의 독립적 재계산이나 런타임 경쟁 접근의 완전한 방지는 증명하지 않는다.
실행 중 다른 프로세스가 원본/출력/로그를 변경하지 않도록 한다.

## 처리 시간 측정과 튜닝 정책

- FIXED_PARAMS는 기존 초기 기준값을 유지한다. 튜닝 자료만으로 변경 근거를 기록하고
  확정한 뒤 평가를 실행한다. 야간만 보고 모든 조건의 기준값을 바꾸지 않는다.
- 데이터 해상도는 1920×1200이다. 기존 1920×1080 측정 결과와 구분한다.
- 보정 벤치마크는 기존 도구의 워밍업 2회·측정 5회를 사용한다(이번 운영 선택).
  입력 생성·디코딩·로그 I/O를 제외한 연산 호출 시간이며, batch의 I/O 포함 total_ms와 다르다.
- C의 OCR 모델 초기화(워밍업 1회 제외) 제안은 OCR 담당 범위다. A 로그에서 첫 평가 프레임을
  버리거나 누락시키지 않는다. 워밍업은 별도 호출로 한다.

```bash
python -m tools.benchmark_dip --width 1920 --height 1200 --warmups 2 --repeats 5 \
  --output data/annotations/dip_1920x1200_synthetic.json
```

이는 seed=29 합성 프레임 속도 검증이며 실제 야간의 화질·OCR 개선을 검증하지 않는다.
도구에 들어 있는 1080p 목표 비교 필드도 1920×1200의 합의된 성능 기준으로 해석하지 않는다.
실제 PNG 측정 시 `--image`로 튜닝 프레임을 주고 해상도·환경·실험 조건을 기록한다.

## 로컬 확인 기록 (2026-11-23)

- 원본 10,000장·라벨 10,000개, 500장면: 전체 디코딩·라벨 크기 대조 **오류 0건**.
  complete 8,552장, 묶음 라벨 1,448장으로 C 집계와 일치했다.
- 후보 **일반 41·어려운 137**, 총 178개를 재현했다. 평가 5장면/30장,
  튜닝 2장면/12장으로 고정했고 장면 중복은 없다.
- 전달 CSV 4개의 해시와 선정 원본 이미지 42개의 해시를 재검증했다.
  실제 목록·라벨·이미지·상세 보고서는 Git에 포함하지 않았다.
- 1920×1200 합성 프레임, 워밍업 2·측정 5회, 대량 데이터 검사 종료 후 중앙값:
  Gaussian3/5/9 **392.6/434.1/516.1ms**, Median3/5 **1138.0/1895.8ms**,
  fixed **2022.5ms**(p95 2160.1ms). OS의 다른 부하까지 통제한 전용 실험은 아니다.
  1080p 측정이나 실제 야간 성능·화질·OCR 검증으로 바꾸어 보고하지 않는다.
- 로컬 결과: `data/annotations/a_night_audit_20261123.json`,
  `data/manifests/a_night/`, `data/annotations/dip_1920x1200_synthetic_quiet.json`.
  앞선 동시 검사 부하 측정은 별도 `dip_1920x1200_synthetic.json`에 보존한다.
- B가 전체 평가용 orig PNG를 준비하기 전이므로 최종 fixed PNG·fixed.json 생성과
  실데이터 튜닝은 아직 완료하지 않았다. 기존 FIXED_PARAMS도 변경하지 않았다.
