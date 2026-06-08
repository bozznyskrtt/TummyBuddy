"""Concrete characterizer providers used by API wiring."""

from __future__ import annotations

import json
import os
import re
import urllib.request
from dataclasses import dataclass


GEMINI_ENDPOINT = "https://generativelanguage.googleapis.com/v1beta"
DEFAULT_GEMINI_MODEL = "gemini-3.5-flash"


@dataclass
class GeminiCharacterizationProvider:
    api_key: str
    model: str = DEFAULT_GEMINI_MODEL
    timeout_s: float = 20.0

    def __call__(self, substance: str, *, kb, evidence: list[dict]) -> dict:
        request = urllib.request.Request(
            f"{GEMINI_ENDPOINT}/models/{self.model}:generateContent",
            data=json.dumps(_request_body(substance, kb, evidence)).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "x-goog-api-key": self.api_key,
            },
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=self.timeout_s) as response:
            payload = json.loads(response.read().decode("utf-8"))
        return _parse_gemini_payload(payload)


def build_agent_provider():
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        return None
    return GeminiCharacterizationProvider(
        api_key=api_key,
        model=os.environ.get("GEMINI_MODEL", DEFAULT_GEMINI_MODEL),
        timeout_s=float(os.environ.get("GEMINI_TIMEOUT_S", "20")),
    )


def _request_body(substance: str, kb, evidence: list[dict]) -> dict:
    schema_dimensions = kb.property_schema["dimensions"]
    return {
        "contents": [
            {
                "parts": [
                    {
                        "text": (
                            "Characterize this ingestible substance for a deterministic "
                            "gastric physics simulator.\n"
                            f"Substance: {substance}\n"
                            f"Evidence JSON: {json.dumps(evidence, sort_keys=True)}\n"
                            "Return only JSON with keys properties, confidence, metadata. "
                            "properties must contain these dimensions with numeric values "
                            "in 0..1 unless the dimension is enzyme_targets: "
                            f"{json.dumps(schema_dimensions, sort_keys=True)}. "
                            "metadata.citations should list sources used. Do not produce "
                            "symptom curves or predictions."
                        )
                    }
                ]
            }
        ],
        "generationConfig": {
            "responseMimeType": "application/json",
            "temperature": 0.1,
        },
    }


def _parse_gemini_payload(payload: dict) -> dict:
    try:
        text = payload["candidates"][0]["content"]["parts"][0]["text"]
    except (KeyError, IndexError, TypeError) as exc:
        raise ValueError("Gemini response did not include candidate text") from exc
    return json.loads(_json_text(text))


def _json_text(text: str) -> str:
    stripped = text.strip()
    if stripped.startswith("```"):
        match = re.search(r"```(?:json)?\s*(.*?)\s*```", stripped, flags=re.DOTALL)
        if match:
            return match.group(1).strip()
    return stripped
