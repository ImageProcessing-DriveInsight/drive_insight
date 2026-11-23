
from __future__ import annotations

import csv
from pathlib import Path
from typing import Any


def score_vlm(
    verify_sheet: str | Path,
    labels: dict[str, str],
    output_path: str | Path = "results/score.csv",
) -> dict[str, Any]:
    """Calculate scene-fact accuracy and hallucination rate."""

    with open(verify_sheet, "r", encoding="utf-8") as file:
        rows = list(csv.DictReader(file))

    correct = 0
    labeled_facts = 0
    unsupported = 0
    checkable_claims = 0
    unverifiable_claims = 0

    for row in rows:
        claim = row["claim"]
        checkability = row["checkability"].strip().lower()
        label = labels.get(claim, "").strip().lower()

        if checkability != "checkable":
            if label == "unverifiable" or checkability == "unverifiable":
                unverifiable_claims += 1
            continue

        checkable_claims += 1

        if label == "supported":
            labeled_facts += 1
            correct += 1
        elif label == "unsupported":
            labeled_facts += 1
            unsupported += 1

    scene_accuracy = (
        correct / labeled_facts * 100
        if labeled_facts > 0 else None
    )

    hallucination_rate = (
        unsupported / checkable_claims * 100
        if checkable_claims > 0 else None
    )

    result = {
        "scene_accuracy": scene_accuracy,
        "hallucination_rate": hallucination_rate,
        "correct": correct,
        "labeled_facts": labeled_facts,
        "unsupported": unsupported,
        "checkable_claims": checkable_claims,
        "unverifiable_claims": unverifiable_claims,
    }

    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)

    with open(output, "w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=result.keys())
        writer.writeheader()
        writer.writerow(result)

    return result
