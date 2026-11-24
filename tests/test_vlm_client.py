import json

import pytest

from src.vlm import client as vlm_client


VALID_RESPONSE = {
    "vehicles": ["A white car"],
    "events": [
        {
            "order": 1,
            "content": "A car is visible near the intersection",
            "frame": 2,
        }
    ],
    "visibility_notes": ["The road is bright"],
    "uncertain": [],
}


class FakeResponse:
    def __init__(self, data):
        self.data = data

    def raise_for_status(self):
        pass

    def json(self):
        return self.data


class FakeRequests:
    def __init__(self, responses):
        self.responses = responses
        self.calls = []

    def post(self, url, **kwargs):
        self.calls.append({"url": url, **kwargs})
        return self.responses.pop(0)


def test_retry_once_then_success(tmp_path, monkeypatch):
    image = tmp_path / "frame.png"
    image.write_bytes(b"fake image data")

    fake = FakeRequests([
        FakeResponse({"response": '{"wrong_field": []}'}),
        FakeResponse({"response": json.dumps(VALID_RESPONSE)}),
    ])

    monkeypatch.setattr(vlm_client, "requests", fake)

    result = vlm_client.analyze_frame(image, frame_number=2)

    assert result == VALID_RESPONSE
    assert len(fake.calls) == 2

    for call in fake.calls:
        assert call["json"]["model"] == "qwen3-vl:4b-instruct"
        assert call["json"]["options"]["temperature"] == 0
        assert call["json"]["stream"] is False

    print("PASS: Retry once, then success")


def test_retry_failure_raises_error(tmp_path, monkeypatch):
    image = tmp_path / "frame.png"
    image.write_bytes(b"fake image data")

    fake = FakeRequests([
        FakeResponse({"response": '{"wrong_field": []}'}),
        FakeResponse({"response": '{"still_wrong": []}'}),
    ])

    monkeypatch.setattr(vlm_client, "requests", fake)

    with pytest.raises(ValueError, match="after one retry"):
        vlm_client.analyze_frame(image)

    assert len(fake.calls) == 2

    print("PASS: Retry failure raises ValueError")


def test_missing_image_raises_error(tmp_path):
    image = tmp_path / "missing.png"

    with pytest.raises(FileNotFoundError):
        vlm_client.analyze_frame(image)

    print("PASS: Missing image raises FileNotFoundError")
