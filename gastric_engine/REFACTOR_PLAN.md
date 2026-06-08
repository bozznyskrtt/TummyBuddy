# Refactor Plan — Open-World, Learning-Based Gastric Engine

> **Audience:** an implementing agent (or human) executing this refactor phase by phase.
> **Read first:** `ARCHITECTURE.md` (current design). This plan *evolves* that design;
> it does not throw it away. Every phase keeps the existing 10 acceptance tests green.
>
> **Goal of this refactor:** remove the last rule-based smell (compounds keyed by *name*),
> make the engine **open-world** (any substance, known or not), and push it
> **as learning-based as possible** — *without* sacrificing the physics-grounded "why".

---

## 0. The governing idea: grey-box, not black-box

```
PHYSICS  = the backbone   → deterministic, explainable, works with zero data
LEARNING = layered on top → corrects & personalizes WHERE data exists,
                            degrades gracefully back to physics where it doesn't
LLM/AGENT = knowledge oracle only → fills substance KNOWLEDGE; NEVER touches the ODE numbers
```

**Three hard rules that must survive every phase:**

1. **The simulation stays deterministic physics.** The LLM/agent only ever writes into the
   knowledge base (Pillar 2). It must never be called inside the timestep loop, and never
   produce a symptom curve directly.
2. **Open-world by construction.** A substance the engine has never seen must still flow
   through the physics — via a *property vector*, not a name match. No more silent
   `unknown_compounds: [ignored]`.
3. **Everything degrades gracefully.** No chem DB? Use the LLM estimate. No LLM? Use a
   neutral vector + low confidence. No personal data? Use population physics. The engine
   never crashes or refuses; it lowers `confidence` instead.

---

## 1. What changes, in one diagram

```
                         BEFORE (closed-world, rule-based)
chemicals ──▶ compounds.json[name].physical_effects[law] ──▶ physics dispatch on law strings
                         (unknown name → ignored)

                         AFTER (open-world, property-based)
chemicals ──▶ known?  yes ─▶ cached property vector ─────────┐
                      no  ─▶ characterizer (stub→agent)      │
                              → property vector + confidence ─┤
                              → cache  (knowledge accumulates)│
                                                              ▼
                                          GENERIC PHYSICS acting on the property vector
                                          (acid_load→pH, osmotic→osmolality, ... )
                                                              │
                              personal physiology (Bayesian) ◀┤  learning surface 2
                              calibration fit (from outcomes) ◀┘  learning surface 3
```

---

## 2. Target folder structure (before → after)

```
core/            engine, state, physics, biochemistry, intestine, symptoms,
                 counterfactual, output_builder            (unchanged set; physics rewritten)
knowledge_base/  property_schema.json     ← NEW: the canonical property dimensions
                 compounds.json           ← MIGRATED: each compound carries `properties`
                 reactions.json, interactions.json, physiology_defaults.json, loader.py
characterization/                          ← NEW PACKAGE (the agentic Flavor-B layer)
    __init__.py
    characterizer.py   # characterize(substance) -> CharacterizationResult
    tools.py           # retrieval tools (PubChem/FooDB) — interface now, impl in Phase 4
    validation.py      # clamp to property_schema ranges, attach per-field confidence
    cache.py           # persistent store of characterized substances (JSON file)
physiology/      profile_builder.py, learning.py           (strengthened in Phase 5)
learning/                                   ← NEW PACKAGE (learning surface 3)
    __init__.py
    calibration_fit.py # fit calibration constants from logged meal→outcome data
utils/           kinetics, calibration, parsing            (calibration becomes fittable)
```

**Removed:** the per-compound `physical_effects`/`law` declarations and the `law`-dispatch
ladder in `physics.py`. They are replaced by property vectors + generic physics functions.

---

## 3. The property vector (the heart of the refactor)

Every `law` in today's `physics.py` is a hidden property dimension. Make them explicit.
`knowledge_base/property_schema.json` defines the canonical dimensions, valid ranges, and
which physics function consumes each:

| Property dimension | Range | Replaces today's `law` | Physics target |
|---|---|---|---|
| `acid_load` | 0–1 | `acidify` | lowers `pH` |
| `buffering` | 0–1 | `buffering` | raises `buffering_capacity` |
| `osmotic_coeff` | 0–1 | `osmotic` | raises `osmolality` |
| `carbonation` | 0–1 | `henry_release` | gas release → `gas_volume_ml` |
| `fat_emptying` | 0–1 | `cck_feedback` | raises `fat_brake` (slows emptying) |
| `les_relaxant` | 0–1 | `les_relaxation` | raises `fundus_pressure` |
| `acid_secretagogue` | 0–1 | `acid_stimulation` | raises `acid_secretion_rate` |
| `irritant_potential` | 0–1 | `irritation` | raises `irritation` |
| `fermentability` | 0–1 | `if_undigested.gas_yield` | intestinal gas/osmolality |
| `bulk` | 0–1 | `bulk` | solid volume contribution |
| `enzyme_targets` | map | `reactions` list | biochemistry substrate routing |

Example migrated compound row:

```jsonc
"lactose": {
  "unit": "g",
  "properties": {
    "osmotic_coeff": 0.9, "fermentability": 0.8,
    "acid_load": 0.0, "buffering": 0.0, "carbonation": 0.0,
    "fat_emptying": 0.0, "les_relaxant": 0.0, "acid_secretagogue": 0.0,
    "irritant_potential": 0.0, "bulk": 0.0,
    "enzyme_targets": { "lactase": "substrate" }
  },
  "source": "seed", "confidence": 1.0
}
```

> The named registry now just *caches* property vectors for common foods. The engine reads
> `properties`, never the compound name.

---

## 4. Phased execution

Each phase: **goal → files → concrete changes → acceptance → guardrail.** Do not start
phase N+1 until phase N's acceptance passes AND the original 10 tests are still green.

### Phase 0 — Lock current behavior (safety net)
- **Goal:** capture today's numeric output so the refactor can prove it didn't break physics.
- **Files:** `tests/test_regression_snapshot.py` (new).
- **Do:** run the Coke + durian + milkshake scenarios, save the resulting symptom &
  mechanism curves to a fixture; assert future runs match within a tolerance (e.g. 1e-6
  pre-refactor, then a documented tolerance after the physics rewrite).
- **Acceptance:** snapshot test passes against current code.

### Phase 1 — Property schema + migrate compounds.json (non-breaking)
- **Goal:** introduce property vectors *alongside* the existing fields.
- **Files:** `knowledge_base/property_schema.json` (new); `knowledge_base/compounds.json`
  (add `properties` to every compound using the §3 mapping); `knowledge_base/loader.py`
  (load the schema; expose `kb.property_schema`).
- **Do:** keep the old `physical_effects` keys in place for now (dual-support) so nothing
  breaks. Add a loader validation that every `properties` block conforms to the schema.
- **Acceptance:** all compounds have schema-valid `properties`; 10 tests still green.

### Phase 2 — Rewrite physics to consume property vectors
- **Goal:** physics acts on properties, not `law` strings. This is the biggest diff.
- **Files:** `core/physics.py` (rewrite `apply_physical_effect` → `apply_properties`);
  `core/engine.py` `_apply_compound_effects` (iterate compounds, read `properties`);
  `core/intestine.py` (`ferment_in_intestine` reads `fermentability` not `if_undigested`).
- **Do:** replace the `if law == ...` ladder with generic functions, one per property
  dimension, each a pure function of `(state, property_value, amount, physiology)`. Delete
  the `law` dispatch once parity is shown. Move the hard-coded per-compound normalizers
  (`_normalized_amount` for caffeine/ethanol) into a `potency` field on the property vector.
- **Acceptance:** snapshot test (Phase 0) matches within documented tolerance; 10 tests green.
- **Guardrail:** do this behind the snapshot test; if a curve shifts, it must be an
  explainable, intended consequence of removing a hack — document it.

### Phase 3 — Open-world seam + characterizer STUB (no LLM yet)
- **Goal:** make the engine open-world *before* any LLM exists.
- **Files:** `characterization/characterizer.py`, `validation.py`, `cache.py` (new);
  `core/engine.py` (on unknown substance → characterize → inject vector); remove the
  silent-ignore in `simulate_core`'s `clean_chemicals` filter.
- **Interface (freeze this contract now):**
  ```python
  # characterization/characterizer.py
  @dataclass
  class CharacterizationResult:
      substance: str
      properties: dict          # conforms to property_schema.json
      confidence: float         # 0–1, per overall vector
      source: str               # "seed" | "cache" | "stub" | "agent"

  def characterize(substance: str, *, kb, cache) -> CharacterizationResult: ...
  ```
  The **stub** returns a neutral vector (all ~0.1) with `confidence=0.2, source="stub"`,
  caches it, and logs it for later human/agent review.
- **Do:** propagate per-substance confidence into the response `confidence` (lower it when
  any active substance is stub/agent-derived). Cache writes accumulate to a JSON file —
  this is **learning surface 1** (knowledge grows with use).
- **Acceptance (new test):** feeding an unseen substance (e.g. `"yuzu": 5`) no longer lands
  in `unknown_compounds`; it gets a property vector, affects the sim, and lowers `confidence`.

### Phase 4 — Real agentic characterizer (DEFERRED: "API later")
- **Goal:** replace the stub with the tool-using RAG agent. **Interface unchanged**, so this
  is a clean drop-in — the engine does not change.
- **Files:** `characterization/tools.py` (PubChem/FooDB retrieval), `characterizer.py`
  (agent loop), config for the model/provider.
- **Agent loop (spec only here; implement when wiring the API):**
  1. retrieve the substance from chem DBs (tool calls) → real physicochemical data
  2. reason over retrieved facts → fill the property vector
  3. self-check unsupported fields → lower their confidence
  4. `validation.py` clamps to schema ranges → cache as `source="agent"`
- **Hard rules:** runs **once per novel substance, outside the loop**; output cached for
  determinism; clamped to physical ranges; confidence propagated. **Never** called per
  timestep, **never** emits curves.
- **Acceptance:** with the agent enabled, a novel substance yields a grounded vector with
  citations in `metadata`; with it disabled, the Phase-3 stub still works. Same cached input
  → identical curves (determinism check).

### Phase 5 — Learning surfaces 2 & 3
- **Goal:** push learning as far as the available data honestly allows.
- **Surface 2 — personal physiology (strengthen existing):** `physiology/learning.py` already
  does a Bayesian update for `lactase_Vmax`. Generalize it to all enzyme levels and symptom
  thresholds, each as `(mean, variance)`, updated from the user's meal→symptom logs. Feed the
  posterior back in via the existing `learned_physiology` overlay in `profile_builder.py`.
- **Surface 3 — calibration fit (new):** `learning/calibration_fit.py`. Turn the hand-tuned
  constants in `utils/calibration.py` (`SYMPTOM_GAIN`, gas/osmotic coefficients, the bloating
  `0.3` weight, counterfactual `MATERIAL_DROP`) into parameters **fit from data**, while
  leaving the physics equations themselves untouched.
  - **The method:** treat each constant as a tunable parameter; run an optimizer
    (`scipy.optimize`) that wraps the existing engine and minimizes the error between the
    engine's predicted symptom curves and logged meal→outcome reports. The result is the
    same engine, professionally calibrated instead of guessed.
  - **Guardrails:** every fitted constant is clamped to a physically sensible range; if the
    log set is below a minimum sample count, the fit **no-ops back to the seed defaults**
    (never overfit a handful of meals). Physics structure is unchanged, so the "why" /
    counterfactual explanation stays fully intact.
- **Acceptance:** (2) logging 3 dairy→diarrhea meals lowers posterior `lactase_Vmax` mean and
  variance, and the next prediction's lactose risk rises. (3) fitting on a synthetic outcome
  set reduces curve error vs the seed constants and stays within the clamped ranges, with no
  regression on the 10 tests; below the minimum sample count the fit returns the defaults.

---

## 5. Cross-cutting requirements

- **Confidence propagation:** `build_output` must lower `confidence` when (a) any active
  substance is stub/agent-derived, or (b) personal physiology variance is high. Surface the
  reason in `metadata` (e.g. `"low_confidence_substances": ["yuzu"]`).
- **Determinism & caching:** the characterizer is memoized to `characterization/cache.py`'s
  JSON store keyed by substance. Same meal must always yield the same curves.
- **Tests are the contract:** the original 10 acceptance tests must stay green through every
  phase. New tests are added per phase, never deletions of old guarantees.
- **No LLM in the loop:** a lint/review check — `grep` the timestep loop and physics for any
  import from `characterization/` executed per step. There must be none.

---

## 6. Risks & guardrails (read before Phase 4)

| Risk | Guardrail |
|---|---|
| LLM hallucinates property values | Prefer chem-DB retrieval over generation; clamp to schema ranges; attach low confidence |
| Non-reproducible demos | Characterize once, cache, key by substance; never call the agent in the loop |
| Learning overfits sparse data | Bayesian priors + variance; calibration fit needs a minimum sample count or it no-ops to defaults |
| Refactor silently changes physics | Phase 0 snapshot test gates Phase 2; any change must be explained |
| "Learning" erodes the "why" | Physics stays the backbone; learning only **re-fits physical constants**, never replaces the explainable core |

---

## 7. Definition of done

1. An **unseen substance** flows through the physics (open-world) and only lowers
   `confidence` — never silently ignored.
2. `compounds.json` is **property vectors**; `physics.py` has **no `law`/name dispatch**.
3. The **characterizer seam** exists with a working stub; the real agent is a drop-in
   behind the frozen interface (Phase 4, API-later).
4. **Three learning surfaces** are live: knowledge cache grows with use; personal physiology
   is Bayesian; calibration constants are fit from data.
5. The original **10 acceptance tests still pass**, plus the new open-world, determinism,
   and learning tests.
6. The **durian+beer test still holds** (interactions remain data), and the **"why"**
   (counterfactual explanation) is unchanged — proving learning did not turn it into a
   black box.

---

## 8. Out of scope (future upgrade, do NOT build now)

A heavier learning option exists — a **learned residual model** that predicts the gap
between the physics curves and real outcomes and adds it back. It is intentionally **not**
part of this plan because it (a) needs hundreds–thousands of labeled meals we do not have,
and (b) introduces a black-box term that partially erodes the explainable "why".

Revisit only after Surface 3's calibration fit is live **and** a substantial outcome-log
dataset has been collected. Until then, Surface 3 (re-fitting physical constants) is the
ceiling — it is fully explainable and works with the small data we actually have.
