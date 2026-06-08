import json


def _agent_payload(kb, **properties):
    vector = dict(kb.property_schema["defaults"])
    vector.update(properties)
    return {
        "properties": vector,
        "confidence": 0.88,
        "metadata": {
            "citations": [
                {
                    "source": "PubChem",
                    "url": "https://pubchem.ncbi.nlm.nih.gov/compound/example",
                }
            ]
        },
    }


def test_agent_enabled_characterization_surfaces_citations_and_clamps_properties(tmp_path):
    from gastric_engine.characterization.cache import CharacterizationCache
    from gastric_engine.core.engine import simulate_core
    from gastric_engine.knowledge_base.loader import load_knowledge_base
    from gastric_engine.physiology.profile_builder import build_profile

    kb = load_knowledge_base()

    def fake_agent(substance, *, kb, evidence):
        assert substance == "agentic_berry"
        assert evidence == []
        return _agent_payload(kb, osmotic_coeff=1.8, fermentability=0.4)

    result = simulate_core(
        {"agentic_berry": 6},
        {"solid_volume_ml": 50, "liquid_volume_ml": 250},
        build_profile({}),
        {"duration_min": 20, "output_dt_min": 10},
        kb=kb,
        characterization_cache=CharacterizationCache(tmp_path / "cache.json"),
        characterization_agent=fake_agent,
        characterization_agent_enabled=True,
    )

    assert result["summary"]["confidence"] == "medium"
    assert result["metadata"]["characterized_substances"] == [
        {
            "substance": "agentic_berry",
            "source": "agent",
            "confidence": 0.88,
            "metadata": {
                "citations": [
                    {
                        "source": "PubChem",
                        "url": "https://pubchem.ncbi.nlm.nih.gov/compound/example",
                    }
                ]
            },
        }
    ]
    assert max(result["mechanism_curves"]["osmolality"]) > 0.2
    assert kb.compounds["agentic_berry"]["properties"]["osmotic_coeff"] == 1.0


def test_agent_disabled_uses_stub_without_calling_provider(tmp_path):
    from gastric_engine.characterization.cache import CharacterizationCache
    from gastric_engine.characterization.characterizer import characterize
    from gastric_engine.knowledge_base.loader import load_knowledge_base

    def raising_agent(substance, *, kb, evidence):
        raise AssertionError("agent should not be called when disabled")

    result = characterize(
        "quiet_substance",
        kb=load_knowledge_base(),
        cache=CharacterizationCache(tmp_path / "cache.json"),
        agent=raising_agent,
        agent_enabled=False,
    )

    assert result.source == "stub"
    assert result.confidence == 0.2


def test_cached_agent_characterization_keeps_repeated_simulations_deterministic(tmp_path):
    from gastric_engine.characterization.cache import CharacterizationCache
    from gastric_engine.core.engine import simulate_core
    from gastric_engine.knowledge_base.loader import load_knowledge_base
    from gastric_engine.physiology.profile_builder import build_profile

    cache_path = tmp_path / "cache.json"
    calls = {"count": 0}

    def fake_agent(substance, *, kb, evidence):
        calls["count"] += 1
        return _agent_payload(kb, osmotic_coeff=0.7, carbonation=0.2)

    request = {
        "chemicals": {"cached_agentic": 5},
        "meal_physical": {"solid_volume_ml": 50, "liquid_volume_ml": 250},
        "physiology": build_profile({}),
        "config": {"duration_min": 30, "output_dt_min": 10},
    }
    first = simulate_core(
        **request,
        kb=load_knowledge_base(),
        characterization_cache=CharacterizationCache(cache_path),
        characterization_agent=fake_agent,
        characterization_agent_enabled=True,
    )
    second = simulate_core(
        **request,
        kb=load_knowledge_base(),
        characterization_cache=CharacterizationCache(cache_path),
        characterization_agent=lambda substance, *, kb, evidence: (_ for _ in ()).throw(
            AssertionError("cached result should avoid the agent")
        ),
        characterization_agent_enabled=True,
    )

    assert calls["count"] == 1
    assert first["mechanism_curves"] == second["mechanism_curves"]
    assert first["symptom_curves"] == second["symptom_curves"]

    cache = json.loads(cache_path.read_text(encoding="utf-8"))
    assert cache["cached_agentic"]["source"] == "agent"
