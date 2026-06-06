"""Calibration constants used by the gastric engine.

The values here are intentionally centralized so literature-backed constants can
be swapped without changing simulation code.
"""

LIQUID_EMPTYING_HALF_LIFE_MIN = 20.0
SOLID_EMPTYING_HALF_LIFE_MIN = 120.0
BASELINE_MOTILITY = 0.8

CO2_RELEASE_RATE_PER_MIN = 0.025
CO2_GAS_ML_PER_G = 420.0
GAS_VENT_HALF_LIFE_MIN = 28.0
BASE_GASTRIC_GAS_ML = 20.0

LACTASE_G_PER_MIN = 2.20
AMYLASE_G_PER_MIN = 0.45
PEPSIN_G_PER_MIN = 0.40
ADH_G_PER_MIN = 0.25
ALDH_G_PER_MIN = 0.20

FERMENTATION_RATE_PER_MIN = 0.008
FERMENTATION_GAS_ML_PER_G = 120.0

SYMPTOM_GAIN = 10.0

CALIBRATION_SOURCES = {
    "liquid_emptying": "Liquid gastric emptying half-time calibrated near 20 min.",
    "solid_emptying": "Solid gastric emptying half-time calibrated near 2 h.",
    "fat_feedback": "Fat slows emptying through CCK-mediated feedback.",
}
