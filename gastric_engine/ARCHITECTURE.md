# TummyBuddy Gastric Engine — Architecture (Agent Build Guide)

> **Read this first.** This document is the source of truth for building the engine.
> If you are an implementing agent, read this top-to-bottom before writing any code,
> then follow `BUILD_PLAN.md` for the phased implementation order, and
> `INPUT_CONTRACT.md` for the data interface with the upstream pipeline.

---

## 0. What this engine is (and is NOT)

**It IS:** a two-compartment (stomach + intestine) physiological simulator. You feed it
the **chemicals** in a meal plus a **user's clinical profile**, and it simulates digestion
over 2–6 hours, then reports **which symptoms are likely, when they peak, and exactly why**.

**It is NOT:** a food→disease lookup table. There are **no food-specific modules**.
Coke, durian+beer, and a milkshake all run through the *same* code path. They differ only
in which **data rows** in the knowledge base activate.

### The single governing principle

> **Physics is the engine. Knowledge is data. Foods are never hard-coded.**

If you ever find yourself writing `if food == "coke"` or a `carbonation_module.py`, STOP.
That logic belongs in `knowledge_base/*.json` as data, consumed by the general loop.

### What the engine delivers (project promise)

| Promise | Mechanism in this engine |
|---|---|
| "chance of a stomachache" | Symptom probability curves from threshold crossings (§6) |
| **"why does it happen"** | Counterfactual attribution — re-run minus each chemical (§7.2) |
| symptoms that appear *later* | Intestinal compartment: fermentation → gas/diarrhea (§5) |
| "includes clinical data" | Personal physiology pillar + Bayesian learning (§4, §7.3) |
| works on *any* food | General loop + compound vocabulary, no per-food code (§3) |
| credible in a demo | Literature-calibrated rate constants (§7.4) |

---

## 1. System overview

```
 UPSTREAM (teammates)                    THIS ENGINE (your part)
 ┌───────────────┐  ┌──────────────┐    ┌────────────────────────────────────┐
 │ Image →       │  │ Ingredient → │    │  POST /simulate                    │
 │ Ingredients   │─▶│ Chemicals    │───▶│  chemicals + clinical profile      │
 └───────────────┘  └──────────────┘    │            ↓                       │
                       (see              │  General Simulation Loop           │
                    INPUT_CONTRACT.md)   │   ├ Biochemistry (Tellurium)       │
                                         │   ├ Physics (data-declared ODEs)   │
                                         │   ├ Stomach → Intestine flow       │
                                         │   └ Symptom emergence              │
                                         │            ↓                       │
                                         │  Counterfactual root-cause         │
                                         │            ↓                       │
                                         │  curves + symptoms + "why" JSON    │
                                         └────────────────────────────────────┘
```

---

## 2. The 3 Pillars

The engine is built from three conceptual pillars. Keep them strictly separated in code.

```
┌─────────────────────────────────────────────────────────────┐
│  PILLAR 1: STOMACH/GUT STATE      (the physical system)     │
│  One shared state vector evolving via ODEs                   │
│                                                              │
│  PILLAR 2: KNOWLEDGE BASE         (pure data, not code)     │
│  compounds.json + reactions.json + interactions.json         │
│                                                              │
│  PILLAR 3: PERSONAL PHYSIOLOGY    (the individual)          │
│  Clinical data → stomach properties (rates + thresholds)     │
└─────────────────────────────────────────────────────────────┘
```

---

## 3. Pillar 1 — The State Vector

There is **one shared state object** describing the whole gut at time `t`. Modules never
keep private state; they read and write this shared vector. Adding a new compound is a new
**key**, never a new module.

```python
# core/state.py
@dataclass
class GutState:
    time_min: float

    # --- Stomach: mechanics ---
    volume_ml: float            # total stomach contents
    solid_volume_ml: float
    liquid_volume_ml: float
    gas_volume_ml: float        # free gas in headspace
    pressure: float             # intragastric pressure, normalized 0–1
    fundus_pressure: float      # pressure at the LES — DRIVES REFLUX
    wall_tension: float
    emptying_rate: float        # mL/min leaving to the intestine

    # --- Stomach: chemistry ---
    pH: float                   # 1.5 (very acidic) – 7
    acid_secretion_rate: float
    buffering_capacity: float   # food's ability to neutralize acid
    osmolality: float           # solute concentration → drives water shifts

    # --- Chemical species in the STOMACH (grams unless noted) ---
    stomach_species: dict       # {"lactose": g, "glucose": g, "fat": g,
                                #  "ethanol": g, "acetaldehyde": g,
                                #  "CO2_dissolved": g, "caffeine": mg,
                                #  "protein": g, "peptides": g, "FODMAP": g, ...}

    # --- INTESTINE compartment (see §5) ---
    intestine_species: dict     # undigested matter that flowed downstream
    intestine_gas_ml: float
    intestine_osmolality: float
    cramping: float

    # --- Enzyme activities (set by Pillar 3) ---
    enzymes: dict               # {"lactase": v, "pepsin": v, "ADH": v, "ALDH": v}
```

> **Rule:** every physical quantity a symptom depends on must live here, so the
> counterfactual tracer (§7.2) and symptom layer (§6) can read it uniformly.

---

## 4. Pillar 3 — Personal Physiology

Clinical data defines stomach **properties** (continuous), not yes/no modifiers. This is
why "same food, different person, different outcome" emerges naturally.

```jsonc
// physiology profile (built from clinical data by physiology/profile_builder.py)
{
  "physiology": {
    "gastric_capacity_ml": 950,
    "baseline_acid_secretion": 0.6,
    "les_competence": 0.5,        // lower = weaker valve = reflux-prone
    "mucosal_resilience": 0.7,    // lower = irritation-prone
    "gastric_motility": 0.8       // contraction strength → emptying speed
  },
  "enzyme_levels": {
    "lactase_Vmax": 0.15,         // LACTOSE INTOLERANT (normal ≈ 1.0)
    "pepsin_Vmax": 1.0,
    "ADH_Vmax": 0.9,
    "ALDH_Vmax": 1.0              // an interaction can drop this to 0.35
  },
  "symptom_thresholds": {
    "reflux_pressure_threshold": 0.68,
    "bloating_volume_threshold": 0.75,
    "pain_irritation_threshold": 0.6,
    "diarrhea_osmotic_threshold": 0.7
  }
}
```

**Worked example — lactose intolerance is fully emergent:**
18 g lactose meets `lactase_Vmax = 0.15` → barely hydrolyzed → stays osmotically active →
osmolality high → water drawn into lumen → volume/gas rise → empties into intestine still
undigested → ferments → gas + cramping + diarrhea hours later. A normal person
(`lactase_Vmax = 1.0`) clears it in minutes → no symptoms. **One parameter, total difference.**

---

## 5. Pillar 1 (cont.) — Two compartments: Stomach + Intestine

The engine is **two connected compartments**, because many real stomachaches are not gastric.

```
   STOMACH                          INTESTINE / COLON
   ─────────                        ──────────────────
   gas, pressure, acid    ───────▶  undigested lactose & FODMAPs
   reflux, early fullness  empties  ferment → gas → cramping → diarrhea
   (0–60 min symptoms)              (1–6 hour symptoms)
```

- Each timestep, `emptying_rate` moves a fraction of stomach contents into the intestine.
- **Whatever the stomach failed to digest** (undigested lactose, FODMAPs) arrives in the
  intestine and **ferments** → produces gas → raises intestinal osmolality → cramping and
  later-onset diarrhea risk.
- This compartment is what lets the engine answer *"why did I get diarrhea 3 hours later?"*

> Keep the intestine model **minimal**: fermentation of undigested fermentable carbs →
> gas + osmotic water. Do not model full intestinal absorption; it's out of scope.

---

## 6. Symptoms EMERGE — they are not scored by rules

Symptoms are **threshold crossings on the emergent curves**, plus timing. There is no
`if pressure high: reflux = 0.86`.

```python
# core/symptoms.py
def derive_symptoms(history, thresholds):
    reflux = [sigmoid((s.fundus_pressure - thresholds.reflux_pressure_threshold) * GAIN)
              for s in history]

    bloating = [sigmoid((s.volume_ml / capacity - thresholds.bloating_volume_threshold) * GAIN)
                for s in history]

    # Later-onset, from the INTESTINE compartment
    diarrhea = [sigmoid((s.intestine_osmolality - thresholds.diarrhea_osmotic_threshold) * GAIN)
                for s in history]

    pain = [sigmoid((irritation(s) - thresholds.pain_irritation_threshold) * GAIN)
            for s in history]

    return {"reflux": reflux, "bloating": bloating,
            "diarrhea": diarrhea, "upper_pain": pain}
```

Each symptom is a **curve over time**, so the app can show *when* it peaks, not just a score.

---

## 7. The General Simulation Loop (the ONE code path)

```python
# core/engine.py
def simulate(chemicals, physiology, kb, config):
    state = initialize_state(chemicals, physiology)          # meal → compounds

    # Build the Tellurium model DYNAMICALLY from whatever is present
    reactions    = collect_active_reactions(state, kb)       # data-driven
    interactions = collect_active_interactions(state, chemicals, physiology, kb)
    bio_model    = build_tellurium_model(reactions, interactions, physiology)

    history = []
    # Solver: scipy.solve_ivp with adaptive stepping (see §7.5)
    for t in timesteps(config):
        state.stomach_species = bio_model.step(state.stomach_species, dt)  # 1. BIOCHEMISTRY

        for compound, amount in state.stomach_species.items():             # 2. PHYSICS
            for effect in kb.compounds[compound].get("physical_effects", []):
                apply_physical_effect(state, effect, amount, physiology)    #    (data-declared)

        update_mechanics(state, physiology)        # 3. pressure, gas, pH, emptying_rate
        flow = empty_to_intestine(state, dt)       # 4. STOMACH → INTESTINE
        ferment_in_intestine(state, flow, dt)      # 5. downstream gas / osmolality / cramping

        history.append(snapshot(state))

    symptoms    = derive_symptoms(history, physiology["symptom_thresholds"])  # §6
    root_causes = counterfactual_attribution(chemicals, physiology, kb, config, symptoms)  # §7.2
    return build_output(history, symptoms, root_causes)
```

> **There is no `if food == X` in this loop.** It iterates over whatever compounds exist
> and applies whatever effects the registry declares. That is the entire point.

### 7.1 Biochemistry (Tellurium)
`core/biochemistry.py` builds a Tellurium/Antimony model at runtime from the **active**
reactions only. Personal enzyme levels (`lactase_Vmax`, `ALDH_Vmax`, …) become the `Vmax`
parameters. Active interactions (§ knowledge base) modify those parameters before the run.

### 7.2 Counterfactual root-cause engine ⭐
Because the engine is deterministic, attribute causality by **re-running with one chemical
removed** and measuring the change in each symptom's peak:

```python
def counterfactual_attribution(chemicals, physiology, kb, config, baseline_symptoms):
    causes = {}
    base_peaks = peak_of_each(baseline_symptoms)
    for chem in chemicals:
        reduced = {k: v for k, v in chemicals.items() if k != chem}
        alt = simulate_core(reduced, physiology, kb, config)   # NOTE: core, no recursion
        for symptom, base in base_peaks.items():
            drop = base - peak(alt.symptoms[symptom])
            if drop > MATERIAL:
                causes.setdefault(symptom, []).append(
                    {"chemical": chem, "contribution": drop})
    return normalize_and_explain(causes)   # → "reflux: 52% CO2, 28% volume, 20% caffeine"
```

> **Guard against recursion:** the counterfactual must call the *core* simulate (no nested
> attribution), or you get exponential blow-up. Factor the loop into `simulate_core()`
> (returns curves+symptoms) and a thin `simulate()` wrapper that adds attribution once.

### 7.3 Bayesian personal learning
Each personal parameter is a **distribution** `(mean, variance)`, not a point. After a meal,
the user reports symptoms; `physiology/learning.py` does a Bayesian update toward the
evidence. Over ~5 meals the engine converges on the user's true physiology — replacing the
old hand-tuned `+= 0.05` heuristic.

```
Before: lactase_Vmax = 0.5 ± 0.3   (uncertain)
Dairy meal → diarrhea reported     (evidence: low lactase)
After:  lactase_Vmax = 0.2 ± 0.1   (now confident: intolerant)
```

### 7.4 Literature calibration
Rate constants are tuned to published gut data so curves are defensible, not invented:
- Liquid gastric emptying t½ ≈ 20 min; solids t½ ≈ 2 h.
- Fat measurably slows emptying (CCK feedback).
- Keep a `utils/calibration.py` table citing each constant's source.

### 7.5 ODE solver
Use `scipy.integrate.solve_ivp` with an adaptive method (e.g. `LSODA`/`RK45`). Do **not**
hand-roll fixed-step Euler — it's less stable and less accurate. Sample the solution at the
output timepoints the API requests.

---

## 8. Folder structure

```
gastric_engine/
├── ARCHITECTURE.md          ← this file (source of truth)
├── BUILD_PLAN.md            ← phased implementation order
├── INPUT_CONTRACT.md        ← interface with upstream pipeline
├── main.py
├── api/
│   └── routes.py            # POST /simulate
│
├── core/
│   ├── engine.py            # the ONE general loop (§7) + simulate_core/simulate
│   ├── state.py            # GutState vector (§3, §5)
│   ├── physics.py          # mechanical ODEs: pressure, gas, pH, emptying
│   ├── biochemistry.py     # dynamic Tellurium model builder (§7.1)
│   ├── intestine.py        # fermentation compartment (§5)
│   ├── symptoms.py         # threshold-crossing emergence (§6)
│   ├── counterfactual.py   # root-cause attribution (§7.2)
│   └── output_builder.py
│
├── knowledge_base/          ← PURE DATA — the "intelligence" (no Python)
│   ├── compounds.json       # what each substance does physically
│   ├── reactions.json       # biochemistry for Tellurium
│   ├── interactions.json    # molecular facts (durian+beer lives here)
│   └── physiology_defaults.json
│
├── physiology/
│   ├── profile_builder.py   # clinical data → stomach properties (§4)
│   └── learning.py          # Bayesian feedback update (§7.3)
│
└── utils/
    ├── kinetics.py          # michaelis_menten, henry_release, sigmoid
    ├── calibration.py       # literature-sourced constants (§7.4)
    └── parsing.py           # chemicals dict → initial state
```

> **Note what's gone:** the original `modules/` folder of 10 food-specific files is
> **deleted**. It is replaced by `knowledge_base/` (data) + `core/physics.py` +
> `core/biochemistry.py` (two general engines). If you are recreating per-food modules,
> you have misunderstood the architecture.

---

## 9. Anti-patterns (do NOT do these)

| Anti-pattern | Do this instead |
|---|---|
| `if food == "coke": run_carbonation()` | Add CO₂ effects to `compounds.json`; the loop applies them |
| A new `.py` module per food/drink | A new data row in the knowledge base |
| `reflux_score = 0.86 if pressure>0.8` | Let reflux emerge from `fundus_pressure` crossing the personal threshold |
| Hard-coding durian+beer logic in code | One row in `interactions.json` (ALDH ×0.35) |
| Fixed-step Euler integration | `scipy.solve_ivp` adaptive solver |
| Clinical flags as score multipliers | Clinical data → continuous stomach **properties** |
| Counterfactual calling full `simulate()` | Counterfactual calls `simulate_core()` (no nested attribution) |

---

## 10. The durian+beer test (acceptance criterion for "general")

A correct implementation handles all three with **zero food-specific code**:

1. **Lactose intolerance** — emerges from `lactase_Vmax` alone (no code).
2. **Gas → reflux** — emerges from CO₂ outgassing → fundus pressure → threshold (no code).
3. **Durian + beer** — works after adding **one row** to `interactions.json`; the general
   loop suppresses ALDH, acetaldehyde accumulates, irritation rises, symptoms emerge.

If adding durian+beer required editing `engine.py`, the architecture is wrong.
