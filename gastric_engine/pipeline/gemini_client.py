"""Single Gemini call site. Returns parsed JSON.

Import-guarded: the SDK is only imported when an actual call is made, so the
rest of the repo (and the test suite) imports without `google-genai` installed.
"""

from __future__ import annotations

import base64
import io
import json
import os
import re
import urllib.error
import urllib.request
from typing import Any

DEFAULT_MODEL = "gemini-2.5-flash"
DEFAULT_OPENROUTER_MODEL = "nvidia/nemotron-3-ultra-550b-a55b:free"
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"

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


def _env_first(*names: str) -> str | None:
    for name in names:
        value = os.environ.get(name)
        if value:
            return value.strip().strip('"').strip("'")
    return None


def _resolve_openrouter_api_key() -> str:
    key = _env_first("OPENROUTER_API_KEY", "openrouter_api")
    if not key:
        raise RuntimeError(
            "OpenRouter API key is not set. Add OPENROUTER_API_KEY or openrouter_api to your environment."
        )
    return key


def _resolve_openrouter_model(model: str | None) -> str:
    return (
        model
        or _env_first("OPENROUTER_MODEL", "openrouter_model")
        or DEFAULT_OPENROUTER_MODEL
    )


def _openrouter_enabled() -> bool:
    return bool(_env_first("OPENROUTER_API_KEY", "openrouter_api"))


def _image_to_data_url(image: Any) -> str:
    image_format = (getattr(image, "format", None) or "PNG").upper()
    mime = "image/jpeg" if image_format in {"JPG", "JPEG"} else "image/png"
    buffer = io.BytesIO()
    image.save(buffer, format="JPEG" if mime == "image/jpeg" else "PNG")
    encoded = base64.b64encode(buffer.getvalue()).decode("ascii")
    return f"data:{mime};base64,{encoded}"


def _openrouter_message_content(prompt: str, image: Any | None) -> Any:
    if image is None:
        return prompt
    return [
        {"type": "text", "text": prompt},
        {"type": "image_url", "image_url": {"url": _image_to_data_url(image)}},
    ]


def _openrouter_content_text(response: dict) -> str:
    try:
        content = response["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        raise ValueError(f"OpenRouter returned an unexpected response: {response!r}") from exc
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = [
            item.get("text", "")
            for item in content
            if isinstance(item, dict) and item.get("type") in {None, "text"}
        ]
        return "".join(parts)
    raise ValueError(f"OpenRouter returned non-text content: {content!r}")


def _generate_openrouter_json(
    prompt: str,
    *,
    image: Any | None,
    model: str | None,
    urlopen=urllib.request.urlopen,
) -> Any:
    payload = {
        "model": _resolve_openrouter_model(model),
        "messages": [
            {
                "role": "user",
                "content": _openrouter_message_content(prompt, image),
            }
        ],
        "response_format": {"type": "json_object"},
        "temperature": 0,
    }
    request = urllib.request.Request(
        OPENROUTER_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {_resolve_openrouter_api_key()}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://localhost/tummybuddy",
            "X-Title": "TummyBuddy",
        },
        method="POST",
    )
    try:
        with urlopen(request, timeout=60) as response:
            raw = response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"OpenRouter request failed with HTTP {exc.code}: {detail}") from exc
    parsed = json.loads(raw)
    return _parse_json_text(_openrouter_content_text(parsed))


def generate_json(prompt: str, *, image: Any | None = None, model: str | None = None) -> Any:
    """Call the configured model provider with a text prompt/image and parse JSON."""
    if _openrouter_enabled():
        return _generate_openrouter_json(prompt, image=image, model=model)

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
