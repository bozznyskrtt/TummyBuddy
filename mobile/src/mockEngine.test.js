const assert = require("assert");
const { buildMockSimulation, isKnownMeal } = require("./mockEngine");

// An imported photo is not a recognized sample. The mock must NOT silently
// pretend it is ramen — that is the bug where fish & chips showed "Spicy ramen".
assert.equal(isKnownMeal("ramen"), true);
assert.equal(isKnownMeal("fish-and-chips"), false);
assert.equal(isKnownMeal(null), false);
assert.equal(buildMockSimulation("fish-and-chips"), null, "unknown meals must not map to ramen");
assert.equal(buildMockSimulation(null), null, "no selected meal must not map to ramen");

const result = buildMockSimulation("ramen");

assert.equal(result.meal.name, "Spicy ramen bowl");
assert.equal(result.confidence.level, "medium");
assert.equal(result.openWorld.substances[0].source, "stub");
assert.ok(result.symptoms.reflux.some((point) => point.value > 0.4));
assert.equal(result.timeline.physical.gastricPressure.length, 6);
assert.equal(result.timeline.reactions.lactoseRemaining.length, 6);
assert.ok(result.timeline.physical.gastricPressure[2].value > result.timeline.physical.gastricPressure[0].value);
assert.ok(result.timeline.reactions.spiceIrritation[2].value > result.timeline.reactions.spiceIrritation[0].value);
assert.ok(result.rootCauses[0].impact > result.rootCauses[1].impact);

console.log("mockEngine tests passed");
