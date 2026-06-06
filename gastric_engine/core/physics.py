"""Mechanical and chemical physics for the shared gut state."""

from __future__ import annotations

from gastric_engine.core.state import GutState
from gastric_engine.utils import calibration
from gastric_engine.utils.kinetics import clamp, exponential_remaining, first_order_release


def reset_transient_effects(state: GutState, physiology: dict) -> None:
    phys = physiology.get("physiology", {})
    state.acid_secretion_rate = float(phys.get("baseline_acid_secretion", 0.5))
    state.buffering_capacity = float(
        physiology.get("runtime_modifiers", {}).get("buffering_capacity_delta", 0.0)
    )
    state.osmolality = 0.1
    state.irritation = max(0.0, (1.0 - float(phys.get("mucosal_resilience", 0.8))) * 0.18)
    state.fat_brake = 0.0
    state.les_relaxation = 0.0
    state.acid_load_effect = 0.0


def apply_physical_effect(
    state: GutState,
    effect: dict,
    amount: float,
    physiology: dict,
    *,
    compound: str,
    dt_min: float,
) -> None:
    law = effect.get("law")
    coefficient = float(effect.get("coefficient", effect.get("strength", 1.0)))
    amount = max(0.0, float(amount or 0.0))

    if law == "henry_release":
        release = first_order_release(
            state.stomach_species.get(compound, 0.0),
            calibration.CO2_RELEASE_RATE_PER_MIN,
            dt_min,
        )
        state.stomach_species[compound] = max(
            0.0, state.stomach_species.get(compound, 0.0) - release
        )
        state.gas_volume_ml += release * calibration.CO2_GAS_ML_PER_G
    elif law == "cck_feedback":
        state.fat_brake += coefficient * amount / (amount + 20.0)
    elif law == "osmotic":
        state.osmolality += coefficient * amount / 40.0
    elif law == "buffering":
        state.buffering_capacity += coefficient * amount / (amount + 40.0)
    elif law == "acid_stimulation":
        state.acid_secretion_rate += coefficient * _normalized_amount(compound, amount)
    elif law == "acidify":
        state.acid_load_effect += coefficient * amount
    elif law == "les_relaxation":
        state.les_relaxation += coefficient * _normalized_amount(compound, amount)
    elif law == "irritation":
        state.irritation += coefficient * _normalized_amount(compound, amount)
    elif law == "bulk":
        # Bulk volume is supplied by meal_physical. Keep fiber data-driven without
        # re-adding its volume every simulation step.
        return


def update_mechanics(state: GutState, physiology: dict) -> None:
    phys = physiology.get("physiology", {})
    capacity = float(phys.get("gastric_capacity_ml", 1000.0))
    les_competence = float(phys.get("les_competence", 0.8))
    mucosal_resilience = float(phys.get("mucosal_resilience", 0.8))

    state.volume_ml = state.solid_volume_ml + state.liquid_volume_ml + state.gas_volume_ml
    state.pressure = pressure_from_volume(
        state.solid_volume_ml + state.liquid_volume_ml,
        state.gas_volume_ml,
        capacity,
    )
    state.fundus_pressure = clamp(
        state.pressure
        + (state.gas_volume_ml / capacity) * 0.25
        + state.les_relaxation * 0.25
        + (1.0 - les_competence) * 0.12,
        0.0,
        1.5,
    )
    state.wall_tension = clamp(state.volume_ml / max(capacity, 1.0), 0.0, 2.0)

    acid = state.acid_secretion_rate
    state.pH = clamp(3.4 - 1.45 * acid + state.buffering_capacity + state.acid_load_effect, 1.2, 7.0)
    acid_irritation = max(0.0, (3.2 - state.pH) * 0.14)
    state.irritation += acid_irritation * (1.2 - mucosal_resilience)
    state.irritation += state.stomach_species.get("acetaldehyde", 0.0) * 0.035
    state.irritation = clamp(state.irritation, 0.0, 2.0)


def pressure_from_volume(non_gas_volume_ml: float, gas_volume_ml: float, capacity_ml: float) -> float:
    fill_component = max(0.0, (non_gas_volume_ml / max(capacity_ml, 1.0) - 0.75) / 0.70)
    gas_component = min(0.9, gas_volume_ml / max(capacity_ml, 1.0) * 1.80)
    return clamp(fill_component + gas_component, 0.0, 1.5)


def advance_emptying(state: GutState, physiology: dict, dt_min: float) -> float:
    phys = physiology.get("physiology", {})
    motility = max(0.2, float(phys.get("gastric_motility", calibration.BASELINE_MOTILITY)))
    motility_factor = calibration.BASELINE_MOTILITY / motility
    fat_factor = 1.0 + 2.8 * state.fat_brake

    liquid_half = calibration.LIQUID_EMPTYING_HALF_LIFE_MIN * fat_factor * motility_factor
    solid_half = calibration.SOLID_EMPTYING_HALF_LIFE_MIN * fat_factor * motility_factor

    before = state.solid_volume_ml + state.liquid_volume_ml
    new_liquid = exponential_remaining(state.liquid_volume_ml, liquid_half, dt_min)
    new_solid = exponential_remaining(state.solid_volume_ml, solid_half, dt_min)
    emptied = max(0.0, before - new_liquid - new_solid)

    state.liquid_volume_ml = new_liquid
    state.solid_volume_ml = new_solid
    state.emptying_rate = emptied / max(dt_min, 1e-6)
    state.last_emptying_fraction = emptied / before if before > 0 else 0.0
    return state.last_emptying_fraction


def vent_gas(state: GutState, dt_min: float) -> None:
    baseline = calibration.BASE_GASTRIC_GAS_ML
    excess = max(0.0, state.gas_volume_ml - baseline)
    state.gas_volume_ml = baseline + exponential_remaining(
        excess, calibration.GAS_VENT_HALF_LIFE_MIN, dt_min
    )


def _normalized_amount(compound: str, amount: float) -> float:
    if compound == "caffeine":
        return amount / 100.0
    if compound == "ethanol":
        return amount / 25.0
    return amount
