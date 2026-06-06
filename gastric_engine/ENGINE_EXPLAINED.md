# TummyBuddy Gastric Engine Explained

This document explains the current `gastric_engine` project in simple language.
It is meant to answer two questions:

1. What does each file do?
2. How does the engine work from request to final symptom explanation?

The short version:

```text
Meal chemicals + meal size + user health profile
        |
        v
Build a virtual stomach and intestine state
        |
        v
Simulate digestion minute by minute
        |
        v
Convert pressure, gas, acid, lactose, irritation, and intestine state into symptoms
        |
        v
Run counterfactual simulations to explain which chemicals caused the symptoms
```

The most important design rule is:

```text
Physics is the engine.
Knowledge is data.
Foods are never hard-coded.
```

That means the engine should not contain code like:

```python
if food == "coke":
    cause_reflux()
```

Instead, Coke is represented by compounds such as `CO2_dissolved`, `fat`, or `caffeine`.
The engine knows what those compounds do because the knowledge base says so.

For example:

```text
CO2_dissolved
  -> releases gas
  -> gas raises stomach pressure
  -> high fundus pressure can trigger reflux
```

This is why a Coke, sparkling water, beer, or any future carbonated drink can all use the
same logic.

## 1. Top-Level Project Shape

The main project lives inside:

```text
gastric_engine/
```

The root folder also contains helper/config files:

```text
TummyBuddy/
  CLAUDE.md
  gastric_engine/
  .pytest_cache/
  .claude/
  .agents/
  .codex/
```

Generated folders such as `__pycache__`, `.pytest_cache`, and `.venv` are not part of the
main architecture. They are created by Python, pytest, or the local environment.

## 2. Main Directory Map

```text
gastric_engine/
  api/              HTTP/API layer
  core/             simulation engine
  knowledge_base/   data that describes compounds, reactions, interactions, defaults
  physiology/       converts user health flags into engine parameters
  safety/           urgent symptom red-flag checks
  tests/            acceptance tests
  utils/            shared math, calibration, and parsing helpers
```

The most important folder is `core/`.
The most important file is:

```text
gastric_engine/core/engine.py
```

That file coordinates the simulation.

## 3. File-By-File Explanation

### `CLAUDE.md`

This is a guide for coding agents working in the repo.

It explains:

- what the project is
- how to run tests
- how to start the server
- the architecture rules
- the three major pillars
- the build phases
- anti-patterns to avoid

It is not runtime code. The engine does not import it.

### `gastric_engine/ARCHITECTURE.md`

This is the source-of-truth architecture guide.

It explains the big concept:

```text
Meal chemicals + personal physiology -> simulated digestion -> symptoms + why
```

It defines the three pillars:

1. State vector
2. Knowledge base
3. Personal physiology

It also describes the general simulation loop and why the engine should avoid food-specific
logic.

### `gastric_engine/BUILD_PLAN.md`

This is the phased implementation plan.

It lists the intended development stages:

```text
Phase 0: API scaffold
Phase 1: state and solver harness
Phase 2: knowledge base
Phase 3: physics
Phase 4: biochemistry
Phase 5: intestine
Phase 6: symptoms
Phase 7: counterfactual attribution
Phase 8: learning
Phase 9: safety and polish
```

The current tests map closely to these phases.

### `gastric_engine/INPUT_CONTRACT.md`

This is the contract between the upstream food/ingredient system and this engine.

The engine does not want raw food names. It wants compound keys such as:

```text
protein
fat
starch
lactose
FODMAP
fiber
caffeine
ethanol
CO2_dissolved
acid_load
spice_capsaicin
durian_sulfur
```

This file tells the upstream team:

- which compound names are allowed
- what units to use
- what request shape the API expects
- what response shape the API returns

### `gastric_engine/ENGINE_EXPLAINED.md`

This file.

It is a plain-language walkthrough of the engine and all important files.

### `gastric_engine/requirements.txt`

This lists Python dependencies:

```text
fastapi
pydantic
scipy
tellurium
uvicorn
pytest
```

Important current detail:

The requirements include `tellurium`, but the current implementation uses a lightweight
Michaelis-Menten model in `core/biochemistry.py`. It keeps a Tellurium-compatible boundary,
but does not require Tellurium to understand the current code path.

### `gastric_engine/__init__.py`

This marks `gastric_engine` as a Python package.

It lets imports like this work:

```python
from gastric_engine.core.engine import simulate
```

It has no major runtime behavior.

### `gastric_engine/main.py`

This is the ASGI entrypoint.

It imports the FastAPI app from:

```text
gastric_engine/api/routes.py
```

It is what a deployment server would point at:

```bash
uvicorn gastric_engine.main:app --reload --port 8000
```

In simple terms:

```text
main.py says: "The web app lives in api/routes.py."
```

## 4. API Files

### `gastric_engine/api/__init__.py`

This marks `api` as a Python package.

It has no major behavior.

### `gastric_engine/api/schemas.py`

This defines optional Pydantic request schemas.

The main class is:

```python
class SimulationRequest(BaseModel):
    chemicals: dict[str, float]
    meal_physical: dict[str, float]
    clinical_profile: dict[str, bool]
    learned_physiology: dict | None = None
    symptoms_reported: dict | None = None
    simulation_config: dict | None = Field(default=None)
```

In plain language, one simulation request contains:

- `chemicals`: what the meal contains
- `meal_physical`: how physically large the meal is
- `clinical_profile`: user's known health flags
- `learned_physiology`: optional learned user-specific parameters
- `symptoms_reported`: optional symptoms used for safety flags
- `simulation_config`: optional duration and output timing

The file also has a fallback so the project can still import even when Pydantic is not
installed in a local test environment.

### `gastric_engine/api/routes.py`

This is the API layer.

It creates a FastAPI app if FastAPI is installed:

```python
app = FastAPI(title="TummyBuddy Gastric Engine") if FastAPI else None
```

It exposes two logical handlers:

```python
health()
simulate_endpoint(payload)
```

`health()` returns:

```json
{"status": "ok"}
```

`simulate_endpoint(payload)` does the real API work:

1. Load the knowledge base.
2. Read `chemicals` from the request.
3. Separate known compounds from unknown compounds.
4. Check urgent safety flags from reported symptoms.
5. Build a personalized physiology profile.
6. Run the engine through `simulate(...)`.
7. Attach unknown compounds and safety flags.
8. Lower confidence if unknown compounds or safety flags exist.
9. Return the final response.

Important architectural point:

`routes.py` is thin. It does not contain digestion logic. It mostly prepares input and calls
the engine.

## 5. Core Engine Files

The `core/` folder is where digestion is simulated.

### `gastric_engine/core/__init__.py`

This marks `core` as a Python package.

It has no major behavior.

### `gastric_engine/core/state.py`

This defines the shared state object:

```python
@dataclass
class GutState:
    ...
```

Think of `GutState` as the engine's snapshot of the virtual body at one moment.

It stores stomach mechanics:

```text
time_min
volume_ml
solid_volume_ml
liquid_volume_ml
gas_volume_ml
pressure
fundus_pressure
wall_tension
emptying_rate
```

It stores stomach chemistry:

```text
pH
acid_secretion_rate
buffering_capacity
osmolality
stomach_species
```

It stores intestine state:

```text
intestine_species
intestine_gas_ml
intestine_osmolality
cramping
```

It stores runtime effect values:

```text
irritation
fat_brake
les_relaxation
acid_load_effect
last_emptying_fraction
```

The method:

```python
snapshot()
```

returns a plain dictionary with the values the output layer and tests need.

The most important idea:

```text
All symptom-causing body values should live in GutState.
```

That keeps the engine easier to reason about.

### `gastric_engine/core/engine.py`

This is the coordinator.

It contains:

```python
simulate_core(...)
simulate(...)
```

#### `simulate_core(...)`

This runs one simulation.

Inputs:

```text
chemicals
meal_physical
physiology
config
knowledge base
```

Main steps:

1. Load the knowledge base if one was not passed in.
2. Merge default simulation config.
3. Build output time points.
4. Filter chemicals to known positive numeric compounds.
5. Collect active interactions.
6. Apply interactions to physiology.
7. Initialize the `GutState`.
8. Apply compound effects at time 0.
9. Update mechanics.
10. Collect active biochemical reactions.
11. Build the biochemistry model.
12. Simulate time forward.
13. At each internal time step:
    - run biochemistry
    - apply compound physical effects
    - advance stomach emptying
    - move contents into the intestine
    - ferment undigested material in the intestine
    - vent gas
    - update pressure, pH, irritation, and other mechanics
14. Store snapshots in `history`.
15. Derive symptoms from the history.
16. Build the public response.

The key loop looks conceptually like this:

```text
for each output time:
  while current time has not reached target:
    step biochemistry
    apply physical effects
    empty stomach contents into intestine
    ferment intestinal contents
    vent gas
    update mechanics
  save snapshot
```

#### `simulate(...)`

This wraps `simulate_core(...)`.

It first runs the normal simulation.

Then it calls:

```python
counterfactual_attribution(...)
```

That function reruns the simulation multiple times, each time removing one chemical.

Example:

```text
Original: CO2 + fat + caffeine
Run 1:    fat + caffeine
Run 2:    CO2 + caffeine
Run 3:    CO2 + fat
```

Then it compares the results and explains which chemical mattered most.

### `gastric_engine/core/physics.py`

This handles stomach mechanics and physical effects.

Important functions:

```python
reset_transient_effects(...)
apply_physical_effect(...)
update_mechanics(...)
pressure_from_volume(...)
advance_emptying(...)
vent_gas(...)
```

#### `reset_transient_effects(...)`

Resets temporary per-step values before applying this step's compound effects.

Examples:

```text
fat_brake
les_relaxation
acid_load_effect
irritation baseline
osmolality
```

#### `apply_physical_effect(...)`

This reads effect rows from `compounds.json`.

For example, a compound can declare:

```json
{ "law": "osmotic", "target": "osmolality", "coefficient": 0.9 }
```

Then `apply_physical_effect(...)` applies that effect to the current `GutState`.

Supported laws currently include:

```text
henry_release
cck_feedback
osmotic
buffering
acid_stimulation
acidify
les_relaxation
irritation
bulk
```

Examples:

```text
henry_release:
  dissolved CO2 becomes gas

cck_feedback:
  fat slows stomach emptying

osmotic:
  lactose or FODMAP raises osmolality

les_relaxation:
  caffeine or ethanol relaxes the lower esophageal sphincter

irritation:
  capsaicin or ethanol increases mucosal irritation
```

#### `update_mechanics(...)`

Recalculates physical stomach values:

```text
total volume
gastric pressure
fundus pressure
wall tension
pH
irritation
```

Fundus pressure is important because it drives reflux.

In plain language:

```text
If stomach pressure is high,
and gas is high,
and LES competence is low,
then reflux risk rises.
```

#### `advance_emptying(...)`

Moves stomach volume forward in time.

Liquids empty faster than solids.

Fat slows emptying.

Motility changes emptying speed.

The function updates:

```text
solid_volume_ml
liquid_volume_ml
emptying_rate
last_emptying_fraction
```

#### `vent_gas(...)`

Lets excess stomach gas decay back toward baseline over time.

This avoids gas increasing forever.

### `gastric_engine/core/biochemistry.py`

This handles biochemical reactions.

It is data-driven by:

```text
knowledge_base/reactions.json
knowledge_base/compounds.json
knowledge_base/interactions.json
```

Important functions/classes:

```python
collect_active_reactions(...)
collect_active_interactions(...)
apply_interactions(...)
BiochemistryModel
build_biochemistry_model(...)
```

#### `collect_active_reactions(...)`

Looks at which compounds are present and asks:

```text
Which reactions should be active?
```

Example:

```text
If lactose is present:
  activate lactose_hydrolysis

If ethanol is present:
  activate ethanol_oxidation
```

#### `collect_active_interactions(...)`

Looks for special interactions.

Example:

```text
If durian_sulfur and ethanol are both present:
  activate durian_alcohol_aldh
```

That interaction lowers `ALDH_Vmax`, so acetaldehyde clears more slowly.

#### `apply_interactions(...)`

Takes active interactions and modifies runtime physiology.

Examples:

```text
durian + ethanol:
  ALDH_Vmax = ALDH_Vmax * 0.35

nsaid_use:
  reduce buffering capacity
```

#### `BiochemistryModel.step(...)`

Advances biochemical reactions for one time step.

Current reactions include:

```text
lactose -> glucose + galactose
starch -> maltose
protein -> peptides
ethanol -> acetaldehyde -> acetate
```

The current implementation uses Michaelis-Menten-style rates.

In simple terms:

```text
More enzyme activity means faster digestion.
Less enzyme activity means slower digestion.
```

That is why lactose intolerance works:

```text
normal lactase_Vmax = 1.0
  lactose is digested quickly

low lactase_Vmax = 0.15
  lactose remains undigested
  it moves to intestine
  it ferments
  diarrhea risk rises later
```

### `gastric_engine/core/intestine.py`

This handles the downstream intestine compartment.

Important functions:

```python
empty_to_intestine(...)
ferment_in_intestine(...)
```

#### `empty_to_intestine(...)`

When stomach contents empty, a fraction of each stomach compound moves into:

```python
state.intestine_species
```

Example:

```text
If 10 percent of stomach contents empty,
then 10 percent of each remaining compound moves to the intestine.
```

#### `ferment_in_intestine(...)`

Looks for undigested compounds that ferment.

For example:

```text
lactose
FODMAP
```

If these reach the intestine undigested:

```text
they ferment
intestinal gas rises
intestinal osmolality rises
cramping rises
diarrhea risk may rise
```

This file is why the engine can explain delayed symptoms.

### `gastric_engine/core/symptoms.py`

This converts body state into symptom probability curves.

Main function:

```python
derive_symptoms(history, physiology)
```

It reads the simulated history and produces:

```text
time_min
reflux
bloating
diarrhea
upper_pain
```

Each symptom is a list of values over time.

Example:

```text
time:     0, 10, 20, 30, 40
reflux:   0.1, 0.4, 0.9, 0.8, 0.5
```

The symptoms come from threshold crossings:

```text
reflux:
  fundus_pressure crosses reflux threshold

bloating:
  gas volume and intestinal gas get high

diarrhea:
  intestine osmolality gets high

upper_pain:
  irritation gets high
```

This file does not decide symptoms by food name.
It decides symptoms by simulated body state.

### `gastric_engine/core/counterfactual.py`

This explains root causes.

Main function:

```python
counterfactual_attribution(...)
```

It compares the normal simulation against simulations with one chemical removed.

Example:

```text
Meal has:
  CO2_dissolved
  fat
  caffeine

Baseline reflux burden:
  high

Remove CO2_dissolved:
  reflux burden drops a lot

Remove fat:
  reflux burden drops some

Remove caffeine:
  reflux burden drops a little
```

Then the engine can say:

```text
CO2_dissolved contributed 52 percent of reflux burden.
fat contributed 28 percent.
caffeine contributed 20 percent.
```

This file also contains human-readable mechanism messages, such as:

```text
CO2_dissolved:
  carbonation outgassing raised fundus pressure

fat:
  delayed emptying kept the stomach full and pressurized

lactose:
  undigested lactose raised osmotic load and fermentation
```

### `gastric_engine/core/output_builder.py`

This builds the public response.

Important functions:

```python
mechanism_curves(...)
build_summary(...)
build_output(...)
```

#### `mechanism_curves(...)`

Turns the history snapshots into lists over time.

Examples:

```text
gas_volume_ml:    [20, 30, 45, 40, ...]
gastric_pressure: [0.1, 0.3, 0.6, 0.5, ...]
pH:               [3.0, 2.8, 2.5, ...]
```

#### `build_summary(...)`

Finds the strongest symptom peak and labels risk.

Example:

```json
{
  "main_symptom": "reflux",
  "risk_level": "high",
  "peak_time_min": 30,
  "confidence": "medium"
}
```

#### `build_output(...)`

Assembles the final response:

```text
summary
symptom_curves
mechanism_curves
root_causes
unknown_compounds
safety_flags
metadata
```

## 6. Knowledge Base Files

The `knowledge_base/` folder is how the engine knows what compounds do.

This is one of the strongest parts of the design.

### `gastric_engine/knowledge_base/__init__.py`

Marks `knowledge_base` as a Python package.

It has no major behavior.

### `gastric_engine/knowledge_base/loader.py`

Loads JSON files into a `KnowledgeBase` dataclass.

The dataclass contains:

```python
compounds
reactions
interactions
physiology_defaults
```

It also exposes:

```python
compound_keys
```

That property returns all valid compound names from `compounds.json`.

The API uses this to separate:

```text
known compounds
unknown compounds
```

### `gastric_engine/knowledge_base/compounds.json`

This is the authoritative compound vocabulary.

It tells the engine what each compound does.

Examples:

```text
CO2_dissolved:
  physical effect: henry_release

fat:
  physical effect: cck_feedback

lactose:
  reaction: lactose_hydrolysis
  physical effect: osmotic
  if undigested: ferments in intestine

FODMAP:
  physical effect: osmotic
  if undigested: ferments in intestine

caffeine:
  acid stimulation
  LES relaxation

ethanol:
  reaction: ethanol_oxidation
  LES relaxation
  irritation
```

If you want the engine to understand a new compound, this is usually the first place to
add it.

### `gastric_engine/knowledge_base/reactions.json`

This defines biochemical reactions.

Examples:

```text
lactose_hydrolysis:
  lactose -> glucose + galactose

starch_digestion:
  starch -> maltose

protein_digestion:
  protein -> peptides

ethanol_oxidation:
  ethanol -> acetaldehyde -> acetate
```

The engine activates only reactions for compounds that are present.

### `gastric_engine/knowledge_base/interactions.json`

This defines special interactions that physics alone cannot infer.

Examples:

```text
durian_sulfur + ethanol:
  ALDH_Vmax is multiplied by 0.35

nsaid_use:
  buffering capacity is reduced

h_pylori_history:
  mucosal resilience is reduced
```

This is how the engine supports special cases without writing food-specific code.

Durian plus beer works because:

```text
durian_sulfur and ethanol are present
  -> interaction activates
  -> ALDH enzyme is reduced
  -> acetaldehyde accumulates
  -> irritation rises
```

### `gastric_engine/knowledge_base/physiology_defaults.json`

This defines the baseline person and clinical modifiers.

Default physiology includes:

```text
gastric_capacity_ml
baseline_acid_secretion
les_competence
mucosal_resilience
gastric_motility
```

Default enzyme levels include:

```text
lactase_Vmax
amylase_Vmax
pepsin_Vmax
ADH_Vmax
ALDH_Vmax
```

Default symptom thresholds include:

```text
reflux_pressure_threshold
bloating_volume_threshold
pain_irritation_threshold
diarrhea_osmotic_threshold
```

Clinical modifiers change those defaults.

Example:

```text
reflux_gord:
  lower LES competence
  lower reflux threshold

lactose_intolerance:
  lower lactase_Vmax

gastritis_history:
  lower mucosal resilience
  lower pain threshold
```

## 7. Physiology Files

The `physiology/` folder turns user health information into simulation parameters.

### `gastric_engine/physiology/__init__.py`

Marks `physiology` as a Python package.

It has no major behavior.

### `gastric_engine/physiology/profile_builder.py`

This builds a personalized physiology profile.

Main function:

```python
build_profile(clinical_profile, learned_physiology=None)
```

It starts from defaults in:

```text
knowledge_base/physiology_defaults.json
```

Then it applies clinical flags.

Example input:

```json
{
  "reflux_gord": true,
  "lactose_intolerance": true
}
```

becomes something like:

```text
les_competence is lower
reflux threshold is lower
lactase_Vmax is lower
```

Then it overlays `learned_physiology` if provided.

This matters because two users can eat the same meal and get different outcomes.

### `gastric_engine/physiology/learning.py`

This implements a simple Bayesian-style update for learned physiology.

Main function:

```python
update_posterior_from_meal_logs(prior, logs)
```

Current focus:

```text
lactase_Vmax
```

If a user repeatedly reports diarrhea after lactose-heavy meals, the posterior lactase
estimate moves lower and becomes more certain.

In simple terms:

```text
The engine learns:
"This user seems more lactose-sensitive than we first thought."
```

## 8. Safety Files

### `gastric_engine/safety/__init__.py`

Marks `safety` as a Python package.

It has no major behavior.

### `gastric_engine/safety/red_flags.py`

Checks reported symptoms for urgent warning signs.

Current red flags:

```text
blood_in_vomit
black_stool
severe_chest_pain
```

If any are present, the API response includes a safety flag.

Important:

Safety flags are not treated as probabilities.
They are direct warnings.

## 9. Utility Files

### `gastric_engine/utils/__init__.py`

Marks `utils` as a Python package.

It has no major behavior.

### `gastric_engine/utils/parsing.py`

Builds the initial `GutState` from request input.

Main function:

```python
initialize_state(chemicals, meal_physical, physiology)
```

It reads:

```text
solid_volume_ml
liquid_volume_ml
chemicals
enzyme levels
```

Then it creates a `GutState`.

Example:

```text
solid_volume_ml = 650
liquid_volume_ml = 700
chemicals = {"fat": 55, "CO2_dissolved": 2.1}
```

becomes:

```text
state.solid_volume_ml = 650
state.liquid_volume_ml = 700
state.stomach_species["fat"] = 55
state.stomach_species["CO2_dissolved"] = 2.1
```

### `gastric_engine/utils/kinetics.py`

Shared math helpers.

Important helpers:

```text
clamp
sigmoid
michaelis_menten_rate
consume_michaelis
exponential_remaining
first_order_release
peak_time
curve_peak
curve_auc
apply_path
```

What they mean:

```text
clamp:
  keep a value between min and max

sigmoid:
  turn a threshold crossing into a smooth probability

michaelis_menten_rate:
  enzyme-style reaction speed

exponential_remaining:
  half-life decay, used for emptying and gas venting

curve_auc:
  total symptom burden over time
```

`exponential_remaining(...)` tries to use scipy's `solve_ivp` if available, with an
analytical fallback.

### `gastric_engine/utils/calibration.py`

Central place for model constants.

Examples:

```text
LIQUID_EMPTYING_HALF_LIFE_MIN = 20.0
SOLID_EMPTYING_HALF_LIFE_MIN = 120.0
CO2_RELEASE_RATE_PER_MIN = 0.025
GAS_VENT_HALF_LIFE_MIN = 28.0
LACTASE_G_PER_MIN = 2.20
FERMENTATION_RATE_PER_MIN = 0.008
SYMPTOM_GAIN = 10.0
```

This is good architecture because constants are not scattered everywhere.

If the model needs better scientific calibration, this file is one major place to improve.

## 10. Test Files

### `gastric_engine/tests/test_acceptance.py`

This is the main test suite.

It tests the engine by behavior, not tiny implementation details.

Current tests cover:

```text
health endpoint and response shape
liquid emptying half-life
new compound row works without engine change
Coke meal has higher pressure than salad
lactose intolerance
durian plus beer interaction
intestinal late symptoms
symptom peak timing
counterfactual attribution
Bayesian learning
safety flags and unknown compounds
```

This is a good test style for this project because the engine is a simulation.
The tests ask:

```text
Does the whole system behave correctly?
```

rather than:

```text
Did this one private helper produce exactly this internal number?
```

## 11. Full Request Lifecycle

This section traces one API request through the engine.

### Step 1: Client sends a request

Example:

```json
{
  "chemicals": {
    "fat": 55,
    "CO2_dissolved": 2.1,
    "caffeine": 60
  },
  "meal_physical": {
    "solid_volume_ml": 650,
    "liquid_volume_ml": 700
  },
  "clinical_profile": {
    "reflux_gord": true
  },
  "simulation_config": {
    "duration_min": 120,
    "output_dt_min": 10
  }
}
```

This represents a large fatty carbonated caffeinated meal for a reflux-prone user.

### Step 2: API receives it

File:

```text
api/routes.py
```

Function:

```python
simulate_endpoint(payload)
```

It loads the knowledge base and separates:

```text
known compounds:
  fat
  CO2_dissolved
  caffeine

unknown compounds:
  anything not in compounds.json
```

### Step 3: Safety flags are checked

File:

```text
safety/red_flags.py
```

If the user reported something like:

```json
{"blood_in_vomit": true}
```

the response gets an urgent safety flag.

### Step 4: Physiology profile is built

File:

```text
physiology/profile_builder.py
```

Input:

```json
{"reflux_gord": true}
```

The profile builder starts with defaults and changes:

```text
les_competence lower
reflux threshold lower
```

Meaning:

```text
This user is more likely to reflux at the same stomach pressure.
```

### Step 5: `simulate(...)` starts

File:

```text
core/engine.py
```

The API calls:

```python
simulate(known_chemicals, meal_physical, physiology, config, kb=kb)
```

`simulate(...)` first calls:

```python
simulate_core(...)
```

### Step 6: Config is prepared

The default config is:

```python
DEFAULT_CONFIG = {"duration_min": 360, "output_dt_min": 10}
```

If the request passes a config, it overrides defaults.

Example:

```text
duration_min = 120
output_dt_min = 10
```

The engine will return values at:

```text
0, 10, 20, 30, ... 120 minutes
```

Internally, it still steps minute by minute.

### Step 7: Chemicals are cleaned

The engine keeps only:

```text
known compound keys
numeric values
positive amounts
```

So this:

```json
{
  "fat": 55,
  "CO2_dissolved": 2.1,
  "mystery_extract": 5,
  "ethanol": 0
}
```

becomes:

```json
{
  "fat": 55,
  "CO2_dissolved": 2.1
}
```

### Step 8: Interactions are collected

File:

```text
core/biochemistry.py
```

Function:

```python
collect_active_interactions(...)
```

Example:

```text
durian_sulfur + ethanol
  -> activate durian_alcohol_aldh
```

For a Coke-style meal, there may be no active interaction.

### Step 9: Interactions modify runtime physiology

Function:

```python
apply_interactions(...)
```

Example:

```text
durian_alcohol_aldh:
  ALDH_Vmax = ALDH_Vmax * 0.35
```

The original profile is not mutated directly. A runtime copy is adjusted.

### Step 10: Initial state is created

File:

```text
utils/parsing.py
```

Function:

```python
initialize_state(...)
```

It creates a `GutState` like:

```text
time_min = 0
solid_volume_ml = 650
liquid_volume_ml = 700
gas_volume_ml = baseline gas
stomach_species = {
  "fat": 55,
  "CO2_dissolved": 2.1,
  "caffeine": 60
}
```

### Step 11: Time-zero physical effects are applied

File:

```text
core/engine.py
core/physics.py
```

The engine calls:

```python
_apply_compound_effects(...)
```

That loops through each compound:

```text
fat
CO2_dissolved
caffeine
```

For each compound, it reads `compounds.json`.

Then it applies declared effects:

```text
fat:
  cck_feedback -> fat_brake rises

CO2_dissolved:
  henry_release -> dissolved CO2 may become gas

caffeine:
  acid_stimulation -> acid secretion rises
  les_relaxation -> reflux protection weakens
```

### Step 12: Mechanics are updated

File:

```text
core/physics.py
```

Function:

```python
update_mechanics(...)
```

It calculates:

```text
total stomach volume
gastric pressure
fundus pressure
pH
irritation
wall tension
```

This turns chemical and volume facts into physical body facts.

### Step 13: Active reactions are collected

File:

```text
core/biochemistry.py
```

Function:

```python
collect_active_reactions(...)
```

If lactose is present:

```text
lactose_hydrolysis active
```

If ethanol is present:

```text
ethanol_oxidation active
```

If the meal only has fat, caffeine, and CO2:

```text
there may be no biochemical reaction
```

because those are mostly physical effects in the current model.

### Step 14: Biochemistry model is built

File:

```text
core/biochemistry.py
```

Function:

```python
build_biochemistry_model(...)
```

It builds a `BiochemistryModel` using active reactions and enzyme levels.

Example:

```text
lactase_Vmax controls lactose digestion speed
ALDH_Vmax controls acetaldehyde clearance speed
```

### Step 15: The simulation loop runs

File:

```text
core/engine.py
```

The loop progresses through time.

For each internal minute:

```text
1. Step biochemistry
2. Apply physical effects
3. Advance emptying
4. Move contents to intestine
5. Ferment intestine contents
6. Vent gas
7. Update mechanics
```

This repeats until the simulation duration is reached.

### Step 16: Biochemistry changes compounds

File:

```text
core/biochemistry.py
```

Example with lactose:

```text
normal lactase:
  lactose amount falls quickly

low lactase:
  lactose remains high
```

Example with ethanol:

```text
ethanol becomes acetaldehyde
acetaldehyde becomes acetate
```

If ALDH is inhibited:

```text
acetaldehyde remains higher
irritation rises
```

### Step 17: Physical effects change the state

File:

```text
core/physics.py
```

Examples:

```text
CO2_dissolved releases gas.
fat increases fat_brake.
caffeine increases acid and LES relaxation.
lactose increases osmolality.
spice_capsaicin increases irritation.
```

### Step 18: Stomach empties into intestine

Files:

```text
core/physics.py
core/intestine.py
```

First:

```python
advance_emptying(...)
```

calculates how much of the stomach emptied.

Then:

```python
empty_to_intestine(...)
```

moves the same fraction of each compound to the intestine.

### Step 19: Intestinal fermentation happens

File:

```text
core/intestine.py
```

Function:

```python
ferment_in_intestine(...)
```

If undigested lactose or FODMAP reaches the intestine:

```text
fermentation produces gas
intestine_gas_ml rises
intestine_osmolality rises
cramping rises
```

This is the delayed symptom path.

### Step 20: Gas vents

File:

```text
core/physics.py
```

Function:

```python
vent_gas(...)
```

Excess gas decays back toward baseline over time.

This prevents unrealistic gas buildup.

### Step 21: Snapshots are saved

File:

```text
core/state.py
```

Function:

```python
state.snapshot()
```

At every output time, the engine saves values like:

```text
time_min
volume_ml
gas_volume_ml
gastric_pressure
fundus_pressure
pH
osmolality
intestine_gas_ml
intestine_osmolality
lactose_remaining_g
acetaldehyde_g
irritation
```

These snapshots become `history`.

### Step 22: Symptoms are derived

File:

```text
core/symptoms.py
```

Function:

```python
derive_symptoms(history, runtime_physiology)
```

It produces probability curves:

```text
reflux
bloating
diarrhea
upper_pain
```

Example:

```text
fundus pressure high
  -> reflux curve rises

intestinal osmolality high
  -> diarrhea curve rises

irritation high
  -> upper pain curve rises
```

### Step 23: Output is built

File:

```text
core/output_builder.py
```

Function:

```python
build_output(...)
```

It returns:

```text
summary
symptom_curves
mechanism_curves
root_causes
unknown_compounds
safety_flags
metadata
```

At this point, `simulate_core(...)` is done.

### Step 24: Counterfactual attribution runs

File:

```text
core/counterfactual.py
```

Because the public API called `simulate(...)`, not just `simulate_core(...)`, the engine now
explains why symptoms happened.

It removes one chemical at a time and reruns `simulate_core(...)`.

Example:

```text
Baseline:
  CO2 + fat + caffeine

Counterfactual A:
  fat + caffeine

Counterfactual B:
  CO2 + caffeine

Counterfactual C:
  CO2 + fat
```

Then it compares symptom burden.

If removing `CO2_dissolved` drops reflux the most, CO2 becomes the top reflux driver.

### Step 25: API attaches metadata and returns

Back in:

```text
api/routes.py
```

The API attaches:

```text
unknown_compounds
safety_flags
confidence changes
```

Then the client receives the final response.

## 12. Example: Carbonated Fatty Meal and Reflux

Input:

```text
fat = 55g
CO2_dissolved = 2.1g
caffeine = 60mg
large solid volume
large liquid volume
reflux_gord = true
```

Engine reasoning:

```text
fat slows emptying
large meal keeps stomach full
CO2 releases gas
gas increases stomach pressure
caffeine relaxes LES
reflux-prone physiology lowers the reflux threshold
fundus pressure crosses threshold
reflux probability rises
```

Output:

```text
main symptom: reflux
risk: high or medium depending on curve peak
peak time: usually early, around 20-40 min in tests
root cause: CO2 often ranks highest
```

## 13. Example: Lactose Intolerance and Late Diarrhea

Input:

```text
lactose = 18g
lactose_intolerance = true
duration = 360 min
```

Engine reasoning:

```text
lactose requires lactase
lactose intolerance lowers lactase_Vmax
lactose is digested slowly
undigested lactose empties into intestine
lactose ferments
intestinal gas rises
intestinal osmolality rises
diarrhea curve rises later
```

Output:

```text
diarrhea risk rises after stomach phase
root cause points to lactose
mechanism mentions osmotic load and fermentation
```

## 14. Example: Durian Plus Beer

Input:

```text
ethanol > 0
durian_sulfur > 0
```

Knowledge base:

```text
interactions.json says:
  if durian_sulfur and ethanol are both present,
  multiply ALDH_Vmax by 0.35
```

Engine reasoning:

```text
ethanol converts to acetaldehyde
ALDH clears acetaldehyde
durian interaction lowers ALDH activity
acetaldehyde clears more slowly
acetaldehyde increases irritation
upper pain or irritation risk can rise
```

Important point:

```text
No durian-specific code is needed in engine.py.
```

The behavior comes from data.

## 15. How The Major Pieces Talk To Each Other

```text
api/routes.py
  calls build_profile(...)
  calls simulate(...)

physiology/profile_builder.py
  loads physiology_defaults.json
  returns personalized physiology

core/engine.py
  loads or receives knowledge base
  initializes GutState
  calls biochemistry, physics, intestine, symptoms, output

core/physics.py
  reads compound physical effects
  updates pressure, pH, emptying, gas, irritation

core/biochemistry.py
  reads reactions and interactions
  updates stomach_species

core/intestine.py
  moves compounds downstream
  ferments undigested compounds

core/symptoms.py
  converts body state into symptom curves

core/counterfactual.py
  reruns simulate_core without each chemical
  computes root causes

core/output_builder.py
  formats final response
```

## 16. What The Engine Currently Does Well

The current architecture has several good properties:

1. It has one main simulation loop.
2. The API layer is thin.
3. Food behavior is data-driven.
4. State is centralized in `GutState`.
5. Symptoms emerge from simulated body state.
6. Counterfactual attribution explains causes.
7. Tests cover the major acceptance behavior.

## 17. Current Limitations

These are not failures. They are natural next steps.

### Knowledge base validation is missing

The JSON files are powerful, but string keys can be fragile.

For example, a typo in a law name could silently fail.

Good improvement:

```text
Add a knowledge base validator.
```

It should check:

```text
all effect laws are supported
all referenced reactions exist
all physiology paths exist
all compound rows have required fields
INPUT_CONTRACT.md matches compounds.json
```

### Real Pydantic response schemas are not complete

There is a request schema, but the response is mostly plain dictionaries.

Good improvement:

```text
Add typed response models.
```

This would make the API contract more reliable.

### Biochemistry backend is lightweight

The docs mention Tellurium.

The current code uses a local Michaelis-Menten model with a Tellurium-compatible concept.

Good improvement:

```text
Make the biochemistry backend explicit:
  local_mm
  tellurium
```

Then tests can use `local_mm`, while production can eventually use Tellurium.

### Calibration needs stronger source tracking

Constants are centralized in `utils/calibration.py`, which is good.

But the source notes are brief.

Good improvement:

```text
Add detailed citations or calibration notes for each constant.
```

### No broader app architecture yet

This is currently an engine/backend package.

It does not yet include:

```text
database
user accounts
meal history storage
frontend
deployment config
observability
auth
```

That is fine for an engine module, but important to know.

## 18. Best Next Improvement

The best next improvement is:

```text
Add a knowledge base validation layer.
```

Why?

Because the architecture depends on JSON data being correct.

The engine's best idea is that behavior comes from data, not food-specific code.
So the data needs strong validation.

Recommended new file:

```text
gastric_engine/knowledge_base/validation.py
```

Recommended new tests:

```text
gastric_engine/tests/test_knowledge_base_validation.py
```

Validation should catch:

```text
unknown physical effect laws
reaction IDs referenced by compounds but missing in reactions.json
interaction effects pointing at invalid physiology fields
compound keys in INPUT_CONTRACT.md missing from compounds.json
required fields missing from compound rows
invalid units or empty IDs
```

This would make the engine safer to extend.

## 19. Mental Model To Remember

If you remember only one thing, remember this:

```text
The engine is not a food lookup table.
It is a small digestion simulator.
```

Food becomes chemicals.

Chemicals affect a shared gut state.

The gut state changes over time.

Symptoms come from the changed state.

Root causes come from rerunning the simulation without each chemical.

That is the whole architecture.
