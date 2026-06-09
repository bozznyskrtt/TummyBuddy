from gastric_engine.pipeline.orchestrator import analyze_meal


def test_orchestrator_chains_stages_into_simulation():
    def fake_image_stage(image):
        return {"dish": "fish and chips", "ingredients": [{"name": "cod", "amount": "150 g"}]}

    def fake_bridge_stage(ingredients):
        assert ingredients == [{"name": "cod", "amount": "150 g"}]
        return {
            "chemicals": {"fat": 30.0, "protein": 28.0},
            "meal_physical": {"solid_volume_ml": 400, "liquid_volume_ml": 100},
            "unknown_compounds": ["malt vinegar"],
        }

    result = analyze_meal(
        b"fake-image",
        clinical_profile={"reflux_gord": True},
        simulation_config={"duration_min": 30, "output_dt_min": 10},
        image_stage=fake_image_stage,
        bridge_stage=fake_bridge_stage,
    )

    assert result["dish"] == "fish and chips"
    assert result["ingredients"][0]["name"] == "cod"
    assert result["chemicals"] == {"fat": 30.0, "protein": 28.0}
    assert "malt vinegar" in result["unknown_compounds"]
    assert "summary" in result
    assert "symptom_curves" in result
    assert "mechanism_curves" in result
