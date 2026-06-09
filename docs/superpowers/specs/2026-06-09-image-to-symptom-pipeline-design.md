# Image → Symptom Visualization Pipeline — Design

**Date:** 2026-06-09
**Status:** Approved (pending spec review)

## Goal

Wire the `recipe` branch (Gemini image → ingredients) into the `dev` gastric
engine and visualize the simulation output. Deliver one runnable end-to-end
path: **food image → ingredients → chemicals → simulation → interactive chart.**

This implements the "Stage 2: ingredient → chemicals" bridge that
`INPUT_CONTRACT.md` specifies but the codebase never implemented.

## Architecture

```
 food image (upload or bundled sample)
   │
   ▼  pipeline/image_to_ingredients.py        ← ported from recipe notebook (Gemini)
 {dish, ingredients:[{name, amount}]}
   │
   ▼  pipeline/ingredients_to_chemicals.py    ← NEW second Gemini stage (the bridge)
 {chemicals:{compound vocab}, meal_physical:{…}, unknown_compounds:[…]}
   │
   ▼  core/engine.simulate  (existing — untouched)
 {summary, symptom_curves, mechanism_curves, root_causes, safety_flags}
   │
   ▼  GET / static page  +  POST /analyze-image  (FastAPI)
 interactive Chart.js page
```

`core/` is not modified. The engine remains the single food-independent loop.

## Components

### 1. `gastric_engine/pipeline/image_to_ingredients.py`
Ports the recipe notebook's `predict_food_and_ingredients` into the repo.
- Uses the modern `google-genai` SDK, model from `GEMINI_MODEL`
  (default `gemini-2.5-flash`), key from `GEMINI_API_KEY`.
- Accepts image **bytes** or a path; normalizes to RGB via Pillow.
- Returns `{dish, ingredients:[{name, amount}]}`.
- Import-guards `google-genai` so the rest of the repo imports without it.

### 2. `gastric_engine/pipeline/ingredients_to_chemicals.py` (the bridge)
A second Gemini call that maps the ingredient list onto the engine's compound
vocabulary.
- The prompt is **built from `knowledge_base/compounds.json`** at runtime, so
  the vocabulary is read from data — never hard-coded. Honors the project's
  "foods are never hard-coded" rule.
- Returns `chemicals` (only valid compound keys, positive values) +
  `meal_physical` (`solid_volume_ml`, `liquid_volume_ml`, `meal_mass_g`).
- Anything it cannot map → `unknown_compounds` list (the engine already lowers
  confidence when this is non-empty).
- Validation layer drops keys not in the vocabulary and coerces amounts to
  numbers before returning, regardless of model output quality.

### 3. `gastric_engine/pipeline/orchestrator.py`
Runs image → ingredients → chemicals → `simulate_endpoint`, threading the
request's `clinical_profile` through. Returns the full simulation result plus
`dish`, `ingredients`, and mapped `chemicals` so the UI can show the reasoning
at every stage.

### 4. API (`gastric_engine/api/routes.py`)
- `POST /analyze-image` — multipart image upload + clinical-profile fields →
  orchestrator → JSON result.
- `GET /` — serves `api/static/index.html`.
- Static files served from `api/static/`.

### 5. `gastric_engine/api/static/index.html`
Single page, Chart.js via CDN. Lets the user:
- Upload an image **or** pick a bundled sample.
- Toggle clinical flags (reflux_gord, lactose_intolerance, gastritis_history…).
- See results: **summary card** (main symptom, risk, peak time, confidence),
  **symptom-curves** line chart (reflux/bloating/diarrhea/upper_pain vs time),
  **mechanism "why" chart** (gastric_pressure, fundus_pressure, gas_volume_ml,
  pH), detected **dish + ingredients + mapped chemicals**, and **root-cause
  drivers** with advice text.
- Re-toggling a clinical flag re-runs the analysis → demonstrates
  "same food, different person, different outcome."

## Supporting changes
- `gastric_engine/requirements.txt`: add `google-genai`, `pillow`,
  `python-multipart`.
- Copy 2–3 sample images from the `recipe` branch `sample image/` into
  `api/static/samples/` for the demo.
- Secrets: `GEMINI_API_KEY` lives only in git-ignored `.env`; never committed.

## Error handling
- Missing `GEMINI_API_KEY` → clear, actionable error.
- Non-JSON Gemini output → caught; surfaced as an error with the raw text
  (mirrors the notebook's existing behavior).
- Unmappable ingredients → `unknown_compounds`; confidence lowered by the engine.
- `google-genai` / FastAPI not installed → import guards keep `pytest` green.

## Testing
- Unit: `ingredients_to_chemicals` with a **mocked** Gemini client — asserts
  only valid compound keys survive, unknowns are reported, amounts parse to
  numbers.
- Unit: `image_to_ingredients` with a stubbed client — asserts the
  `{dish, ingredients}` shape.
- Unit: orchestrator with both stages stubbed → reaches `simulate_endpoint` and
  returns a well-formed result.
- Live: with the real `GEMINI_API_KEY`, run a sample image end-to-end and load
  the chart page.

## Notes
- Model: `gemini-2.5-flash` (matches recipe notebook). `providers.py` currently
  defaults to a non-existent `gemini-3.5-flash`; that module is left untouched,
  and the new code does not copy that default.
