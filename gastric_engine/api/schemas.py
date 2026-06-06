"""Optional Pydantic schemas for FastAPI deployments."""

from __future__ import annotations

try:  # pragma: no cover - optional dependency in this local environment
    from pydantic import BaseModel, Field
except Exception:  # pragma: no cover
    BaseModel = object

    def Field(default=None, **_kwargs):
        return default


class SimulationRequest(BaseModel):
    if BaseModel is object:  # pragma: no cover
        pass
    else:
        chemicals: dict[str, float]
        meal_physical: dict[str, float]
        clinical_profile: dict[str, bool]
        learned_physiology: dict | None = None
        symptoms_reported: dict | None = None
        simulation_config: dict | None = Field(default=None)
