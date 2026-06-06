"""Shared stomach and intestine state vector."""

from __future__ import annotations

from dataclasses import dataclass, field

from gastric_engine.utils.calibration import BASE_GASTRIC_GAS_ML


@dataclass
class GutState:
    time_min: float = 0.0

    volume_ml: float = 0.0
    solid_volume_ml: float = 0.0
    liquid_volume_ml: float = 0.0
    gas_volume_ml: float = BASE_GASTRIC_GAS_ML
    pressure: float = 0.0
    fundus_pressure: float = 0.0
    wall_tension: float = 0.0
    emptying_rate: float = 0.0

    pH: float = 3.0
    acid_secretion_rate: float = 0.0
    buffering_capacity: float = 0.0
    osmolality: float = 0.1

    stomach_species: dict[str, float] = field(default_factory=dict)
    intestine_species: dict[str, float] = field(default_factory=dict)
    intestine_gas_ml: float = 0.0
    intestine_osmolality: float = 0.1
    cramping: float = 0.0

    enzymes: dict[str, float] = field(default_factory=dict)

    irritation: float = 0.0
    fat_brake: float = 0.0
    les_relaxation: float = 0.0
    acid_load_effect: float = 0.0
    last_emptying_fraction: float = 0.0

    def snapshot(self) -> dict[str, float]:
        return {
            "time_min": self.time_min,
            "volume_ml": self.volume_ml,
            "solid_volume_ml": self.solid_volume_ml,
            "liquid_volume_ml": self.liquid_volume_ml,
            "gas_volume_ml": self.gas_volume_ml,
            "gastric_pressure": self.pressure,
            "fundus_pressure": self.fundus_pressure,
            "wall_tension": self.wall_tension,
            "emptying_rate": self.emptying_rate,
            "pH": self.pH,
            "osmolality": self.osmolality,
            "intestine_gas_ml": self.intestine_gas_ml,
            "intestine_osmolality": self.intestine_osmolality,
            "cramping": self.cramping,
            "irritation": self.irritation,
            "lactose_remaining_g": self.stomach_species.get("lactose", 0.0)
            + self.intestine_species.get("lactose", 0.0),
            "acetaldehyde_g": self.stomach_species.get("acetaldehyde", 0.0),
        }
