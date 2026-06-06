# Build Plan — Gastric Engine (Phased Implementation for Agents)

> Read `ARCHITECTURE.md` first. This file is the **order** in which to build, with an
> acceptance test at every phase. Build phase N fully (its test passing) before N+1.
> Tech stack: **Python 3.11+, FastAPI, Pydantic, scipy, Tellurium, pytest.**

---

## Golden rules (apply to every phase)

- **No food-specific code, ever.** Foods live in `knowledge_base/*.json` as data.
- **Test-driven:** write the phase's acceptance test first, watch it fail, then build.
- **One shared state object** (`GutState`) — modules read/write it, never keep private state.
- If a phase needs a new compound, add it to `compounds.json` (and `INPUT_CONTRACT.md`).

---

## Phase 0 — Scaffold & contract

**Build:** project skeleton per `ARCHITECTURE.md` §8, FastAPI app, `POST /simulate`
returning a stub, Pydantic schemas matching `INPUT_CONTRACT.md`.

**Acceptance:** posting the sample request returns a schema-valid (stub) response; `pytest`
runs; `GET /health` returns 200.

---

## Phase 1 — State vector & solver harness

**Build:** `core/state.py` (`GutState`, §3/§5), `utils/parsing.py` (chemicals → initial
state), and the `scipy.solve_ivp` integration harness in `core/engine.py` that advances a
trivial state (e.g. linear gastric emptying) from 0→duration and records snapshots.

**Acceptance:** liquid-only meal empties with t½ ≈ 20 min (literature, §7.4); curves are
smooth and sampled at `output_dt_min`.

---

## Phase 2 — Knowledge base + dynamic loader

**Build:** `knowledge_base/compounds.json`, `reactions.json`, `interactions.json`,
`physiology_defaults.json` (seed versions provided). Loader functions
`collect_active_reactions`, `collect_active_interactions`. `core/physics.py`
`apply_physical_effect` dispatching on the data-declared effect `law`.

**Acceptance:** with **zero** changes to `engine.py`, adding a compound row to the JSON makes
the engine respond to it. Unit test proves a new compound's `physical_effects` are applied.

---

## Phase 3 — Physics (mechanics) module

**Build:** `core/physics.py` mechanics — `update_mechanics`: gas outgassing (Henry's law),
volume, `pressure_from_volume`, `fundus_pressure` (uses `les_competence`), `pH` from acid vs
buffering, `emptying_rate` = motility minus fat brake.

**Acceptance (the headline demo):** *burger + fries + Coke* produces higher peak
`gastric_pressure` and `fundus_pressure` than *salad + water*. CO₂ raises `gas_volume_ml`
then it decays.

---

## Phase 4 — Biochemistry (Tellurium)

**Build:** `core/biochemistry.py` — build a Tellurium/Antimony model at runtime from the
active reactions; personal enzyme levels become `Vmax`; active interactions modify `Vmax`
before the run. Wire `bio_model.step` into the loop.

**Acceptance:**
- Normal `lactase_Vmax=1.0`: lactose → ~0 within minutes.
- Intolerant `lactase_Vmax=0.15`: `lactose_remaining_g` stays high → flows to intestine.
- **Durian+beer:** with the `interactions.json` row, `ALDH_Vmax` drops to 0.35 and
  `acetaldehyde` accumulates vs the no-durian control. **No engine code changed.**

---

## Phase 5 — Intestinal compartment

**Build:** `core/intestine.py` — `empty_to_intestine` moves contents downstream;
`ferment_in_intestine` converts undigested lactose/FODMAPs → intestinal gas + osmolality +
`cramping`.

**Acceptance:** lactose-intolerant milkshake produces **rising `intestine_gas_ml` and
`intestine_osmolality` hours after** the meal, while a normal profile does not.

---

## Phase 6 — Symptom emergence

**Build:** `core/symptoms.py` (§6) — sigmoid threshold crossings producing per-symptom
probability **curves** (reflux, bloating, diarrhea, upper_pain).

**Acceptance:** reflux-prone profile (`les_competence` low) crosses the reflux threshold on
the Coke meal and peaks at 20–30 min; diarrhea curve for the intolerant profile rises only
in the later (intestinal) window.

---

## Phase 7 — Counterfactual root-cause engine ⭐

**Build:** `core/counterfactual.py` (§7.2). Factor the loop into `simulate_core()`
(curves+symptoms) and a `simulate()` wrapper that runs `simulate_core` once per removed
chemical and attributes each symptom's peak change. **Guard against recursion** —
counterfactual calls `simulate_core`, never `simulate`.

**Acceptance:** on the Coke meal, removing `CO2_dissolved` drops reflux peak the most;
`root_causes.reflux.drivers` is ranked and sums to ~100%; an `advice` string is produced.

---

## Phase 8 — Personal physiology & Bayesian learning

**Build:** `physiology/profile_builder.py` (clinical flags → continuous properties) and
`physiology/learning.py` (each param a `(mean,var)`; Bayesian update from reported symptoms).

**Acceptance:** simulate a user who logs diarrhea after 3 dairy meals → posterior
`lactase_Vmax` mean falls and variance shrinks; next prediction shows higher lactose risk.

---

## Phase 9 — Safety, uncertainty, polish

**Build:** `safety` red-flag pass over `symptoms_reported` (blood in vomit, black stool, etc.
→ `safety_flags`, never softened into probabilities); `unknown_compounds` → lower
`confidence`; `output_builder.py` assembles the final response.

**Acceptance:** red-flag input yields an urgent `safety_flags` entry; unmapped compounds
lower `confidence`; full response matches `INPUT_CONTRACT.md` §4.

---

## Definition of done (whole engine)

The **durian+beer test** (`ARCHITECTURE.md` §10) passes:
1. Lactose intolerance — emerges from `lactase_Vmax` alone, no code.
2. Gas → reflux — emerges from CO₂ → fundus pressure → threshold, no code.
3. Durian+beer — works via one `interactions.json` row, no engine edit.

Plus: every symptom is a time **curve**, every prediction has a counterfactual **why**, and
all rate constants cite a source in `utils/calibration.py`.
