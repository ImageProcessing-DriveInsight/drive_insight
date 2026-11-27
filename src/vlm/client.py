import base64
import json
import logging
import os
from pathlib import Path

import requests

from src.vlm.schema import validate_vlm_response


logger = logging.getLogger(__name__)

MODEL_NAME = "qwen3-vl:4b-instruct"
# Used only on the retry after a reply hit the num_predict limit.
RETRY_REPEAT_PENALTY = 1.3
OLLAMA_URL = os.getenv(
    "OLLAMA_URL",
    "http://localhost:11434",
)

SYSTEM_PROMPT = """
You are a dashcam scene understanding assistant.

Analyze the image carefully  and return JSON with exactly these fields:
- vehicles: list of strings
- events: list of objects with order, content, frame
- visibility_notes: list of strings
- uncertain: list of strings

Rules:
1. Detect all clearly visible vehicles, including vehicles in the distance.
2. Do not return an empty vehicles list when vehicles are clearly visible.
3. Use simple labels such as car, bus, truck, or motorcycle.
4. If the vehicle type is unclear, use "vehicle".
5. Do not invent vehicles that cannot be visually confirmed.
6. Never read, transcribe, guess, or output license plate characters.
7. If a plate is visible, only say "license plate visible".
8. Do not invent movement or events from a single image.
9. Describe only what is visibly confirmed.
10. Distinguish fog, mist, rain, and low-light conditions.
11. Do not infer rain only from poor visibility.
12. Put uncertain observations in the uncertain field.
13. Return valid JSON only.
"""


def get_ollama_url():
    """Return the Ollama API URL."""
    return OLLAMA_URL.rstrip("/") + "/api/generate"


def analyze_frame(image_path, prompt=None, frame_number=1):
    image_path = Path(image_path)

    if not image_path.is_file():
        raise FileNotFoundError(f"Image not found: {image_path}")

    mime_type = {
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".webp": "image/webp",
    }.get(image_path.suffix.lower())

    if mime_type is None:
        raise ValueError("Unsupported image format.")

    image_data = base64.b64encode(
        image_path.read_bytes()
    ).decode("utf-8")

    user_prompt = (
        prompt or SYSTEM_PROMPT
    ) + f"\nAnalyze this as frame {frame_number}."

    payload = {
        "model": MODEL_NAME,
        "prompt": user_prompt,
        "images": [image_data],
        "stream": False,
        "format": "json",
        "options": {
            "temperature": 0,
            "num_predict": 1024,
        },
    }

    hit_token_limit = False

    for attempt in range(2):
        if attempt == 1 and hit_token_limit:
            # At temperature 0 a reply that loops on one word until
            # num_predict loops the same way again; penalise repeats.
            payload = {
                **payload,
                "options": {
                    **payload["options"],
                    "repeat_penalty": RETRY_REPEAT_PENALTY,
                },
            }
        if attempt == 1:
            payload["prompt"] += """
Your previous response failed JSON/schema validation.
Return exactly the required four fields.
Each event must contain integer order, string content, and integer frame.
Return JSON only.
"""

        try:
            response = requests.post(
                get_ollama_url(),
                json=payload,
                timeout=300,
            )
            response.raise_for_status()
            response_data = response.json()
            hit_token_limit = response_data.get("done_reason") == "length"

            result = json.loads(
                response_data.get("response", "")
            )

            if validate_vlm_response(result):
                return result

            logger.warning(
                "Ollama response failed schema validation. "
                "Attempt: %s, image: %s",
                attempt + 1,
                image_path,
            )

        except (
            requests.RequestException,
            json.JSONDecodeError,
            TypeError,
        ) as error:
            logger.warning(
                "Ollama request/JSON error. "
                "Attempt: %s, image: %s, error: %s",
                attempt + 1,
                image_path,
                error,
            )

    logger.error(
        "VLM response failed JSON/schema validation after one retry. "
        "Image: %s, frame: %s",
        image_path,
        frame_number,
    )

    raise ValueError(
        "VLM response failed JSON/schema validation after one retry."
    )
