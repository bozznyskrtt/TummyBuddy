"""Minimal downstream intestinal fermentation compartment."""

from __future__ import annotations

from gastric_engine.core.state import GutState
from gastric_engine.utils import calibration
from gastric_engine.utils.kinetics import clamp, first_order_release, sigmoid


def empty_to_intestine(state: GutState, fraction: float) -> dict[str, float]:
    fraction = clamp(fraction, 0.0, 1.0)
    flow: dict[str, float] = {}
    if fraction <= 0.0:
        return flow
    for compound, amount in list(state.stomach_species.items()):
        moved = amount * fraction
        if moved <= 0.0:
            continue
        state.stomach_species[compound] = max(0.0, amount - moved)
        state.intestine_species[compound] = state.intestine_species.get(compound, 0.0) + moved
        flow[compound] = moved
    return flow


def ferment_in_intestine(state: GutState, kb, dt_min: float) -> None:
    osmotic_load = 0.0
    for compound, amount in list(state.intestine_species.items()):
        row = kb.compounds.get(compound, {})
        properties = row.get("properties", {})
        fermentability = _property_value(properties, "fermentability")
        if fermentability <= 0.0 or amount <= 0:
            continue
        fermented = first_order_release(amount, calibration.FERMENTATION_RATE_PER_MIN, dt_min)
        state.intestine_species[compound] = max(0.0, amount - fermented)
        state.intestine_gas_ml += (
            fermented * fermentability * calibration.FERMENTATION_GAS_ML_PER_G
        )

    for compound, amount in state.intestine_species.items():
        row = kb.compounds.get(compound, {})
        properties = row.get("properties", {})
        if _property_value(properties, "fermentability") <= 0.0:
            continue
        osmotic_load += amount * _intestinal_osmotic_coeff(properties)

    state.intestine_osmolality = clamp(
        0.1 + osmotic_load + state.intestine_gas_ml * 0.0012,
        0.1,
        2.0,
    )
    state.cramping = sigmoid((state.intestine_osmolality - 0.55) * 5.0)


def _property_value(properties: dict, dimension: str) -> float:
    return max(0.0, float(properties.get(dimension, 0.0) or 0.0))


def _intestinal_osmotic_coeff(properties: dict) -> float:
    potency = properties.get("potency", {})
    if isinstance(potency, dict) and "intestinal_osmotic_coeff" in potency:
        return max(0.0, float(potency["intestinal_osmotic_coeff"]))
    return _property_value(properties, "fermentability") * 0.05
