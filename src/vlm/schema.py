
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

    if not REQUIRED_FIELDS.issubset(data.keys()):
        return False

    for field in REQUIRED_FIELDS:
        if not isinstance(data[field], list):
            return False

    for event in data["events"]:
        if not isinstance(event, dict):
            return False

        if not {"order", "description", "frame"}.issubset(event.keys()):
            return False

        if not isinstance(event["order"], int):
            return False

        if not isinstance(event["description"], str):
            return False

        if not isinstance(event["frame"], int):
            return False

    return True
