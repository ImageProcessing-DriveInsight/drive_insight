import json

import pytest

from src.vlm import client as vlm_client


VALID_RESPONSE = {
    "vehicles": ["A white car"],
    "events": [
        {
            "order": 1,
            "description": "A car turns left",
            "frame": 2,
        }
    ],
    "visibility_notes": ["The road is bright"],
    "uncertain": [],
}


class FakeResponse:
    def __init__(self, text):
        self.text = text


class FakeModels:
    def __init__(self, responses):
        self.responses = responses
        self.calls = []

    def generate_content(self, **kwargs):
        self.calls.append(kwargs)
        return self.responses.pop(0)


class FakeGeminiClient:
    def __init__(self, responses):
        self.models = FakeModels(responses)


def test_retry_once_then_success(tmp_path, monkeypatch):
    image = tmp_path / "frame.png"
    image.write_bytes(b"fake image data")

    fake = FakeGeminiClient([
        FakeResponse('{"wrong_field": []}'),
        FakeResponse(json.dumps(VALID_RESPONSE)),
    ])

    monkeypatch.setattr(
        vlm_client,
        "get_gemini_client",
        lambda: fake,
    )

    result = vlm_client.analyze_frame(image)

    assert result == VALID_RESPONSE
    assert len(fake.models.calls) == 2

    for call in fake.models.calls:
        assert call["config"].temperature == 0

    print("PASS: Retry once, then success")


def test_retry_failure_raises_error(tmp_path, monkeypatch):
    image = tmp_path / "frame.png"
    image.write_bytes(b"fake image data")

    fake = FakeGeminiClient([
        FakeResponse('{"wrong_field": []}'),
        FakeResponse('{"still_wrong": []}'),
    ])

    monkeypatch.setattr(
        vlm_client,
        "get_gemini_client",
        lambda: fake,
    )

    with pytest.raises(ValueError, match="after one retry"):
        vlm_client.analyze_frame(image)

    assert len(fake.models.calls) == 2

    print("PASS: Retry failure raises ValueError")
