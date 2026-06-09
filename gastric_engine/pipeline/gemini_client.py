"""Single Gemini call site. Returns parsed JSON.

Import-guarded: the SDK is only imported when an actual call is made, so the
rest of the repo (and the test suite) imports without `google-genai` installed.
"""

from __future__ import annotations

import json
import os
import re
from typing import Any

DEFAULT_MODEL = "gemini-2.5-flash"

_FENCE_RE = re.compile(r"^```(?:json)?\s*|\s*```$", re.IGNORECASE)


def _strip_json_fences(text: str) -> str:
    cleaned = text.strip()
    cleaned = _FENCE_RE.sub("", cleaned)
    return cleaned.strip()


def _parse_json_text(text: str) -> Any:
    try:
        return json.loads(_strip_json_fences(text))
    except json.JSONDecodeError as exc:
        raise ValueError(
            f"Gemini did not return valid JSON. Raw response: {text!r}"
        ) from exc


def _resolve_api_key() -> str:
    key = os.environ.get("GEMINI_API_KEY")
    if not key:
        raise RuntimeError(
            "GEMINI_API_KEY is not set. Add it to your environment or .env file."
        )
    return key


def _resolve_model(model: str | None) -> str:
    return model or os.environ.get("GEMINI_MODEL") or DEFAULT_MODEL


def generate_json(prompt: str, *, image: Any | None = None, model: str | None = None) -> Any:
    """Call Gemini with a text prompt (and optional PIL image) and parse JSON."""
    from google import genai  # local import: only needed for real calls
    from google.genai import types

    client = genai.Client(api_key=_resolve_api_key())
    contents: list[Any] = [image, prompt] if image is not None else [prompt]
    response = client.models.generate_content(
        model=_resolve_model(model),
        contents=contents,
        config=types.GenerateContentConfig(response_mime_type="application/json"),
    )
    return _parse_json_text(response.text)
