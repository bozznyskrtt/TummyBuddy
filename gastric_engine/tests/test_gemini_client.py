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
