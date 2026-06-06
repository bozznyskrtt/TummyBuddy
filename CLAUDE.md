# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

---

## What This Project Is

**TummyBuddy Gastric Engine** is a two-compartment physiological simulator (stomach + intestine) that predicts which symptoms a user will experience after eating a meal, when they peak, and exactly why. It takes a meal's **chemicals** (protein, fat, lactose, CO₂, etc.) plus a user's **clinical profile** (reflux history, lactose intolerance, etc.) and simulates digestion over 2–6 hours.

The engine's core promise: **Physics is the engine. Knowledge is data. Foods are never hard-coded.**

**Read `gastric_engine/ARCHITECTURE.md` first** — it is the source of truth for the entire system design and explains the three pillars, the state vector, the general simulation loop, and the acceptance criteria.

---

## Quick Start & Common Commands

### Setup
```bash
cd /home/bozznyskrtt/TummyBuddy
pip install -r gastric_engine/requirements.txt
```

### Run all tests
```bash
pytest gastric_engine/tests/
```

### Run a single test
```bash
pytest gastric_engine/tests/test_acceptance.py::test_liquid_emptying_half_life_is_about_20_minutes -xvs
```

### Run the server locally (development)
```bash
cd /home/bozznyskrtt/TummyBuddy
uvicorn gastric_engine.main:app --reload --port 8000
```

### Test the `/simulate` endpoint
```bash
curl -X POST http://localhost:8000/simulate \
  -H "Content-Type: application/json" \
  -d '{"chemicals": {"fat": 55, "CO2_dissolved": 2.1}, "meal_physical": {"solid_volume_ml": 650, "liquid_volume_ml": 700}, "clinical_profile": {"reflux_gord": true, "lactose_intolerance": true}}'
```

### Type checking (if mypy installed)
```bash
mypy gastric_engine/
```

---

## Architecture Overview — Three Pillars

The engine is organized into three strictly separated pillars (see `ARCHITECTURE.md` §2):

### Pillar 1: State Vector (`core/state.py`)
One shared `GutState` object evolving over time via ODEs. Contains:
- **Stomach mechanics:** volume, pressure, fundus_pressure (drives reflux), gas, pH, emptying_rate
- **Stomach chemistry:** `stomach_species` dict (e.g., `{"lactose": 18, "CO2": 2.1, ...}`)
- **Intestine compartment:** undigested flow, fermentation, gas, osmolality
- **Enzyme activities:** set by Pillar 3, used in Pillar 2

**Key rule:** every physical quantity a symptom depends on must live here. No private state in modules.

### Pillar 2: Knowledge Base (`knowledge_base/*.json`)
**Pure data, never code.** Contains:
- `compounds.json` — what each substance does physically (e.g., CO₂ outgasses, fat slows emptying)
- `reactions.json` — biochemistry for the Tellurium model (e.g., `lactose → glucose + galactose`)
- `interactions.json` — molecular facts (e.g., durian+beer → ALDH inhibition)
- `physiology_defaults.json` — baseline parameters

Adding a new food/effect = adding a JSON row, not code. If you find yourself writing `if food == "coke"`, stop — that logic belongs in the knowledge base as data.

### Pillar 3: Personal Physiology (`physiology/`)
Clinical data → continuous stomach **properties** (not yes/no flags):
- `gastric_capacity_ml`, `les_competence` (lower = weaker LES), `mucosal_resilience`
- `enzyme_levels` (e.g., `lactase_Vmax = 0.15` for intolerance)
- `symptom_thresholds` (e.g., reflux triggers at `fundus_pressure = 0.68`)

This is why "same food, different person, different outcome" emerges naturally.

---

## The General Simulation Loop — One Code Path

`core/engine.py` contains the **only** food-independent loop (§7 in `ARCHITECTURE.md`):

1. **Build state** from chemicals + meal_physical + physiology
2. **Collect active reactions** from knowledge base (data-driven)
3. **Collect active interactions** (durian+beer → ALDH ×0.35)
4. **For each timestep:**
   - Step the Tellurium biochemistry model (e.g., lactose → glucose)
   - Apply physical effects declared in `compounds.json` (e.g., CO₂ outgassing)
   - Update mechanics (pressure, gas, pH, emptying)
   - Flow contents stomach → intestine
   - Ferment undigested matter in intestine
5. **Derive symptoms** as threshold crossings (reflux emerges when `fundus_pressure > threshold`)
6. **Counterfactual attribution:** re-run minus each chemical, measure symptom drop → root causes

**There is no `if food == X` anywhere.** The loop iterates over whatever compounds exist and applies whatever effects the data declares.

---

## Key Files & Responsibilities

| File | Purpose |
|------|---------|
| `ARCHITECTURE.md` | System design source of truth — **read this first** |
| `BUILD_PLAN.md` | Phased implementation order with acceptance tests |
| `INPUT_CONTRACT.md` | Interface with upstream ingredient→chemicals stage |
| `core/engine.py` | The general loop: simulate_core (no attribution), simulate (with attribution) |
| `core/state.py` | GutState dataclass — the shared state vector |
| `core/physics.py` | Mechanics: pressure, gas, pH, emptying, LES competence |
| `core/biochemistry.py` | Tellurium model builder + reaction/interaction collection |
| `core/intestine.py` | Downstream compartment: fermentation, gas, osmolality |
| `core/symptoms.py` | Sigmoid threshold crossings → symptom curves |
| `core/counterfactual.py` | Root-cause attribution (with recursion guard) |
| `core/output_builder.py` | Assemble final JSON response |
| `knowledge_base/loader.py` | Load JSON + build runtime registry |
| `physiology/profile_builder.py` | Clinical flags → continuous properties |
| `physiology/learning.py` | Bayesian update from symptom reports |
| `safety/red_flags.py` | Detect alarming symptoms (blood, black stool) |
| `api/routes.py` | FastAPI endpoints + test-friendly handlers |

---

## The Durian+Beer Test (Acceptance Criterion)

A correct implementation handles all three with **zero food-specific code**:

1. **Lactose intolerance** — emerges from `lactase_Vmax = 0.15` alone
2. **Gas → reflux** — emerges from CO₂ outgassing → fundus pressure → threshold
3. **Durian + beer** — works after adding **one row** to `interactions.json` (ALDH ×0.35); no engine edit needed

If adding durian+beer requires changing `engine.py`, the architecture is wrong.

---

## Testing Strategy

Tests are **acceptance-driven** — write the test first (watch it fail), then build.

### Acceptance test phases (from `BUILD_PLAN.md`):
- **Phase 0:** Schema validation + `/health` endpoint
- **Phase 1:** State vector + solver harness; liquid emptying t½ ≈ 20 min
- **Phase 2:** Knowledge base loader; adding a compound row works without code change
- **Phase 3:** Physics mechanics; burger+fries+Coke shows higher pressure than salad
- **Phase 4:** Biochemistry; lactose intolerance emerges, durian+beer works
- **Phase 5:** Intestinal fermentation; diarrhea rises hours later
- **Phase 6:** Symptom curves (reflux, bloating, diarrhea, pain)
- **Phase 7:** Counterfactual root causes (CO₂ contributes X%, fat contributes Y%)
- **Phase 8:** Personal learning; Bayesian update converges after ~5 meals
- **Phase 9:** Safety flags + confidence scoring

---

## Common Development Patterns

### Running a single test with output
```bash
pytest gastric_engine/tests/test_acceptance.py::test_liquid_emptying_half_life_is_about_20_minutes -xvs
```

The `-xvs` flags mean:
- `-x`: stop on first failure
- `-v`: verbose output
- `-s`: show print statements (no capture)

### Testing a specific symptom
Look for tests that simulate specific foods (e.g., lactose intolerance, durian+beer) in the acceptance file. Run them with:
```bash
pytest gastric_engine/tests/test_acceptance.py -k "lactose" -xvs
```

### Debugging state evolution
The `GutState` dataclass has a `.snapshot()` method. The simulation returns a `history` list. Print snapshots to trace:
```python
result = simulate_core(chemicals, meal_physical, physiology, config)
print(result["mechanism_curves"]["gastric_pressure"])
```

### Adding a new compound
1. Add a row to `gastric_engine/knowledge_base/compounds.json`
2. Add reactions (if metabolizable) to `reactions.json`
3. If it interacts with something (e.g., durian+ethanol), add to `interactions.json`
4. Update `INPUT_CONTRACT.md` with the new compound key
5. Write an acceptance test in `test_acceptance.py` (optional, but recommended)
6. Run the existing tests — they should still pass

No code changes needed in `engine.py`, `physics.py`, or `symptoms.py`.

---

## Calibration & Literature

All rate constants should be defensible. Keep a record in `utils/calibration.py`:
- Liquid gastric emptying t½ ≈ 20 min (literature source)
- Solid emptying t½ ≈ 2 hours
- Fat slows emptying (CCK feedback)

If a constant is tuned or empirical, add a comment with the source.

---

## Anti-patterns (Do NOT Do These)

| Anti-pattern | Do this instead |
|---|---|
| `if food == "coke": run_carbonation()` | Add CO₂ effects to `compounds.json` |
| New `.py` module per food | New data row in knowledge base |
| `reflux_score = 0.86 if pressure > 0.8` | Let reflux emerge from sigmoid threshold crossing |
| Hard-coding durian+beer logic | One row in `interactions.json` (ALDH modifier) |
| Fixed-step Euler integration | `scipy.solve_ivp` with adaptive stepping (LSODA/RK45) |
| Counterfactual calling `simulate()` | Counterfactual calls `simulate_core()` (guard against recursion) |
| Private state in modules | All state lives in shared `GutState` |

---

## Troubleshooting

### Tests fail after modifying `compounds.json`
Ensure the compound key is added to `INPUT_CONTRACT.md` and referenced consistently in code/tests.

### Symptom curve is flat or wrong
Check:
1. Is the symptom threshold reasonable for the physiology?
2. Are the state values (pressure, volume, osmolality) actually changing? Print `mechanism_curves` to verify.
3. Is the sigmoid gain too small? (See `utils/kinetics.py`.)

### Counterfactual attribution sums to >100% or <0%
This suggests a phase error or recursion issue. Ensure counterfactual calls `simulate_core()`, not `simulate()`.

### Biochemistry model won't build
Ensure:
- All compounds in `stomach_species` have entries in `compounds.json`
- All active reactions reference compounds that exist
- No typos in compound keys (case-sensitive)

---

## Development Notes

- **Not a git repo:** This directory is not initialized as a git repository. If you need version control, run `git init` first.
- **FastAPI optional:** Routes are structured so `api/routes.py` functions can be called directly without FastAPI (useful for testing).
- **Pytest cache:** Ignore `.pytest_cache/` — it's autogenerated.
- **Python 3.11+:** Required for type hints. Ensure your interpreter is current.

---

## Reading Order

1. **`ARCHITECTURE.md`** — system design (§0–10)
2. **`BUILD_PLAN.md`** — phased implementation with acceptance tests
3. **`INPUT_CONTRACT.md`** — upstream interface (compound vocabulary)
4. **`core/engine.py`** — the general loop (start with `simulate_core`)
5. **`gastric_engine/tests/test_acceptance.py`** — see acceptance tests in action
6. Specific pillar files (`state.py`, knowledge base files, `profile_builder.py`) as needed

---

## Questions?

If something is unclear or seems wrong, check:
1. Does `ARCHITECTURE.md` address it? (Especially §9: anti-patterns)
2. Is there an acceptance test that demonstrates the behavior?
3. Does the code follow the three-pillar separation strictly?

The engine is designed to be transparent: all complexity lives in the physics/biochemistry, not in per-food hacks.
