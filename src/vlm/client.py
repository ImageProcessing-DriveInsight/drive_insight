import json
import logging
import os
from pathlib import Path

from google import genai
from google.genai import types

from src.vlm.schema import validate_vlm_response


logger = logging.getLogger(__name__)

MODEL_NAME = "gemini-3.8-flash"

SYSTEM_PROMPT = """
You are a dashcam scene understanding assistant.

Analyze the image and return JSON with exactly these fields:
- vehicles: list of strings
- events: list of objects with order, content, frame
- visibility_notes: list of strings
- uncertain: list of strings

Rules:
1. Never read, transcribe, guess, or output license plate characters.
2. If a plate is visible, only say "license plate visible".
3. Do not invent movement or events from a single image.
4. Put uncertain observations in the uncertain field.
5. Return valid JSON only.
"""


def get_gemini_client():
    api_key = os.getenv("GEMINI_API_KEY")

    if not api_key:
        raise ValueError("GEMINI_API_KEY is not set.")

    return genai.Client(api_key=api_key)


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

    client = get_gemini_client()

    image_part = types.Part.from_bytes(
        data=image_path.read_bytes(),
        mime_type=mime_type,
    )

    user_prompt = prompt or SYSTEM_PROMPT

    for attempt in range(2):
        retry_instruction = ""

        if attempt == 1:
            retry_instruction = """
Your previous response did not pass JSON/schema validation.
Please correct it and return valid JSON with exactly the required fields.
Follow the required event structure:
order (integer), content (string), frame (integer).
"""

        response = client.models.generate_content(
            model=MODEL_NAME,
            contents=[
                user_prompt + retry_instruction,
                f"Analyze this as frame {frame_number}.",
                image_part,
            ],
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                temperature=0,
            ),
        )

        try:
            result = json.loads(response.text)

            if validate_vlm_response(result):
                return result

        except (json.JSONDecodeError, TypeError):
            pass

    logger.error(
        "VLM response failed JSON/schema validation after one retry. "
        "Image: %s, frame: %s",
        image_path,
        frame_number,
    )

    raise ValueError(
        "VLM response failed JSON/schema validation after one retry."
    )
