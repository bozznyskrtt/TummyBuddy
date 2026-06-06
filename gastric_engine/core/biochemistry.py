"""Dynamic biochemical reaction harness.

The public model is built from active reaction rows. The local implementation
uses Michaelis-Menten kinetics directly so tests run without Tellurium, while
keeping the same data-driven boundary a Tellurium backend would use.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from gastric_engine.utils import calibration
from gastric_engine.utils.kinetics import apply_path, consume_michaelis


def collect_active_reactions(species: dict[str, float], kb) -> list[dict[str, Any]]:
    active: list[dict[str, Any]] = []
    seen: set[str] = set()
    for compound, amount in species.items():
        if amount <= 0:
            continue
        row = kb.compounds.get(compound, {})
        for reaction_id in row.get("reactions", []):
            if reaction_id in kb.reactions and reaction_id not in seen:
                reaction = deepcopy(kb.reactions[reaction_id])
                reaction["id"] = reaction_id
                active.append(reaction)
                seen.add(reaction_id)
    if species.get("acetaldehyde", 0.0) > 0 and "ethanol_oxidation" not in seen:
        reaction = deepcopy(kb.reactions["ethanol_oxidation"])
        reaction["id"] = "ethanol_oxidation"
        active.append(reaction)
    return active


def collect_active_interactions(
    chemicals: dict[str, float],
    physiology: dict,
    kb,
) -> list[dict[str, Any]]:
    active = []
    flags = physiology.get("clinical_flags", {})
    for row in kb.interactions:
        trigger = row.get("trigger", {})
        all_present = trigger.get("all_present")
        if all_present and all(float(chemicals.get(key, 0.0) or 0.0) > 0 for key in all_present):
            active.append(row)
            continue
        profile_flag = trigger.get("profile_flag")
        if profile_flag and flags.get(profile_flag):
            active.append(row)
    return active


def apply_interactions(physiology: dict, interactions: list[dict[str, Any]]) -> dict:
    adjusted = deepcopy(physiology)
    for interaction in interactions:
        effect = interaction.get("effect", {})
        if "modify_enzyme" in effect:
            key = effect["modify_enzyme"]
            multiplier = float(effect.get("multiply_by", 1.0))
            adjusted.setdefault("enzyme_levels", {})[key] = (
                float(adjusted.get("enzyme_levels", {}).get(key, 1.0)) * multiplier
            )
        elif "reduce" in effect:
            path = effect["reduce"]
            amount = float(effect.get("by", 0.0))
            if "." not in path:
                if path == "buffering_capacity":
                    adjusted.setdefault("runtime_modifiers", {})[
                        "buffering_capacity_delta"
                    ] = -amount
                else:
                    path = f"physiology.{path}"
            if "." in path:
                apply_path(adjusted, path, lambda current: max(0.0, current - amount))
    return adjusted


class BiochemistryModel:
    def __init__(self, reactions: list[dict[str, Any]], enzyme_levels: dict[str, float]):
        self.reactions = reactions
        self.reaction_ids = {reaction["id"] for reaction in reactions}
        self.enzyme_levels = enzyme_levels
        self.backend = "tellurium-compatible-mm"

    def step(self, species: dict[str, float], dt_min: float, pH: float) -> dict[str, float]:
        if "lactose_hydrolysis" in self.reaction_ids:
            lactase_activity = max(0.0, float(self.enzyme_levels.get("lactase_Vmax", 1.0))) ** 1.5
            converted = consume_michaelis(
                species.get("lactose", 0.0),
                calibration.LACTASE_G_PER_MIN * lactase_activity,
                0.05,
                dt_min,
            )
            _move_species(species, "lactose", {"glucose": 0.5, "galactose": 0.5}, converted)

        if "starch_digestion" in self.reaction_ids:
            pH_factor = 1.0 if pH >= 4.0 else max(0.05, (pH - 1.5) / 2.5)
            converted = consume_michaelis(
                species.get("starch", 0.0),
                calibration.AMYLASE_G_PER_MIN
                * float(self.enzyme_levels.get("amylase_Vmax", 1.0))
                * pH_factor,
                0.08,
                dt_min,
            )
            _move_species(species, "starch", {"maltose": 1.0}, converted)

        if "protein_digestion" in self.reaction_ids:
            pH_factor = max(0.0, 1.0 - abs(pH - 2.0) / 3.0)
            converted = consume_michaelis(
                species.get("protein", 0.0),
                calibration.PEPSIN_G_PER_MIN
                * float(self.enzyme_levels.get("pepsin_Vmax", 1.0))
                * pH_factor,
                0.10,
                dt_min,
            )
            _move_species(species, "protein", {"peptides": 1.0}, converted)

        if "ethanol_oxidation" in self.reaction_ids:
            to_acetaldehyde = consume_michaelis(
                species.get("ethanol", 0.0),
                calibration.ADH_G_PER_MIN * float(self.enzyme_levels.get("ADH_Vmax", 1.0)),
                0.02,
                dt_min,
            )
            _move_species(species, "ethanol", {"acetaldehyde": 1.0}, to_acetaldehyde)

            to_acetate = consume_michaelis(
                species.get("acetaldehyde", 0.0),
                calibration.ALDH_G_PER_MIN
                * float(self.enzyme_levels.get("ALDH_Vmax", 1.0)),
                0.01,
                dt_min,
            )
            _move_species(species, "acetaldehyde", {"acetate": 1.0}, to_acetate)

        return species


def build_biochemistry_model(reactions: list[dict[str, Any]], physiology: dict) -> BiochemistryModel:
    return BiochemistryModel(reactions, dict(physiology.get("enzyme_levels", {})))


def _move_species(
    species: dict[str, float],
    substrate: str,
    products: dict[str, float],
    amount: float,
) -> None:
    if amount <= 0:
        return
    species[substrate] = max(0.0, species.get(substrate, 0.0) - amount)
    for product, coefficient in products.items():
        species[product] = species.get(product, 0.0) + amount * coefficient
