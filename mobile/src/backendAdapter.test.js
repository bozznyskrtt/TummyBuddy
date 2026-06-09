const assert = require("assert");
const { adaptSimulation } = require("./backendAdapter");

// Real /analyze-image response captured from the engine (fish & chips, reflux).
const sample = require("./__fixtures__/analyze_sample.json");

const sim = adaptSimulation(sample);

// Meal identity comes from the Gemini vision stage, not a hardcoded sample.
assert.equal(sim.meal.name, "Fish and chips");
assert.ok(sim.meal.chemicals.length > 0, "chemicals should be listed");
assert.ok(/ml$/.test(sim.meal.volume), "volume should be formatted with ml");

// Symptom curves are downsampled to the 6-point UI grid and renamed for the UI.
assert.equal(sim.symptoms.reflux.length, 6);
assert.ok(sim.symptoms.pain, "upper_pain must be mapped to 'pain'");
assert.ok(
  sim.symptoms.reflux.some((p) => p.value > 0.8),
  "strong CO2 meal should show a high reflux peak"
);

// Physical timeline normalized to 0-1 for the bar charts.
assert.equal(sim.timeline.physical.gastricPressure.length, 6);
assert.ok(
  sim.timeline.physical.gastricPressure.every((p) => p.value >= 0 && p.value <= 1),
  "normalized curve must stay within 0-1"
);
assert.ok(
  sim.timeline.physical.gasVolume.some((p) => typeof p.rawValue === "number"),
  "physical curves should retain raw values for unit labels"
);

const reactionUnits = adaptSimulation({
  summary: { confidence: "medium" },
  symptom_curves: { time_min: [0, 30], reflux: [0, 0], bloating: [0, 0], diarrhea: [0, 0], upper_pain: [0, 0] },
  mechanism_curves: {
    time_min: [0, 30],
    gastric_pressure: [0.03, 0.03],
    gas_volume_ml: [20, 20],
    pH: [2.8, 2.8],
    acetaldehyde_g: [0, 1.46],
  },
});
assert.ok(
  reactionUnits.timeline.reactions.acetaldehyde.every((p) => typeof p.rawValue === "undefined"),
  "reaction curves should stay normalized display signals, not raw units"
);

const baselineGas = adaptSimulation({
  summary: { confidence: "medium" },
  symptom_curves: { time_min: [0, 30], reflux: [0, 0], bloating: [0, 0], diarrhea: [0, 0], upper_pain: [0, 0] },
  mechanism_curves: {
    time_min: [0, 30],
    gastric_pressure: [0.03, 0.03],
    gas_volume_ml: [20, 20],
    pH: [2.8, 2.8],
  },
});
assert.ok(
  baselineGas.timeline.physical.gasVolume.every((p) => p.value < 0.1),
  "baseline 20 ml gas should not render as a max-height normalized bar"
);

// Root causes come from the backend counterfactual, ranked, as percentages.
assert.ok(sim.rootCauses.length > 0, "should surface at least one root cause");
assert.ok(
  sim.rootCauses.every((c) => typeof c.impact === "number"),
  "impacts must be numeric percentages"
);

// Unknown ingredient lowers confidence and shows up in the open-world list.
assert.equal(sim.confidence.level, "low");
assert.ok(sim.openWorld.substances.length >= 1, "unknown compound should be surfaced");

// A null/garbage response must not throw.
assert.equal(adaptSimulation(null), null);
assert.equal(adaptSimulation(undefined), null);

console.log("backendAdapter tests passed");
