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


def apply_properties(
    state: GutState,
    properties: dict,
    amount: float,
    *,
    compound: str,
    dt_min: float,
) -> None:
    amount = max(0.0, float(amount or 0.0))

    carbonation = _property_value(properties, "carbonation")
    if carbonation > 0.0:
        releasable = state.stomach_species.get(compound, 0.0) * carbonation
        release = first_order_release(
            releasable,
            calibration.CO2_RELEASE_RATE_PER_MIN,
            dt_min,
        )
        state.stomach_species[compound] = max(
            0.0, state.stomach_species.get(compound, 0.0) - release
        )
        state.gas_volume_ml += release * calibration.CO2_GAS_ML_PER_G

    fat_emptying = _property_value(properties, "fat_emptying")
    if fat_emptying > 0.0:
        state.fat_brake += fat_emptying * amount / (amount + 20.0)

    osmotic_coeff = _property_value(properties, "osmotic_coeff")
    if osmotic_coeff > 0.0:
        state.osmolality += osmotic_coeff * amount / 40.0

    buffering = _property_value(properties, "buffering")
    if buffering > 0.0:
        state.buffering_capacity += buffering * amount / (amount + 40.0)

    acid_secretagogue = _property_value(properties, "acid_secretagogue")
    if acid_secretagogue > 0.0:
        state.acid_secretion_rate += acid_secretagogue * _potent_amount(
            properties, "acid_secretagogue", amount
        )

    acid_load = _property_value(properties, "acid_load")
    if acid_load > 0.0:
        state.acid_load_effect -= acid_load * amount

    les_relaxant = _property_value(properties, "les_relaxant")
    if les_relaxant > 0.0:
        state.les_relaxation += les_relaxant * _potent_amount(
            properties, "les_relaxant", amount
        )

    irritant_potential = _property_value(properties, "irritant_potential")
    if irritant_potential > 0.0:
        state.irritation += irritant_potential * _potent_amount(
            properties, "irritant_potential", amount
        )


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


def _property_value(properties: dict, dimension: str) -> float:
    return max(0.0, float(properties.get(dimension, 0.0) or 0.0))


def _potent_amount(properties: dict, dimension: str, amount: float) -> float:
    potency = properties.get("potency", {})
    amount_scale = 1.0
    if isinstance(potency, dict):
        amount_scale = float(potency.get(dimension, 1.0) or 1.0)
    return amount / max(amount_scale, 1e-9)
