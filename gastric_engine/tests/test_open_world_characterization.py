import json


def test_unseen_substance_is_characterized_cached_and_simulated(tmp_path, monkeypatch):
    from gastric_engine.api.routes import simulate_endpoint

    cache_path = tmp_path / "characterization_cache.json"
    monkeypatch.setenv("GASTRIC_ENGINE_CHARACTERIZATION_CACHE", str(cache_path))

    response = simulate_endpoint(
        {
            "chemicals": {"yuzu": 5},
            "meal_physical": {"solid_volume_ml": 50, "liquid_volume_ml": 250},
            "clinical_profile": {},
            "simulation_config": {"duration_min": 20, "output_dt_min": 10},
        }
    )

    assert response["unknown_compounds"] == []
    assert response["summary"]["confidence"] == "low"
    assert response["metadata"]["low_confidence_substances"] == ["yuzu"]
    assert response["metadata"]["characterized_substances"] == [
        {"substance": "yuzu", "source": "stub", "confidence": 0.2}
    ]
    assert max(response["mechanism_curves"]["osmolality"]) > 0.1

    cache = json.loads(cache_path.read_text(encoding="utf-8"))
    assert cache["yuzu"]["source"] == "stub"
    assert cache["yuzu"]["confidence"] == 0.2
    assert set(cache["yuzu"]["properties"]) >= {"osmotic_coeff", "enzyme_targets"}
