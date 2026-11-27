from __future__ import annotations

import csv
from pathlib import Path
from typing import Any


SCORE_COLUMNS = [
    "condition",
    "clip",
    "facts",
    "facts_correct",
    "checkable_claims",
    "unsupported_claims",
    "uncheckable_claims",
    "scene_acc",
    "hallucination_rate",
]


def score_vlm(
    verify_sheet: str | Path,
    labels: dict[str, str],
    output_path: str | Path = "results/vlm/score.csv",
    condition: str = "unknown",
    clip: str = "unknown",
) -> dict[str, Any]:
    """Calculate VLM scene accuracy and hallucination rate."""

    with open(verify_sheet, "r", encoding="utf-8") as file:
        rows = list(csv.DictReader(file))

    correct = 0
    facts = 0
    unsupported = 0
    checkable_claims = 0
    uncheckable_claims = 0

    for row in rows:
        claim = row["claim"]
        checkability = row["checkability"].strip().lower()
        label = labels.get(claim, row.get("label", "")).strip().lower()

        if checkability in {"uncheckable", "unverifiable"}:
            uncheckable_claims += 1
            continue

        if label in {"uncheckable", "unverifiable"}:
            uncheckable_claims += 1
            continue

        if checkability != "checkable":
            continue

        checkable_claims += 1

        if label in {"correct", "supported"}:
            facts += 1
            correct += 1
        elif label == "unsupported":
            facts += 1
            unsupported += 1

    scene_acc = correct / facts if facts > 0 else None

    hallucination_rate = (
        unsupported / checkable_claims * 100
        if checkable_claims > 0 else None
    )

    result = {
        "condition": condition,
        "clip": clip,
        "facts": facts,
        "facts_correct": correct,
        "checkable_claims": checkable_claims,
        "unsupported_claims": unsupported,
        "uncheckable_claims": uncheckable_claims,
        "scene_acc": scene_acc,
        "hallucination_rate": hallucination_rate,
        # Keep legacy return keys for existing tests/callers.
        "scene_accuracy": scene_acc * 100 if scene_acc is not None else None,
        "correct": correct,
        "labeled_facts": facts,
        "unsupported": unsupported,
        "unverifiable_claims": uncheckable_claims,
    }

    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)

    # One row per condition and clip: replace this pair's old row, keep the rest.
    kept = []
    if output.exists():
        with open(output, "r", newline="", encoding="utf-8") as file:
            kept = [
                row for row in csv.DictReader(file)
                if (row.get("condition"), row.get("clip")) != (condition, clip)
            ]

    new_row = {
        key: "" if result[key] is None else result[key]
        for key in SCORE_COLUMNS
    }

    with open(output, "w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(
            file, fieldnames=SCORE_COLUMNS, extrasaction="ignore"
        )
        writer.writeheader()
        writer.writerows(kept)
        writer.writerow(new_row)

    return result
