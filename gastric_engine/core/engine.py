"""The one general simulation loop."""

from __future__ import annotations

from copy import deepcopy

from gastric_engine.core.biochemistry import (
    apply_interactions,
    build_biochemistry_model,
    collect_active_interactions,
    collect_active_reactions,
)
from gastric_engine.core.counterfactual import counterfactual_attribution
from gastric_engine.core.intestine import empty_to_intestine, ferment_in_intestine
from gastric_engine.core.output_builder import build_output
from gastric_engine.core.physics import (
    advance_emptying,
    apply_physical_effect,
    reset_transient_effects,
    update_mechanics,
    vent_gas,
)
from gastric_engine.core.symptoms import derive_symptoms
from gastric_engine.knowledge_base.loader import load_knowledge_base
from gastric_engine.utils.parsing import initialize_state


DEFAULT_CONFIG = {"duration_min": 360, "output_dt_min": 10}


def simulate_core(
    chemicals: dict[str, float],
    meal_physical: dict[str, float],
    physiology: dict,
    config: dict | None = None,
    *,
    kb=None,
) -> dict:
    kb = kb or load_knowledge_base()
    config = {**DEFAULT_CONFIG, **(config or {})}
    duration = float(config["duration_min"])
    output_dt = float(config["output_dt_min"])
    output_times = _output_times(duration, output_dt)

    clean_chemicals = {
        key: float(value)
        for key, value in chemicals.items()
        if key in kb.compound_keys and isinstance(value, (int, float)) and float(value) > 0
    }
    interactions = collect_active_interactions(clean_chemicals, physiology, kb)
    runtime_physiology = apply_interactions(physiology, interactions)

    state = initialize_state(clean_chemicals, meal_physical, runtime_physiology)
    _apply_compound_effects(state, runtime_physiology, kb, dt_min=0.0)
    update_mechanics(state, runtime_physiology)

    reactions = collect_active_reactions(state.stomach_species, kb)
    bio_model = build_biochemistry_model(reactions, runtime_physiology)

    history = [state.snapshot()]
    current_time = 0.0
    for target_time in output_times[1:]:
        while current_time < target_time - 1e-9:
            dt = min(1.0, target_time - current_time)
            bio_model.step(state.stomach_species, dt, state.pH)
            _apply_compound_effects(state, runtime_physiology, kb, dt_min=dt)
            fraction = advance_emptying(state, runtime_physiology, dt)
            empty_to_intestine(state, fraction)
            ferment_in_intestine(state, kb, dt)
            vent_gas(state, dt)
            current_time += dt
            state.time_min = round(current_time, 8)
            update_mechanics(state, runtime_physiology)
        history.append(state.snapshot())

    symptoms = derive_symptoms(history, runtime_physiology)
    return build_output(
        history,
        symptoms,
        metadata={
            "active_reactions": [reaction["id"] for reaction in reactions],
            "active_interactions": [row["id"] for row in interactions],
            "biochemistry_backend": bio_model.backend,
        },
    )


def simulate(
    chemicals: dict[str, float],
    meal_physical: dict[str, float],
    physiology: dict,
    config: dict | None = None,
    *,
    kb=None,
) -> dict:
    kb = kb or load_knowledge_base()
    baseline = simulate_core(chemicals, meal_physical, physiology, config, kb=kb)
    root_causes = counterfactual_attribution(
        chemicals,
        meal_physical,
        physiology,
        kb,
        {**DEFAULT_CONFIG, **(config or {})},
        baseline,
        simulate_core,
    )
    result = deepcopy(baseline)
    result["root_causes"] = root_causes
    return result


def _apply_compound_effects(state, physiology: dict, kb, *, dt_min: float) -> None:
    reset_transient_effects(state, physiology)
    for compound, amount in list(state.stomach_species.items()):
        row = kb.compounds.get(compound, {})
        for effect in row.get("physical_effects", []):
            apply_physical_effect(
                state,
                effect,
                amount,
                physiology,
                compound=compound,
                dt_min=dt_min,
            )


def _output_times(duration: float, output_dt: float) -> list[float]:
    if output_dt <= 0:
        output_dt = 10.0
    times = []
    current = 0.0
    while current < duration - 1e-9:
        times.append(round(current, 8))
        current += output_dt
    times.append(round(duration, 8))
    return times
