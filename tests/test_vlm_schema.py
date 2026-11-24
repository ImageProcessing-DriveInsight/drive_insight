from src.vlm.schema import validate_vlm_response


def valid_response():
    return {
        "vehicles": ["A white car"],
        "events": [
            {
                "order": 1,
                "content": "A car turns left",
                "frame": 2,
            }
        ],
        "visibility_notes": ["The road is bright"],
        "uncertain": [],
    }


def test_accepts_official_content_format():
    assert validate_vlm_response(valid_response())


def test_accepts_legacy_description_format():
    data = valid_response()
    data["events"][0]["description"] = data["events"][0].pop("content")
    assert validate_vlm_response(data)


def test_rejects_missing_required_field():
    data = valid_response()
    del data["vehicles"]
    assert not validate_vlm_response(data)


def test_rejects_non_string_vehicle():
    data = valid_response()
    data["vehicles"] = [123]
    assert not validate_vlm_response(data)


def test_rejects_event_without_content_or_description():
    data = valid_response()
    data["events"][0].pop("content")
    assert not validate_vlm_response(data)


def test_rejects_invalid_frame_type():
    data = valid_response()
    data["events"][0]["frame"] = "two"
    assert not validate_vlm_response(data)
