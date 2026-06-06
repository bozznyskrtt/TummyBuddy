# Engine Input Contract (Stage 2 → Gastric Engine)

> **Purpose.** The gastric engine speaks in **compounds**. The upstream
> "ingredient → chemicals" stage MUST emit exactly these compound keys.
> This file is the interface your teammate codes against. **The engine's
> `knowledge_base/compounds.json` is the authoritative vocabulary — this doc
> mirrors it for the upstream team.**

---

## 1. Why a fixed vocabulary

A real food has hundreds of chemicals. The engine only cares about the ~15 that drive
gut mechanics (gas, acid, fat, fermentable carbs, irritants, enzyme substrates). Stage 2's
job is **not** to produce a full chemistry dump — it is to **map detected ingredients onto
this fixed compound vocabulary**. Anything outside the vocabulary is ignored by the engine
(and should be flagged as `unknown_compounds` for the uncertainty estimate).

---

## 2. The canonical compound vocabulary

| Compound key | Unit | Meaning / drives |
|---|---|---|
| `protein` | g | pepsin substrate → peptides |
| `fat` | g | slows gastric emptying (CCK feedback) |
| `starch` | g | amylase substrate → maltose |
| `lactose` | g | lactase substrate; if undigested → osmotic + fermentation |
| `FODMAP` | g | fermentable carbs → intestinal gas/cramping |
| `fiber` | g | bulk; modulates emptying |
| `caffeine` | mg | stimulates acid, relaxes LES |
| `ethanol` | g | ADH/ALDH substrate; relaxes LES; mucosal irritation |
| `CO2_dissolved` | g | outgassing → gas volume → pressure → reflux |
| `acid_load` | 0–1 | intrinsic acidity of the meal |
| `spice_capsaicin` | 0–1 | mucosal irritant |
| `durian_sulfur` | 0–1 | interaction trigger (ALDH inhibition with ethanol) |

> Extend this table **only** by first adding the compound to
> `knowledge_base/compounds.json`. Never add a key the engine doesn't know.

---

## 3. Request schema — `POST /simulate`

```jsonc
{
  "chemicals": {                 // ← from Stage 2 (the vocabulary above)
    "protein": 42,
    "fat": 55,
    "starch": 60,
    "lactose": 18,
    "FODMAP": 4,
    "caffeine": 60,
    "ethanol": 0,
    "CO2_dissolved": 2.1,
    "acid_load": 0.75,
    "spice_capsaicin": 0.15,
    "durian_sulfur": 0
  },

  "meal_physical": {             // bulk/volume, also from Stage 2
    "solid_volume_ml": 650,
    "liquid_volume_ml": 700,
    "meal_mass_g": 950
  },

  "clinical_profile": {          // the user's data (engine's Pillar 3 input)
    "reflux_gord": true,
    "gastritis_history": true,
    "ulcer_history": false,
    "lactose_intolerance": true,
    "nsaid_use": false,
    "h_pylori_history": false
  },

  "learned_physiology": {        // OPTIONAL: from the Bayesian learning loop
    "enzyme_levels": { "lactase_Vmax": 0.15 },
    "symptom_thresholds": { "reflux_pressure_threshold": 0.68 }
  },

  "symptoms_reported": {         // OPTIONAL: current symptoms for safety flags
    "blood_in_vomit": false,
    "black_stool": false
  },

  "simulation_config": {
    "duration_min": 360,         // 6h so intestinal symptoms are captured
    "output_dt_min": 10
  }
}
```

**Required:** `chemicals`, `meal_physical`, `clinical_profile`.
**Optional:** `learned_physiology`, `symptoms_reported`, `simulation_config` (sensible
defaults applied if absent).

---

## 4. Response schema

```jsonc
{
  "summary": {
    "main_symptom": "reflux",
    "risk_level": "high",
    "peak_time_min": 22,
    "confidence": "medium"          // lowered by unknown_compounds / sparse history
  },

  "symptom_curves": {               // each is a probability over time
    "time_min":  [0, 10, 20, 30, ...],
    "reflux":    [0.10, 0.45, 0.91, 0.84, ...],
    "bloating":  [0.05, 0.20, 0.40, 0.55, ...],
    "diarrhea":  [0.00, 0.00, 0.05, 0.12, ...],   // later-onset, from intestine
    "upper_pain":[0.10, 0.22, 0.38, ...]
  },

  "mechanism_curves": {             // the physical "why", for visualization
    "gas_volume_ml":   [...],
    "gastric_pressure":[...],
    "fundus_pressure": [...],
    "pH":              [...],
    "lactose_remaining_g": [...],
    "intestine_gas_ml":[...]
  },

  "root_causes": {                  // counterfactual attribution (§7.2 in ARCHITECTURE)
    "reflux": {
      "peak_time_min": 22,
      "drivers": [
        {"chemical": "CO2_dissolved", "contribution": 0.52,
         "mechanism": "carbonation outgassing raised fundus pressure"},
        {"chemical": "fat",           "contribution": 0.28,
         "mechanism": "delayed emptying kept the stomach full and pressurized"},
        {"chemical": "caffeine",      "contribution": 0.20,
         "mechanism": "LES relaxation"}
      ],
      "advice": "Skipping the carbonated drink would lower peak reflux ~41%."
    }
  },

  "unknown_compounds": [],          // ingredients Stage 2 couldn't map → uncertainty
  "safety_flags": []                // red flags from symptoms_reported
}
```

---

## 5. Contract rules (for the upstream team)

1. **Use the exact keys** in §2. `fat`, not `fat_g`. `CO2_dissolved`, not `co2`.
2. **Omit or zero** compounds not present; do not invent keys.
3. **Map, don't dump.** Convert ingredients to this vocabulary; drop everything else.
4. Report anything you couldn't map in your own pipeline so the engine can mark
   `unknown_compounds` and lower confidence rather than silently ignoring it.
5. The **authoritative** list is `knowledge_base/compounds.json`. If you need a new
   compound, request it be added there first.
