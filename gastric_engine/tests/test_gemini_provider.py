import json


class _FakeResponse:
    def __init__(self, payload: dict):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def read(self):
        return json.dumps(self.payload).encode("utf-8")


def test_gemini_provider_posts_generate_content_and_parses_property_vector(monkeypatch):
    from gastric_engine.characterization.providers import GeminiCharacterizationProvider
    from gastric_engine.knowledge_base.loader import load_knowledge_base

    captured = {}

    def fake_urlopen(request, timeout):
        captured["url"] = request.full_url
        captured["headers"] = dict(request.header_items())
        captured["body"] = json.loads(request.data.decode("utf-8"))
        captured["timeout"] = timeout
        return _FakeResponse(
            {
                "candidates": [
                    {
                        "content": {
                            "parts": [
                                {
                                    "text": json.dumps(
                                        {
                                            "properties": {
                                                "osmotic_coeff": 0.9,
                                                "fermentability": 1.4,
                                                "enzyme_targets": {},
                                            },
                                            "confidence": 0.77,
                                            "metadata": {
                                                "citations": [
                                                    {
                                                        "source": "Gemini",
                                                        "url": "https://ai.google.dev/",
                                                    }
                                                ]
                                            },
                                        }
                                    )
                                }
                            ]
                        }
                    }
                ]
            }
        )

    monkeypatch.setattr(
        "gastric_engine.characterization.providers.urllib.request.urlopen",
        fake_urlopen,
    )

    provider = GeminiCharacterizationProvider(
        api_key="test-key",
        model="gemini-test-model",
        timeout_s=4.0,
    )
    result = provider("dragonfruit_extract", kb=load_knowledge_base(), evidence=[])

    assert captured["url"].endswith("/models/gemini-test-model:generateContent")
    assert captured["headers"]["X-goog-api-key"] == "test-key"
    assert captured["timeout"] == 4.0
    assert "dragonfruit_extract" in captured["body"]["contents"][0]["parts"][0]["text"]
    assert result["confidence"] == 0.77
    assert result["metadata"]["citations"][0]["source"] == "Gemini"
    assert result["properties"]["osmotic_coeff"] == 0.9
    assert result["properties"]["fermentability"] == 1.4


def test_api_route_uses_gemini_provider_when_enabled(monkeypatch, tmp_path):
    from gastric_engine.api.routes import simulate_endpoint

    monkeypatch.setenv("GASTRIC_ENGINE_CHARACTERIZER_MODE", "agent")
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    monkeypatch.setenv("GASTRIC_ENGINE_CHARACTERIZATION_CACHE", str(tmp_path / "cache.json"))

    def fake_call(self, substance, *, kb, evidence):
        return {
            "properties": {**kb.property_schema["defaults"], "osmotic_coeff": 0.8},
            "confidence": 0.81,
            "metadata": {"citations": [{"source": "Gemini", "url": "https://ai.google.dev/"}]},
        }

    monkeypatch.setattr(
        "gastric_engine.characterization.providers.GeminiCharacterizationProvider.__call__",
        fake_call,
    )

    response = simulate_endpoint(
        {
            "chemicals": {"dragonfruit_extract": 5},
            "meal_physical": {"solid_volume_ml": 50, "liquid_volume_ml": 250},
            "clinical_profile": {},
            "simulation_config": {"duration_min": 20, "output_dt_min": 10},
        }
    )

    assert response["unknown_compounds"] == []
    assert response["summary"]["confidence"] == "medium"
    assert response["metadata"]["characterized_substances"] == [
        {
            "substance": "dragonfruit_extract",
            "source": "agent",
            "confidence": 0.81,
            "metadata": {
                "citations": [{"source": "Gemini", "url": "https://ai.google.dev/"}]
            },
        }
    ]
