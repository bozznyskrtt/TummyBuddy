"""Input parsing helpers."""

from __future__ import annotations

from gastric_engine.core.state import GutState


def initialize_state(
    chemicals: dict[str, float],
    meal_physical: dict[str, float],
    physiology: dict,
) -> GutState:
    solid = float(meal_physical.get("solid_volume_ml", 0.0) or 0.0)
    liquid = float(meal_physical.get("liquid_volume_ml", 0.0) or 0.0)
    species = {
        key: float(value)
        for key, value in chemicals.items()
        if isinstance(value, (int, float)) and float(value) > 0.0
    }
    state = GutState(
        solid_volume_ml=solid,
        liquid_volume_ml=liquid,
        stomach_species=species,
        enzymes=dict(physiology.get("enzyme_levels", {})),
    )
    state.volume_ml = state.solid_volume_ml + state.liquid_volume_ml + state.gas_volume_ml
    return state
