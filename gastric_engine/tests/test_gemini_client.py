import pytest

from gastric_engine.pipeline import gemini_client


def test_strip_json_fences_removes_markdown_wrapper():
    raw = "```json\n{\"a\": 1}\n```"
    assert gemini_client._strip_json_fences(raw) == '{"a": 1}'


def test_strip_json_fences_passes_through_plain_json():
    assert gemini_client._strip_json_fences('{"a": 1}') == '{"a": 1}'


def test_parse_json_text_raises_actionable_error_on_garbage():
    with pytest.raises(ValueError) as exc:
        gemini_client._parse_json_text("not json at all")
    assert "Gemini did not return valid JSON" in str(exc.value)
    assert "not json at all" in str(exc.value)


def test_resolve_api_key_errors_when_missing(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    with pytest.raises(RuntimeError) as exc:
        gemini_client._resolve_api_key()
    assert "GEMINI_API_KEY" in str(exc.value)


def test_openrouter_uses_lowercase_env_keys_and_json_mode(monkeypatch):
    captured = {}

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def read(self):
            return b'{"choices":[{"message":{"content":"{\\"dish\\":\\"fish\\"}"}}]}'

    def fake_urlopen(request, timeout):
        captured["url"] = request.full_url
        captured["headers"] = dict(request.header_items())
        captured["payload"] = request.data.decode("utf-8")
        captured["timeout"] = timeout
        return FakeResponse()

    monkeypatch.setenv("openrouter_api", "test-openrouter-key")
    monkeypatch.setenv("openrouter_model", "nvidia/nemotron-3-ultra-550b-a55b:free")

    result = gemini_client._generate_openrouter_json(
        "Return JSON",
        image=None,
        model=None,
        urlopen=fake_urlopen,
    )

    assert result == {"dish": "fish"}
    assert captured["url"] == "https://openrouter.ai/api/v1/chat/completions"
    assert captured["headers"]["Authorization"] == "Bearer test-openrouter-key"
    assert '"model": "nvidia/nemotron-3-ultra-550b-a55b:free"' in captured["payload"]
    assert '"response_format": {"type": "json_object"}' in captured["payload"]
    assert '"content": "Return JSON"' in captured["payload"]
    assert captured["timeout"] == 60


def test_openrouter_encodes_image_as_data_url(monkeypatch):
    captured = {}

    class FakeImage:
        format = "JPEG"

        def save(self, handle, format):
            assert format == "JPEG"
            handle.write(b"image-bytes")

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def read(self):
            return b'{"choices":[{"message":{"content":"{\\"ok\\":true}"}}]}'

    def fake_urlopen(request, timeout):
        captured["payload"] = request.data.decode("utf-8")
        return FakeResponse()

    monkeypatch.setenv("openrouter_api", "test-openrouter-key")
    monkeypatch.setenv("openrouter_model", "nvidia/nemotron-3-ultra-550b-a55b:free")

    assert gemini_client._generate_openrouter_json(
        "Analyze",
        image=FakeImage(),
        model=None,
        urlopen=fake_urlopen,
    ) == {"ok": True}
    assert '"type": "text"' in captured["payload"]
    assert '"type": "image_url"' in captured["payload"]
    assert "data:image/jpeg;base64,aW1hZ2UtYnl0ZXM=" in captured["payload"]


def test_generate_json_prefers_openrouter_when_configured(monkeypatch):
    monkeypatch.setenv("openrouter_api", "test-openrouter-key")
    monkeypatch.setenv("openrouter_model", "test-openrouter-model")

    def fake_generate(prompt, *, image, model):
        assert prompt == "Return JSON"
        assert image is None
        assert model is None
        return {"provider": "openrouter"}

    monkeypatch.setattr(gemini_client, "_generate_openrouter_json", fake_generate)

    assert gemini_client.generate_json("Return JSON") == {"provider": "openrouter"}
