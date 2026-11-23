# Docs

[한국어](README.ko.md)

## Plan

| Doc | English | 한국어 |
| --- | --- | --- |
| Roles, interfaces, folders, WBS, schedule, risks | [team_plan.md](plan/team_plan.md) | [team_plan.ko.md](plan/team_plan.ko.md) |
| Feature spec by member, with status | [feature_spec.md](plan/feature_spec.md) | [feature_spec.ko.md](plan/feature_spec.ko.md) |
| Member C guide: plate recognition and evaluation | [member_c_guide.md](plan/member_c_guide.md) | [member_c_guide.ko.md](plan/member_c_guide.ko.md) |
| Member C talk script, 5 minutes | — | [member_c_talk.ko.md](plan/member_c_talk.ko.md) |

## Technical notes

A data preparation: [night-data preselection checks and ownership boundaries (Korean)](night_data_preparation.ko.md).

| Doc | English | 한국어 |
| --- | --- | --- |
| A-01 to A-09: parameters, decisions, experiments, performance and integration | — | [dip_parameters.ko.md](dip_parameters.ko.md) |
| A-09: fixed PNG batches, JSON logs and failure recovery | — | [fixed_batch.ko.md](fixed_batch.ko.md) |
| A-10: repeatable benchmarks, speedups, memory and concurrency decisions | — | [dip_performance.ko.md](dip_performance.ko.md) |
| A-12: forbidden OpenCV/stub checks, allowlist, exit codes and static analysis limits | — | [forbidden_check.ko.md](forbidden_check.ko.md) |
| C-01: detector and OCR comparison, versions, licenses | [model_selection.md](model_selection.md) | [model_selection.ko.md](model_selection.ko.md) |
| C-04 to C-08: preprocessing comparison, status rules, pipeline, CSV format, US plates | [plate_recognition.md](plate_recognition.md) | [plate_recognition.ko.md](plate_recognition.ko.md) |
| C-09: metrics, plate matching and label format | [ocr_evaluation.md](ocr_evaluation.md) | [ocr_evaluation.ko.md](ocr_evaluation.ko.md) |
| C-10: `summary.csv` per condition, proposed `score.csv` format | [aggregation.md](aggregation.md) | [aggregation.ko.md](aggregation.ko.md) |
| C-11: better and worse frames between conditions, worse-case list, images for slides | [comparison.md](comparison.md) | [comparison.ko.md](comparison.ko.md) |
| Plate size and degradation limits, guideline for picking timestamps | [plate_size_check.md](plate_size_check.md) | [plate_size_check.ko.md](plate_size_check.ko.md) |
| ALL-02, ALL-03: label drafts and check images | [label_draft.md](label_draft.md) | [label_draft.ko.md](label_draft.ko.md) |
| ALL-01: synthetic fog clips from clear-day clips | [synthetic_fog.md](synthetic_fog.md) | [synthetic_fog.ko.md](synthetic_fog.ko.md) |
| ALL-01: picking evaluation timestamps by vehicle size | [frame_pick.md](frame_pick.md) | [frame_pick.ko.md](frame_pick.ko.md) |
| Results on own dashcam clips: clear, fog, fixed, adaptive (#78) | [dashcam_results.md](dashcam_results.md) | [dashcam_results.ko.md](dashcam_results.ko.md) |
| Vehicle detection rate on AI Hub vehicle labels (#90) | [aihub_vehicles.md](aihub_vehicles.md) | [aihub_vehicles.ko.md](aihub_vehicles.ko.md) |
| Results per environment condition, several vehicle label files (#92) | [env_report.md](env_report.md) | [env_report.ko.md](env_report.ko.md) |

Plan docs reflect the repository as of Nov 16, 2026.
