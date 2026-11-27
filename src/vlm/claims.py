
from __future__ import annotations

import csv
import random
from pathlib import Path
from typing import Any


def extract_claims(
    vlm_json: dict[str, Any],
    output_path: str | Path = "results/verify_sheet.csv",
    seed: int = 42,
) -> Path:
    """Extract claims and create a blinded verification sheet."""

    claims = []

    # Vehicle claims
    for vehicle in vlm_json.get("vehicles", []):
        if isinstance(vehicle, str) and vehicle.strip():
            claims.append({
                "claim": vehicle.strip(),
                "checkability": "checkable",
                "label": "",
            })
        elif isinstance(vehicle, dict):
            description = vehicle.get("description")
            if isinstance(description, str) and description.strip():
                claims.append({
                    "claim": description.strip(),
                    "checkability": "checkable",
                    "label": "",
                })

    # Event claims: support both current and older JSON formats
    for event in vlm_json.get("events", []):
        if isinstance(event, dict):
            description = event.get("description") or event.get("content")

            if isinstance(description, str) and description.strip():
                claims.append({
                    "claim": description.strip(),
                    "checkability": "checkable",
                    "label": "",
                })

    # Visibility and uncertainty claims
    for field in ("visibility_notes", "uncertain"):
        for item in vlm_json.get(field, []):
            if isinstance(item, str) and item.strip():
                claims.append({
                    "claim": item.strip(),
                    "checkability": "uncheckable",
                    "label": "",
                })

    random.Random(seed).shuffle(claims)

    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)

    with open(output, "w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(
            file,
            fieldnames=["claim", "checkability", "label"],
        )
        writer.writeheader()
        writer.writerows(claims)

    return output
