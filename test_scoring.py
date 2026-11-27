
import csv
import tempfile
from pathlib import Path

from src.vlm.scoring import score_vlm


def run_test(name, rows, labels, expected_accuracy, expected_hallucination):
    with tempfile.TemporaryDirectory() as temp:
        verify = Path(temp) / "verify.csv"
        output = Path(temp) / "score.csv"

        with open(verify, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(
                f, fieldnames=["claim", "checkability", "label"]
            )
            writer.writeheader()
            writer.writerows(rows)

        result = score_vlm(verify, labels, output)

        assert result["scene_accuracy"] == expected_accuracy
        assert result["hallucination_rate"] == expected_hallucination

        print(f"PASS: {name}", result)


run_test(
    "Case 1: one supported, one unsupported",
    [
        {"claim": "Car", "checkability": "checkable", "label": ""},
        {"claim": "Truck", "checkability": "checkable", "label": ""},
    ],
    {"Car": "supported", "Truck": "unsupported"},
    50.0,
    50.0,
)

run_test(
    "Case 2: unverifiable excluded",
    [
        {"claim": "Car", "checkability": "checkable", "label": ""},
        {"claim": "Speed", "checkability": "unverifiable", "label": ""},
    ],
    {"Car": "unsupported", "Speed": "unverifiable"},
    0.0,
    100.0,
)

run_test(
    "Case 3: no checkable claims",
    [
        {"claim": "Dark road", "checkability": "uncheckable", "label": ""},
    ],
    {},
    None,
    None,
)
