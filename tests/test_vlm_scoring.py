import csv

from src.vlm.scoring import score_vlm


def create_verify_sheet(tmp_path, rows):
    verify = tmp_path / "verify.csv"

    with open(verify, "w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(
            file,
            fieldnames=["claim", "checkability", "label"],
        )
        writer.writeheader()
        writer.writerows(rows)

    return verify


def test_correct_and_unsupported_claims(tmp_path):
    rows = [
        {"claim": "Car", "checkability": "checkable", "label": ""},
        {"claim": "Truck", "checkability": "checkable", "label": ""},
    ]

    verify = create_verify_sheet(tmp_path, rows)
    labels = {
        "Car": "correct",
        "Truck": "unsupported",
    }

    result = score_vlm(verify, labels, tmp_path / "score.csv")

    assert result["scene_accuracy"] == 50.0
    assert result["hallucination_rate"] == 50.0


def test_uncheckable_claim_is_excluded(tmp_path):
    rows = [
        {"claim": "Car", "checkability": "checkable", "label": ""},
        {"claim": "Speed", "checkability": "uncheckable", "label": ""},
    ]

    verify = create_verify_sheet(tmp_path, rows)
    labels = {
        "Car": "unsupported",
        "Speed": "uncheckable",
    }

    result = score_vlm(verify, labels, tmp_path / "score.csv")

    assert result["scene_accuracy"] == 0.0
    assert result["hallucination_rate"] == 100.0
    assert result["uncheckable_claims"] == 1


def test_no_checkable_claims_returns_none(tmp_path):
    rows = [
        {"claim": "Dark road", "checkability": "uncheckable", "label": ""},
    ]

    verify = create_verify_sheet(tmp_path, rows)

    result = score_vlm(
        verify,
        {"Dark road": "uncheckable"},
        tmp_path / "score.csv",
    )

    assert result["scene_accuracy"] is None
    assert result["hallucination_rate"] is None
    assert result["uncheckable_claims"] == 1
