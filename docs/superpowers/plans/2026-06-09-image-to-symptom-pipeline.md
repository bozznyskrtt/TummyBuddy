# Image → Symptom Visualization Pipeline Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Wire the recipe branch's Gemini image→ingredients stage into the gastric engine and visualize the simulation output as an interactive web page.

**Architecture:** A new `gastric_engine/pipeline/` package adds two Gemini stages (image→ingredients, ingredients→chemicals) and an orchestrator that feeds the existing `simulate_endpoint`. FastAPI gains an upload endpoint and serves a Chart.js page. `core/` is untouched. All Gemini calls go through one injectable `generate_json` helper so tests run without the SDK or a key.

**Tech Stack:** Python 3.11, FastAPI, `google-genai`, Pillow, Chart.js (CDN), pytest.

---

## File Structure

- Create `gastric_engine/pipeline/__init__.py` — package marker.
- Create `gastric_engine/pipeline/gemini_client.py` — single Gemini JSON-call wrapper (`generate_json`), import-guarded, env-driven.
- Create `gastric_engine/pipeline/ingredients_to_chemicals.py` — the bridge: ingredients → compound vocab + meal_physical, prompt built from KB.
- Create `gastric_engine/pipeline/image_to_ingredients.py` — ported recipe-notebook stage.
- Create `gastric_engine/pipeline/orchestrator.py` — image → ingredients → chemicals → `simulate_endpoint`.
- Create `gastric_engine/api/static/index.html` — Chart.js visualization page.
- Create `gastric_engine/api/static/samples/` — 2–3 demo images from the recipe branch.
- Modify `gastric_engine/api/routes.py` — add `POST /analyze-image`, `GET /`, static mount.
- Modify `gastric_engine/requirements.txt` — add `google-genai`, `pillow`, `python-multipart`.
- Create tests under `gastric_engine/tests/` for each pipeline module.

---

## Task 1: Dependencies and package scaffold

**Files:**
- Modify: `gastric_engine/requirements.txt`
- Create: `gastric_engine/pipeline/__init__.py`
- Create: `gastric_engine/api/static/samples/` (image files)

- [ ] **Step 1: Add dependencies**

Append to `gastric_engine/requirements.txt`:

```
google-genai>=1.0
pillow>=10.0
python-multipart>=0.0.9
```

- [ ] **Step 2: Create the package marker**

Create `gastric_engine/pipeline/__init__.py`:

```python
"""Pipeline stages bridging food images to the gastric engine."""
```

- [ ] **Step 3: Bundle sample images from the recipe branch**

Run:

```bash
cd /home/bozznyskrtt/TummyBuddy
mkdir -p gastric_engine/api/static/samples
git show "origin/recipe:sample image/ramen.jpg" > gastric_engine/api/static/samples/ramen.jpg
git show "origin/recipe:sample image/fish_and_chips.jpg" > gastric_engine/api/static/samples/fish_and_chips.jpg
git show "origin/recipe:sample image/tonkatsu_curry.jpg" > gastric_engine/api/static/samples/tonkatsu_curry.jpg
ls -la gastric_engine/api/static/samples/
```

Expected: three non-empty `.jpg` files listed.

- [ ] **Step 4: Install dependencies**

Run: `pip install -r gastric_engine/requirements.txt`
Expected: installs `google-genai`, `pillow`, `python-multipart` without error.

- [ ] **Step 5: Commit**

```bash
git add gastric_engine/requirements.txt gastric_engine/pipeline/__init__.py gastric_engine/api/static/samples/
git commit -m "chore: add pipeline deps, package scaffold, sample images"
```

---

## Task 2: Gemini JSON-call wrapper

A single place that talks to Gemini and returns parsed JSON. Import-guarded so the
rest of the repo imports without `google-genai`. Both stages depend on it but
inject a stub in tests.

**Files:**
- Create: `gastric_engine/pipeline/gemini_client.py`
- Test: `gastric_engine/tests/test_gemini_client.py`

- [ ] **Step 1: Write the failing test**

Create `gastric_engine/tests/test_gemini_client.py`:

```python
import pytest

from gastric_engine.pipeline import gemini_client


def test_strip_json_fences_removes_markdown_wrapper():
    raw = "```json\n{\"a\": 1}\n```"
    assert gemini_client._strip_json_fences(raw) == '{"a": 1}'


def test_strip_json_fences_passes_through_plain_json():
    assert gemini_client._strip_json_fences('{"a": 1}') == '{"a": 1}'


def test_parse_json_text_raises_actionable_error_on_garbage():
    with pytest.raises(ValueError) as exc:
        gemini_client._parse_json_text("not json at all")
    assert "Gemini did not return valid JSON" in str(exc.value)
    assert "not json at all" in str(exc.value)


def test_resolve_api_key_errors_when_missing(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    with pytest.raises(RuntimeError) as exc:
        gemini_client._resolve_api_key()
    assert "GEMINI_API_KEY" in str(exc.value)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest gastric_engine/tests/test_gemini_client.py -v`
Expected: FAIL — `ModuleNotFoundError: gastric_engine.pipeline.gemini_client`.

- [ ] **Step 3: Write minimal implementation**

Create `gastric_engine/pipeline/gemini_client.py`:

```python
"""Single Gemini call site. Returns parsed JSON.

Import-guarded: the SDK is only imported when an actual call is made, so the
rest of the repo (and the test suite) imports without `google-genai` installed.
"""

from __future__ import annotations

import json
import os
import re
from typing import Any

DEFAULT_MODEL = "gemini-2.5-flash"

_FENCE_RE = re.compile(r"^```(?:json)?\s*|\s*```$", re.IGNORECASE)


def _strip_json_fences(text: str) -> str:
    cleaned = text.strip()
    cleaned = _FENCE_RE.sub("", cleaned)
    return cleaned.strip()


def _parse_json_text(text: str) -> Any:
    try:
        return json.loads(_strip_json_fences(text))
    except json.JSONDecodeError as exc:
        raise ValueError(
            f"Gemini did not return valid JSON. Raw response: {text!r}"
        ) from exc


def _resolve_api_key() -> str:
    key = os.environ.get("GEMINI_API_KEY")
    if not key:
        raise RuntimeError(
            "GEMINI_API_KEY is not set. Add it to your environment or .env file."
        )
    return key


def _resolve_model(model: str | None) -> str:
    return model or os.environ.get("GEMINI_MODEL") or DEFAULT_MODEL


def generate_json(prompt: str, *, image: Any | None = None, model: str | None = None) -> Any:
    """Call Gemini with a text prompt (and optional PIL image) and parse JSON."""
    from google import genai  # local import: only needed for real calls
    from google.genai import types

    client = genai.Client(api_key=_resolve_api_key())
    contents: list[Any] = [image, prompt] if image is not None else [prompt]
    response = client.models.generate_content(
        model=_resolve_model(model),
        contents=contents,
        config=types.GenerateContentConfig(response_mime_type="application/json"),
    )
    return _parse_json_text(response.text)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest gastric_engine/tests/test_gemini_client.py -v`
Expected: PASS (4 passed).

- [ ] **Step 5: Commit**

```bash
git add gastric_engine/pipeline/gemini_client.py gastric_engine/tests/test_gemini_client.py
git commit -m "feat: add import-guarded Gemini JSON call wrapper"
```

---

## Task 3: Ingredients → chemicals bridge

The missing "Stage 2". Builds its prompt from `compounds.json` (vocabulary is
data, never hard-coded), asks Gemini to map ingredients onto that vocabulary
plus meal volumes/mass, then validates the result: only known compound keys with
positive numeric values survive; everything else is reported as `unknown_compounds`.

**Files:**
- Create: `gastric_engine/pipeline/ingredients_to_chemicals.py`
- Test: `gastric_engine/tests/test_ingredients_to_chemicals.py`

- [ ] **Step 1: Write the failing test**

Create `gastric_engine/tests/test_ingredients_to_chemicals.py`:

```python
from gastric_engine.knowledge_base.loader import load_knowledge_base
from gastric_engine.pipeline.ingredients_to_chemicals import (
    build_bridge_prompt,
    map_ingredients_to_chemicals,
)


def test_prompt_lists_compound_vocabulary_from_kb():
    kb = load_knowledge_base()
    prompt = build_bridge_prompt(
        [{"name": "milk", "amount": "200 ml"}], kb
    )
    assert "lactose" in prompt
    assert "CO2_dissolved" in prompt
    assert "solid_volume_ml" in prompt
    assert "milk" in prompt


def test_mapping_keeps_known_compounds_and_reports_unknowns():
    kb = load_knowledge_base()

    def fake_generate(prompt, **kwargs):
        return {
            "chemicals": {
                "lactose": 9.6,
                "fat": 7.0,
                "made_up_key": 5,   # not in vocabulary -> dropped + reported
                "protein": 0,        # zero -> dropped
            },
            "meal_physical": {
                "solid_volume_ml": 0,
                "liquid_volume_ml": 200,
                "meal_mass_g": 205,
            },
            "unmapped": ["food coloring"],
        }

    result = map_ingredients_to_chemicals(
        [{"name": "milk", "amount": "200 ml"}], kb, generate=fake_generate
    )

    assert result["chemicals"] == {"lactose": 9.6, "fat": 7.0}
    assert result["meal_physical"]["liquid_volume_ml"] == 200
    assert "made_up_key" in result["unknown_compounds"]
    assert "food coloring" in result["unknown_compounds"]


def test_mapping_coerces_string_numbers_and_skips_bad_values():
    kb = load_knowledge_base()

    def fake_generate(prompt, **kwargs):
        return {
            "chemicals": {"fat": "12.5", "starch": "lots"},
            "meal_physical": {"solid_volume_ml": "300"},
        }

    result = map_ingredients_to_chemicals(
        [{"name": "fries", "amount": "1 serving"}], kb, generate=fake_generate
    )

    assert result["chemicals"]["fat"] == 12.5
    assert "starch" not in result["chemicals"]
    assert "starch" in result["unknown_compounds"]
    assert result["meal_physical"]["solid_volume_ml"] == 300.0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest gastric_engine/tests/test_ingredients_to_chemicals.py -v`
Expected: FAIL — `ModuleNotFoundError: gastric_engine.pipeline.ingredients_to_chemicals`.

- [ ] **Step 3: Write minimal implementation**

Create `gastric_engine/pipeline/ingredients_to_chemicals.py`:

```python
"""Stage 2: map an ingredient list onto the engine's compound vocabulary.

The vocabulary is read from the knowledge base at runtime — no food is ever
hard-coded here. Gemini proposes amounts; this module validates them.
"""

from __future__ import annotations

import json
from typing import Any, Callable

from gastric_engine.pipeline.gemini_client import generate_json

MEAL_PHYSICAL_KEYS = ("solid_volume_ml", "liquid_volume_ml", "meal_mass_g")


def build_bridge_prompt(ingredients: list[dict], kb) -> str:
    lines = []
    for key in sorted(kb.compound_keys):
        row = kb.compounds.get(key, {})
        desc = row.get("description") or row.get("_doc") or ""
        lines.append(f"- {key}: {desc}".rstrip())
    vocab = "\n".join(lines)
    ingredient_json = json.dumps(ingredients, ensure_ascii=False)
    return (
        "You convert a recipe's ingredients into a fixed set of physiological "
        "compounds for a gastric simulator. For the whole single-serving meal, "
        "estimate the TOTAL amount of each compound below. Units: grams for "
        "masses, mg for caffeine, 0-1 scale for acid_load / spice_capsaicin / "
        "durian_sulfur. Only use compounds from this list:\n"
        f"{vocab}\n\n"
        "Also estimate meal_physical: solid_volume_ml, liquid_volume_ml, "
        "meal_mass_g.\n\n"
        f"Ingredients:\n{ingredient_json}\n\n"
        "Respond strictly as raw JSON (no markdown) matching:\n"
        "{\n"
        '  "chemicals": {"<compound>": <number>, ...},\n'
        '  "meal_physical": {"solid_volume_ml": <n>, "liquid_volume_ml": <n>, '
        '"meal_mass_g": <n>},\n'
        '  "unmapped": ["<ingredient the list could not represent>", ...]\n'
        "}\n"
        "Omit compounds that are absent. Do not invent keys outside the list."
    )


def _as_positive_number(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if number > 0 else None


def map_ingredients_to_chemicals(
    ingredients: list[dict],
    kb,
    *,
    generate: Callable[..., Any] = generate_json,
) -> dict:
    prompt = build_bridge_prompt(ingredients, kb)
    raw = generate(prompt)

    raw_chemicals = raw.get("chemicals", {}) if isinstance(raw, dict) else {}
    raw_physical = raw.get("meal_physical", {}) if isinstance(raw, dict) else {}
    unmapped = list(raw.get("unmapped", []) or []) if isinstance(raw, dict) else []

    chemicals: dict[str, float] = {}
    unknown: list[str] = list(unmapped)
    for key, value in raw_chemicals.items():
        number = _as_positive_number(value)
        if key in kb.compound_keys and number is not None:
            chemicals[key] = number
        elif key not in kb.compound_keys:
            unknown.append(key)

    meal_physical: dict[str, float] = {}
    for key in MEAL_PHYSICAL_KEYS:
        number = _as_positive_number(raw_physical.get(key))
        if number is not None:
            meal_physical[key] = number

    return {
        "chemicals": chemicals,
        "meal_physical": meal_physical,
        "unknown_compounds": unknown,
    }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest gastric_engine/tests/test_ingredients_to_chemicals.py -v`
Expected: PASS (3 passed).

- [ ] **Step 5: Commit**

```bash
git add gastric_engine/pipeline/ingredients_to_chemicals.py gastric_engine/tests/test_ingredients_to_chemicals.py
git commit -m "feat: add ingredient->compound bridge (Stage 2)"
```

---

## Task 4: Image → ingredients stage

Ports the recipe notebook's logic into the repo. Accepts image bytes or a path,
normalizes to RGB, asks Gemini for the dish + granular ingredient list. The
Gemini call and image decoding are injectable for testing.

**Files:**
- Create: `gastric_engine/pipeline/image_to_ingredients.py`
- Test: `gastric_engine/tests/test_image_to_ingredients.py`

- [ ] **Step 1: Write the failing test**

Create `gastric_engine/tests/test_image_to_ingredients.py`:

```python
import pytest

from gastric_engine.pipeline.image_to_ingredients import (
    INGREDIENT_PROMPT,
    predict_food_and_ingredients,
)


def test_prompt_is_gi_focused():
    assert "gastrointestinal" in INGREDIENT_PROMPT.lower()
    assert "json" in INGREDIENT_PROMPT.lower()


def test_predict_returns_dish_and_ingredients_with_stubs():
    def fake_load_image(_image):
        return "IMG"

    def fake_generate(prompt, *, image=None, **kwargs):
        assert image == "IMG"
        return {
            "dish": "ramen",
            "ingredients": [{"name": "wheat noodles", "amount": "200 g"}],
        }

    result = predict_food_and_ingredients(
        b"fake-bytes", generate=fake_generate, load_image=fake_load_image
    )

    assert result["dish"] == "ramen"
    assert result["ingredients"][0]["name"] == "wheat noodles"


def test_predict_raises_on_missing_keys():
    def fake_generate(prompt, *, image=None, **kwargs):
        return {"unexpected": True}

    with pytest.raises(ValueError) as exc:
        predict_food_and_ingredients(
            b"x", generate=fake_generate, load_image=lambda _i: "IMG"
        )
    assert "ingredients" in str(exc.value)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest gastric_engine/tests/test_image_to_ingredients.py -v`
Expected: FAIL — `ModuleNotFoundError: gastric_engine.pipeline.image_to_ingredients`.

- [ ] **Step 3: Write minimal implementation**

Create `gastric_engine/pipeline/image_to_ingredients.py`:

```python
"""Stage 1: food image -> {dish, ingredients}. Ported from the recipe notebook."""

from __future__ import annotations

import io
from typing import Any, Callable

from gastric_engine.pipeline.gemini_client import generate_json

INGREDIENT_PROMPT = (
    "Analyze this food image. Identify the main dish and provide a standard, "
    "detailed single-serving recipe breakdown with realistic estimations of "
    "quantities and units. Because this data is used to predict "
    "gastrointestinal (GI) and stomach distress, you must be highly granular "
    "and include hidden or dissolved components like garlic, onion, cooking "
    "oils, dairy, or wheat if they are typically present in this dish style.\n\n"
    "You must respond strictly in JSON format matching this schema:\n"
    "{\n"
    '  "dish": "dish name",\n'
    '  "ingredients": [\n'
    '    {"name": "ingredient name", "amount": "quantity with unit"}\n'
    "  ]\n"
    "}\n"
    "Do not include markdown wrappers. Output raw JSON text only."
)


def _load_image(image: Any) -> Any:
    """Normalize bytes/path into an RGB PIL image (recipe-notebook behavior)."""
    from PIL import Image  # local import: only needed for real calls

    if isinstance(image, (bytes, bytearray)):
        raw = Image.open(io.BytesIO(image))
    else:
        raw = Image.open(image)
    return raw.convert("RGB")


def predict_food_and_ingredients(
    image: Any,
    *,
    generate: Callable[..., Any] = generate_json,
    load_image: Callable[[Any], Any] = _load_image,
) -> dict:
    img = load_image(image)
    result = generate(INGREDIENT_PROMPT, image=img)
    if not isinstance(result, dict) or "ingredients" not in result:
        raise ValueError(
            f"Image stage expected dish/ingredients JSON, got: {result!r}"
        )
    result.setdefault("dish", "unknown dish")
    return result
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest gastric_engine/tests/test_image_to_ingredients.py -v`
Expected: PASS (3 passed).

- [ ] **Step 5: Commit**

```bash
git add gastric_engine/pipeline/image_to_ingredients.py gastric_engine/tests/test_image_to_ingredients.py
git commit -m "feat: port image->ingredients stage from recipe branch"
```

---

## Task 5: Orchestrator

Chains both stages, then calls the existing `simulate_endpoint`. Merges the two
sources of `unknown_compounds` (bridge output + engine output). Returns the
simulation result enriched with `dish`, `ingredients`, and mapped `chemicals` so
the UI can show every stage.

**Files:**
- Create: `gastric_engine/pipeline/orchestrator.py`
- Test: `gastric_engine/tests/test_pipeline_orchestrator.py`

- [ ] **Step 1: Write the failing test**

Create `gastric_engine/tests/test_pipeline_orchestrator.py`:

```python
from gastric_engine.pipeline.orchestrator import analyze_meal


def test_orchestrator_chains_stages_into_simulation():
    def fake_image_stage(image):
        return {"dish": "fish and chips", "ingredients": [{"name": "cod", "amount": "150 g"}]}

    def fake_bridge_stage(ingredients):
        assert ingredients == [{"name": "cod", "amount": "150 g"}]
        return {
            "chemicals": {"fat": 30.0, "protein": 28.0},
            "meal_physical": {"solid_volume_ml": 400, "liquid_volume_ml": 100},
            "unknown_compounds": ["malt vinegar"],
        }

    result = analyze_meal(
        b"fake-image",
        clinical_profile={"reflux_gord": True},
        simulation_config={"duration_min": 30, "output_dt_min": 10},
        image_stage=fake_image_stage,
        bridge_stage=fake_bridge_stage,
    )

    assert result["dish"] == "fish and chips"
    assert result["ingredients"][0]["name"] == "cod"
    assert result["chemicals"] == {"fat": 30.0, "protein": 28.0}
    assert "malt vinegar" in result["unknown_compounds"]
    assert "summary" in result
    assert "symptom_curves" in result
    assert "mechanism_curves" in result
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest gastric_engine/tests/test_pipeline_orchestrator.py -v`
Expected: FAIL — `ModuleNotFoundError: gastric_engine.pipeline.orchestrator`.

- [ ] **Step 3: Write minimal implementation**

Create `gastric_engine/pipeline/orchestrator.py`:

```python
"""Run image -> ingredients -> chemicals -> simulation as one call."""

from __future__ import annotations

from typing import Any, Callable

from gastric_engine.api.routes import simulate_endpoint
from gastric_engine.knowledge_base.loader import load_knowledge_base
from gastric_engine.pipeline.image_to_ingredients import predict_food_and_ingredients
from gastric_engine.pipeline.ingredients_to_chemicals import map_ingredients_to_chemicals


def analyze_meal(
    image: Any,
    *,
    clinical_profile: dict | None = None,
    learned_physiology: dict | None = None,
    symptoms_reported: dict | None = None,
    simulation_config: dict | None = None,
    image_stage: Callable[[Any], dict] | None = None,
    bridge_stage: Callable[[list], dict] | None = None,
) -> dict:
    image_stage = image_stage or predict_food_and_ingredients
    if bridge_stage is None:
        kb = load_knowledge_base()
        bridge_stage = lambda ingredients: map_ingredients_to_chemicals(ingredients, kb)

    recipe = image_stage(image)
    bridge = bridge_stage(recipe.get("ingredients", []))

    result = simulate_endpoint(
        {
            "chemicals": bridge["chemicals"],
            "meal_physical": bridge["meal_physical"],
            "clinical_profile": clinical_profile or {},
            "learned_physiology": learned_physiology,
            "symptoms_reported": symptoms_reported,
            "simulation_config": simulation_config,
        }
    )

    merged_unknown = list(
        dict.fromkeys(
            [*result.get("unknown_compounds", []), *bridge.get("unknown_compounds", [])]
        )
    )
    result["unknown_compounds"] = merged_unknown
    if merged_unknown:
        result["summary"]["confidence"] = "low"

    result["dish"] = recipe.get("dish", "unknown dish")
    result["ingredients"] = recipe.get("ingredients", [])
    result["chemicals"] = bridge["chemicals"]
    result["meal_physical"] = bridge["meal_physical"]
    return result
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest gastric_engine/tests/test_pipeline_orchestrator.py -v`
Expected: PASS (1 passed).

- [ ] **Step 5: Run the whole suite to confirm no regressions**

Run: `pytest gastric_engine/tests/ -q`
Expected: all tests pass (existing + new).

- [ ] **Step 6: Commit**

```bash
git add gastric_engine/pipeline/orchestrator.py gastric_engine/tests/test_pipeline_orchestrator.py
git commit -m "feat: add pipeline orchestrator chaining stages to simulation"
```

---

## Task 6: API endpoints

Add the upload endpoint and serve the static page. The handler logic
(`analyze_image_endpoint`) is a plain function so it is testable without an
HTTP server, matching the existing `simulate_endpoint` pattern.

**Files:**
- Modify: `gastric_engine/api/routes.py`
- Test: `gastric_engine/tests/test_analyze_image_endpoint.py`

- [ ] **Step 1: Write the failing test**

Create `gastric_engine/tests/test_analyze_image_endpoint.py`:

```python
from gastric_engine.api import routes


def test_analyze_image_endpoint_uses_orchestrator(monkeypatch):
    def fake_analyze_meal(image, **kwargs):
        assert image == b"bytes"
        assert kwargs["clinical_profile"] == {"reflux_gord": True}
        return {"dish": "ramen", "summary": {"main_symptom": "bloating"}}

    monkeypatch.setattr(routes, "analyze_meal", fake_analyze_meal)

    result = routes.analyze_image_endpoint(
        b"bytes", clinical_profile={"reflux_gord": True}
    )
    assert result["dish"] == "ramen"
    assert result["summary"]["main_symptom"] == "bloating"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest gastric_engine/tests/test_analyze_image_endpoint.py -v`
Expected: FAIL — `AttributeError: module ... has no attribute 'analyze_image_endpoint'`.

- [ ] **Step 3: Modify `routes.py`**

Add these imports near the top of `gastric_engine/api/routes.py` (after the existing imports):

```python
from pathlib import Path

from gastric_engine.pipeline.orchestrator import analyze_meal
```

Add this handler after `simulate_endpoint` (before the `if app is not None:` block):

```python
def analyze_image_endpoint(
    image_bytes: bytes,
    *,
    clinical_profile: dict | None = None,
    simulation_config: dict | None = None,
) -> dict:
    return analyze_meal(
        image_bytes,
        clinical_profile=clinical_profile or {},
        simulation_config=simulation_config,
    )


STATIC_DIR = Path(__file__).resolve().parent / "static"
```

Replace the existing `if app is not None:` block with one that also wires the new
routes and static files:

```python
if app is not None:  # pragma: no cover
    import json as _json

    from fastapi import Form, UploadFile
    from fastapi.responses import FileResponse
    from fastapi.staticfiles import StaticFiles

    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

    @app.get("/health")
    def _health_route():
        return health()

    @app.post("/simulate")
    def _simulate_route(payload: dict):
        return simulate_endpoint(payload)

    @app.get("/")
    def _index_route():
        return FileResponse(str(STATIC_DIR / "index.html"))

    @app.post("/analyze-image")
    async def _analyze_image_route(
        image: UploadFile,
        clinical_profile: str = Form("{}"),
        simulation_config: str = Form("null"),
    ):
        return analyze_image_endpoint(
            await image.read(),
            clinical_profile=_json.loads(clinical_profile),
            simulation_config=_json.loads(simulation_config),
        )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest gastric_engine/tests/test_analyze_image_endpoint.py -v`
Expected: PASS (1 passed).

- [ ] **Step 5: Run the whole suite**

Run: `pytest gastric_engine/tests/ -q`
Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add gastric_engine/api/routes.py gastric_engine/tests/test_analyze_image_endpoint.py
git commit -m "feat: add /analyze-image endpoint and static page serving"
```

---

## Task 7: Visualization page

A single self-contained HTML page using Chart.js from CDN. Uploads an image or
picks a bundled sample, sends clinical flags, renders summary + symptom curves +
mechanism curves + detected dish/ingredients/chemicals + root-cause drivers.

**Files:**
- Create: `gastric_engine/api/static/index.html`

- [ ] **Step 1: Create the page**

Create `gastric_engine/api/static/index.html`:

```html
<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<title>TummyBuddy — Meal → Symptoms</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4"></script>
<style>
  body { font-family: system-ui, sans-serif; margin: 0; background: #faf7f2; color: #1f2933; }
  header { background: #b5651d; color: #fff; padding: 16px 24px; }
  main { max-width: 980px; margin: 0 auto; padding: 24px; }
  .card { background: #fff; border-radius: 12px; padding: 18px; margin-bottom: 20px; box-shadow: 0 1px 4px rgba(0,0,0,.08); }
  .row { display: flex; flex-wrap: wrap; gap: 12px; align-items: center; }
  .samples img { height: 64px; border-radius: 8px; cursor: pointer; border: 3px solid transparent; }
  .samples img.sel { border-color: #b5651d; }
  label.flag { margin-right: 14px; }
  button { background: #b5651d; color: #fff; border: 0; padding: 10px 18px; border-radius: 8px; font-size: 15px; cursor: pointer; }
  button:disabled { opacity: .5; cursor: default; }
  .summary { font-size: 18px; }
  .pill { display: inline-block; padding: 2px 10px; border-radius: 999px; color: #fff; font-size: 13px; }
  .risk-high { background: #c0392b; } .risk-medium { background: #d68910; } .risk-low { background: #27ae60; }
  table { border-collapse: collapse; width: 100%; }
  td, th { text-align: left; padding: 4px 8px; border-bottom: 1px solid #eee; font-size: 14px; }
  .muted { color: #6b7280; font-size: 13px; }
  canvas { max-height: 320px; }
</style>
</head>
<body>
<header><h1>TummyBuddy</h1><div class="muted" style="color:#ffe">Photo of a meal → predicted gut symptoms</div></header>
<main>
  <div class="card">
    <h3>1. Pick a meal</h3>
    <div class="row samples" id="samples">
      <img data-sample="/static/samples/ramen.jpg" src="/static/samples/ramen.jpg" alt="ramen" />
      <img data-sample="/static/samples/fish_and_chips.jpg" src="/static/samples/fish_and_chips.jpg" alt="fish and chips" />
      <img data-sample="/static/samples/tonkatsu_curry.jpg" src="/static/samples/tonkatsu_curry.jpg" alt="tonkatsu curry" />
    </div>
    <p class="muted">…or upload your own: <input type="file" id="file" accept="image/*" /></p>
  </div>

  <div class="card">
    <h3>2. Who is eating?</h3>
    <div id="flags">
      <label class="flag"><input type="checkbox" value="reflux_gord" /> Reflux / GORD</label>
      <label class="flag"><input type="checkbox" value="lactose_intolerance" /> Lactose intolerant</label>
      <label class="flag"><input type="checkbox" value="gastritis_history" /> Gastritis</label>
      <label class="flag"><input type="checkbox" value="ulcer_history" /> Ulcer history</label>
      <label class="flag"><input type="checkbox" value="nsaid_use" /> NSAID use</label>
    </div>
    <p><button id="go">Analyze meal</button> <span id="status" class="muted"></span></p>
  </div>

  <div id="results" style="display:none">
    <div class="card">
      <h3 id="dish"></h3>
      <div class="summary" id="summary"></div>
      <p class="muted" id="unknowns"></p>
    </div>
    <div class="card"><h3>Symptoms over time</h3><canvas id="symptomChart"></canvas></div>
    <div class="card"><h3>Why (mechanisms)</h3><canvas id="mechChart"></canvas></div>
    <div class="card"><h3>Root causes</h3><div id="causes"></div></div>
    <div class="card"><h3>Detected ingredients → chemicals</h3>
      <div class="row" style="align-items:flex-start">
        <div style="flex:1"><table id="ingredients"></table></div>
        <div style="flex:1"><table id="chemicals"></table></div>
      </div>
    </div>
  </div>
</main>
<script>
let selectedSample = null, symptomChart, mechChart;
const $ = (id) => document.getElementById(id);

document.querySelectorAll('#samples img').forEach((img) => {
  img.onclick = () => {
    document.querySelectorAll('#samples img').forEach((i) => i.classList.remove('sel'));
    img.classList.add('sel');
    selectedSample = img.dataset.sample;
    $('file').value = '';
  };
});

function clinicalProfile() {
  const profile = {};
  document.querySelectorAll('#flags input:checked').forEach((c) => { profile[c.value] = true; });
  return profile;
}

async function imageBlob() {
  const f = $('file').files[0];
  if (f) return f;
  if (selectedSample) return await (await fetch(selectedSample)).blob();
  return null;
}

$('go').onclick = async () => {
  const blob = await imageBlob();
  if (!blob) { $('status').textContent = 'Choose or upload an image first.'; return; }
  $('go').disabled = true; $('status').textContent = 'Asking Gemini and simulating…';
  const form = new FormData();
  form.append('image', blob, 'meal.jpg');
  form.append('clinical_profile', JSON.stringify(clinicalProfile()));
  form.append('simulation_config', JSON.stringify({ duration_min: 360, output_dt_min: 10 }));
  try {
    const res = await fetch('/analyze-image', { method: 'POST', body: form });
    if (!res.ok) throw new Error(await res.text());
    render(await res.json());
    $('status').textContent = '';
  } catch (e) {
    $('status').textContent = 'Error: ' + e.message;
  } finally {
    $('go').disabled = false;
  }
};

function render(data) {
  $('results').style.display = 'block';
  $('dish').textContent = '🍽️ ' + (data.dish || 'meal');
  const s = data.summary || {};
  $('summary').innerHTML =
    `Main symptom: <b>${s.main_symptom ?? '—'}</b> · ` +
    `<span class="pill risk-${s.risk_level || 'low'}">${(s.risk_level||'low').toUpperCase()}</span> · ` +
    `peak ~${s.peak_time_min ?? '?'} min · confidence: ${s.confidence ?? '—'}`;
  const unknown = data.unknown_compounds || [];
  $('unknowns').textContent = unknown.length ? 'Unmapped (lowers confidence): ' + unknown.join(', ') : '';

  const t = (data.symptom_curves || {}).time_min || [];
  drawLine('symptomChart', (c) => symptomChart = c, t, data.symptom_curves || {},
    ['reflux', 'bloating', 'diarrhea', 'upper_pain'], symptomChart);
  drawLine('mechChart', (c) => mechChart = c, t, data.mechanism_curves || {},
    ['gastric_pressure', 'fundus_pressure', 'gas_volume_ml', 'pH'], mechChart);

  const causes = data.root_causes || {};
  $('causes').innerHTML = Object.entries(causes).map(([sym, info]) => {
    const drivers = (info.drivers || []).map((d) =>
      `<li>${d.chemical} — ${(d.contribution*100).toFixed(0)}% <span class="muted">(${d.mechanism||''})</span></li>`).join('');
    return `<p><b>${sym}</b> (peak ~${info.peak_time_min ?? '?'} min)<ul>${drivers}</ul>` +
      `<span class="muted">${info.advice||''}</span></p>`;
  }).join('') || '<span class="muted">No dominant driver.</span>';

  $('ingredients').innerHTML = '<tr><th>Ingredient</th><th>Amount</th></tr>' +
    (data.ingredients || []).map((i) => `<tr><td>${i.name}</td><td>${i.amount||''}</td></tr>`).join('');
  $('chemicals').innerHTML = '<tr><th>Compound</th><th>Amount</th></tr>' +
    Object.entries(data.chemicals || {}).map(([k, v]) => `<tr><td>${k}</td><td>${v}</td></tr>`).join('');
}

const COLORS = ['#c0392b', '#2980b9', '#27ae60', '#8e44ad', '#d68910', '#16a085'];
function drawLine(canvasId, store, labels, curves, keys, existing) {
  if (existing) existing.destroy();
  const datasets = keys.filter((k) => Array.isArray(curves[k])).map((k, i) => ({
    label: k, data: curves[k], borderColor: COLORS[i % COLORS.length],
    backgroundColor: 'transparent', tension: 0.3, pointRadius: 0,
  }));
  store(new Chart($(canvasId), {
    type: 'line',
    data: { labels, datasets },
    options: { responsive: true, interaction: { mode: 'index', intersect: false },
      scales: { x: { title: { display: true, text: 'minutes' } } } },
  }));
}
</script>
</body>
</html>
```

- [ ] **Step 2: Commit**

```bash
git add gastric_engine/api/static/index.html
git commit -m "feat: add Chart.js visualization page"
```

---

## Task 8: Live end-to-end verification

Run the real pipeline with the Gemini key and confirm the page renders.

- [ ] **Step 1: Load the key and start the server**

Run:

```bash
cd /home/bozznyskrtt/TummyBuddy
set -a && . ./.env && set +a
uvicorn gastric_engine.main:app --port 8000
```

Expected: server starts, "Uvicorn running on http://127.0.0.1:8000".

- [ ] **Step 2: Smoke-test the endpoint with a sample image**

In another shell (with `.env` loaded the same way):

```bash
curl -s -X POST http://localhost:8000/analyze-image \
  -F "image=@gastric_engine/api/static/samples/ramen.jpg" \
  -F 'clinical_profile={"reflux_gord":true}' \
  -F 'simulation_config={"duration_min":360,"output_dt_min":10}' | python3 -m json.tool | head -40
```

Expected: JSON with `dish`, `ingredients`, `chemicals`, `summary`, `symptom_curves`.
If it returns an auth error, the pasted key is not a valid Gemini API key — swap
`GEMINI_API_KEY` in `.env` for an `AIzaSy…` key from aistudio.google.com.

- [ ] **Step 3: Open the page in a browser**

Visit `http://localhost:8000/`, pick the ramen sample, toggle "Reflux / GORD",
click **Analyze meal**, and confirm the summary, both charts, root causes, and
the ingredient/chemical tables populate. Toggle "Lactose intolerant" and
re-run to confirm the outcome changes.

- [ ] **Step 4: No commit needed** (verification only).

---

## Self-Review Notes

- **Spec coverage:** image stage (Task 4), bridge (Task 3), orchestrator (Task 5), API endpoints (Task 6), visualization (Task 7), requirements/samples (Task 1), Gemini wrapper for import-guarding + JSON parsing (Task 2), live run (Task 8). All spec components covered.
- **Meal volumes:** Gemini estimates them inside the bridge call (Task 3 prompt + `MEAL_PHYSICAL_KEYS`), per the approved decision.
- **`foods-never-hard-coded`:** bridge prompt is built from `kb.compound_keys`; `core/` untouched.
- **Type consistency:** `generate`/`generate_json` signature `(prompt, *, image=None, model=None)` is consistent across `gemini_client`, `image_to_ingredients`, and `ingredients_to_chemicals`; `analyze_meal` injection points (`image_stage`, `bridge_stage`) match the orchestrator test.
