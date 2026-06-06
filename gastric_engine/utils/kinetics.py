"""Small kinetic helpers shared by the simulation modules."""

from __future__ import annotations

import math
import warnings
from typing import Callable

try:  # pragma: no cover - exercised indirectly when scipy is available
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        from scipy.integrate import solve_ivp
except Exception:  # pragma: no cover - fallback keeps the engine importable
    solve_ivp = None


def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def sigmoid(value: float) -> float:
    if value >= 0:
        z = math.exp(-value)
        return 1.0 / (1.0 + z)
    z = math.exp(value)
    return z / (1.0 + z)


def michaelis_menten_rate(amount: float, vmax: float, km: float) -> float:
    amount = max(0.0, amount)
    if amount <= 0.0 or vmax <= 0.0:
        return 0.0
    return vmax * amount / (km + amount)


def consume_michaelis(amount: float, vmax: float, km: float, dt_min: float) -> float:
    return min(max(0.0, amount), michaelis_menten_rate(amount, vmax, km) * dt_min)


def exponential_remaining(amount: float, half_life_min: float, dt_min: float) -> float:
    """Return remaining amount after first-order decay over dt.

    Uses scipy.solve_ivp when available, with an analytical fallback for local
    environments that do not have the requested stack installed.
    """

    amount = max(0.0, amount)
    if amount <= 0.0 or dt_min <= 0.0:
        return amount
    if half_life_min <= 0.0:
        return 0.0

    k = math.log(2.0) / half_life_min
    if solve_ivp is None:
        return amount * math.exp(-k * dt_min)

    def ode(_t: float, y: list[float]) -> list[float]:
        return [-k * y[0]]

    solution = solve_ivp(ode, (0.0, dt_min), [amount], t_eval=[dt_min])
    if not solution.success:
        return amount * math.exp(-k * dt_min)
    return max(0.0, float(solution.y[0][-1]))


def first_order_release(amount: float, rate_per_min: float, dt_min: float) -> float:
    amount = max(0.0, amount)
    if amount <= 0.0 or rate_per_min <= 0.0 or dt_min <= 0.0:
        return 0.0
    return amount * (1.0 - math.exp(-rate_per_min * dt_min))


def peak_time(time: list[float], values: list[float]) -> float:
    if not time or not values:
        return 0.0
    peak = max(values)
    return time[values.index(peak)]


def curve_peak(values: list[float]) -> float:
    return max(values) if values else 0.0


def curve_auc(time: list[float], values: list[float]) -> float:
    """Trapezoidal area under a symptom curve = total symptom burden over time.

    Used for counterfactual attribution: unlike the peak, the AUC still moves
    when a driver is removed even if the peak is saturated near 1.0.
    """
    if not time or not values or len(time) != len(values):
        return 0.0
    area = 0.0
    for i in range(1, len(time)):
        dt = time[i] - time[i - 1]
        area += 0.5 * (values[i] + values[i - 1]) * dt
    return area


def apply_path(target: dict, dotted_path: str, value_fn: Callable[[float], float]) -> None:
    parts = dotted_path.split(".")
    current = target
    for part in parts[:-1]:
        current = current.setdefault(part, {})
    leaf = parts[-1]
    current[leaf] = value_fn(float(current.get(leaf, 0.0)))
