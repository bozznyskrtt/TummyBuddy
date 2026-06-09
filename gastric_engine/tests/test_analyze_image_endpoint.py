from gastric_engine.api import routes


def test_analyze_image_endpoint_uses_orchestrator(monkeypatch):
    def fake_analyze_meal(image, **kwargs):
        assert image == b"bytes"
        assert kwargs["clinical_profile"] == {"reflux_gord": True}
        return {"dish": "ramen", "summary": {"main_symptom": "bloating"}}

    monkeypatch.setattr(routes, "analyze_meal", fake_analyze_meal)

    result = routes.analyze_image_endpoint(
        b"bytes", clinical_profile={"reflux_gord": True}
    )
    assert result["dish"] == "ramen"
    assert result["summary"]["main_symptom"] == "bloating"
