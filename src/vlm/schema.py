from typing import Any


REQUIRED_FIELDS = {
    "vehicles",
    "events",
    "visibility_notes",
    "uncertain",
}


def validate_vlm_response(data: dict[str, Any]) -> bool:
    """Validate the VLM scene summary structure."""

    if not isinstance(data, dict):
        return False

    if set(data.keys()) != REQUIRED_FIELDS:
        return False

    for field in ("vehicles", "visibility_notes", "uncertain"):
        if not isinstance(data[field], list):
            return False

        if not all(isinstance(item, str) for item in data[field]):
            return False

    if not isinstance(data["events"], list):
        return False

    for event in data["events"]:
        if not isinstance(event, dict):
            return False

        if not {"order", "frame"}.issubset(event.keys()):
            return False

        has_content = isinstance(event.get("content"), str)
        has_description = isinstance(event.get("description"), str)

        if not (has_content or has_description):
            return False

        if type(event["order"]) is not int:
            return False

        if type(event["frame"]) is not int:
            return False

    return True
