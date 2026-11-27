# 이미지 프레임 목록 (#108)

[English](eval_lists.md)

AI Hub 프레임은 영상이 아니라 이미지 시퀀스에서 나와 타임스탬프가 없습니다. 그래서 `data/eval_set.csv`로는
조건을 알 수 없고, 팀원이 평가 프레임을 CSV 목록으로 넘깁니다(`source`: 원본 이미지, `frame`:
`data/frames/orig/`의 PNG 이름). `tools/eval_lists.py`는 이 목록들을 C의 도구가 읽는 파일 두 개로 만듭니다.
목록이 늘어날 때마다 최종 실행을 같은 방식으로 다시 할 수 있습니다.

```
python tools/eval_lists.py --list data/manifests/a_night/evaluation_frames.csv low_light --list data/annotations/rain_orig_mapping.csv rain
python tools/aihub_vehicles.py <야간 라벨> <비 라벨> --names data/annotations/eval_names.csv
python tools/env_report.py --scenes data/annotations/scenes.json data/annotations/aihub_vehicles.json --envs data/annotations/envs.csv
```

새 목록(터널, 역광)은 `--list 파일 조건`을 하나 더 붙이고 세 명령을 다시 실행합니다. 출력은 통째로 다시 씁니다.

## 출력

| 파일 | 열 | 읽는 곳 |
| --- | --- | --- |
| `data/annotations/envs.csv` | `frame`, `env`, `clip` | `tools/env_report.py --envs` ([노트](env_report.ko.md)) |
| `data/annotations/eval_names.csv` | `source`, `frame` | `tools/aihub_vehicles.py --names` ([노트](aihub_vehicles.ko.md)) |

조건별 프레임 수와 그중 `data/frames/orig/`에 이미 있는 수도 출력합니다. 예를 들어 야간 PNG가 아직 없으면
`low_light: 30 frames, 0 in data/frames/orig`입니다.

## 입력

- 목록마다 조건을 같이 줍니다. 조건 열이 없는 목록(B의 비 목록)이 있기 때문입니다. `condition` 열이 있으면
  (A의 야간 목록) 준 조건과 같아야 합니다.
- `clip`은 목록에 `clip`이나 `scene` 열이 있으면 그 값, 없으면 빈칸입니다. `env_report`는 그 clip의 VLM 행에
  프레임의 조건을 붙이므로, 이 프레임들에 대한 D의 VLM 행도 같은 값을 써야 합니다.
- 평가 목록만 줍니다. 튜닝 목록은 평가하지 않습니다.

다음 경우에는 멈춥니다: `source`나 `frame` 열이 없는 목록, 빈 목록, PNG 이름이 아닌 frame, 두 번 나온 프레임,
파일 이름이 같은 source 두 개(`aihub_vehicles`가 파일 이름으로 라벨을 찾음), 준 조건과 다른 `condition` 열,
영문·숫자·`_`·`-` 외의 글자가 든 조건 이름, 조건이 두 개인 clip.

## 확인한 것

- 11/24에 A의 야간 목록(30장)과 B의 비 목록(30장)으로 돌렸습니다. 이름 목록은 손으로 만든 것과 같았고, 그걸로
  만든 차량 라벨은 바이트까지 같았습니다(60장, 묶음 라벨 없는 54장, 차량 196대). `data/frames/orig/`의 78장
  모두 조건이 붙었습니다.
- 테스트(`tests/test_eval_lists.py`)는 두 형식의 가짜 목록을 쓰고, 출력을 `env_report`와 `aihub_vehicles`로
  다시 읽으며, 멈추는 경우를 모두 확인합니다.

## 데이터 취급

목록과 출력은 AI Hub 파일 이름을 담고 AI Hub 라벨에서 나옵니다. git이 무시하는 `data/manifests/a_night/`와
`data/annotations/`에 두고, 승인된 팀원에게만 넘깁니다.
