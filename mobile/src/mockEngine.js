const meals = {
  ramen: {
    name: "Spicy ramen bowl",
    shortName: "Ramen",
    photoTone: "#F97316",
    volume: "610 ml",
    tags: ["capsaicin", "fat", "noodles", "unknown yuzu oil"],
    chemicals: [
      { name: "irritant_potential", amount: "0.62", color: "#E11D48" },
      { name: "fat_emptying", amount: "0.44", color: "#F59E0B" },
      { name: "osmotic_coeff", amount: "0.31", color: "#0F766E" },
      { name: "yuzu_oil", amount: "characterized", color: "#2563EB" },
    ],
  },
  curry: {
    name: "Tonkatsu curry",
    shortName: "Curry",
    photoTone: "#B45309",
    volume: "730 ml",
    tags: ["fat", "bulk", "starch", "spice"],
    chemicals: [
      { name: "fat_emptying", amount: "0.71", color: "#F59E0B" },
      { name: "bulk", amount: "0.52", color: "#7C3AED" },
      { name: "acid_secretagogue", amount: "0.29", color: "#E11D48" },
    ],
  },
  soda: {
    name: "Burger + orange soda",
    shortName: "Soda",
    photoTone: "#FB923C",
    volume: "980 ml",
    tags: ["CO2", "fat", "acid load", "sugar"],
    chemicals: [
      { name: "carbonation", amount: "0.86", color: "#2563EB" },
      { name: "fat_emptying", amount: "0.66", color: "#F59E0B" },
      { name: "acid_load", amount: "0.38", color: "#E11D48" },
      { name: "osmotic_coeff", amount: "0.47", color: "#0F766E" },
    ],
  },
};

const simulations = {
  ramen: {
    confidence: {
      level: "medium",
      score: 0.68,
      reason: "One open-world ingredient was characterized with a low-confidence neutral vector.",
    },
    openWorld: {
      substances: [{ name: "yuzu oil", source: "stub", confidence: 0.2 }],
    },
    symptoms: {
      reflux: curve([0.08, 0.22, 0.48, 0.43, 0.27, 0.16]),
      bloating: curve([0.05, 0.18, 0.34, 0.52, 0.45, 0.31]),
      pain: curve([0.09, 0.26, 0.44, 0.39, 0.25, 0.14]),
    },
    timeline: {
      physical: {
        gastricPressure: curve([0.12, 0.34, 0.62, 0.55, 0.37, 0.19]),
        gasVolume: curve([0.08, 0.21, 0.34, 0.31, 0.24, 0.14]),
        stomachPH: curve([0.58, 0.42, 0.33, 0.39, 0.48, 0.55]),
      },
      reactions: {
        spiceIrritation: curve([0.1, 0.36, 0.68, 0.58, 0.39, 0.2]),
        starchBreakdown: curve([0.92, 0.72, 0.48, 0.31, 0.2, 0.12]),
        yuzuCharacterization: curve([0.2, 0.2, 0.2, 0.2, 0.2, 0.2]),
        lactoseRemaining: curve([0.0, 0.0, 0.0, 0.0, 0.0, 0.0]),
      },
    },
    rootCauses: [
      { label: "Spice irritation", impact: 46, color: "#E11D48" },
      { label: "Delayed emptying", impact: 31, color: "#F59E0B" },
      { label: "Yuzu uncertainty", impact: 15, color: "#2563EB" },
    ],
  },
  curry: {
    confidence: {
      level: "high",
      score: 0.82,
      reason: "All active compounds are represented by seeded property vectors.",
    },
    openWorld: { substances: [] },
    symptoms: {
      reflux: curve([0.06, 0.14, 0.21, 0.26, 0.19, 0.12]),
      bloating: curve([0.07, 0.18, 0.37, 0.63, 0.7, 0.56]),
      pain: curve([0.04, 0.13, 0.28, 0.35, 0.31, 0.22]),
    },
    timeline: {
      physical: {
        gastricPressure: curve([0.1, 0.29, 0.48, 0.69, 0.72, 0.51]),
        gasVolume: curve([0.06, 0.1, 0.16, 0.22, 0.24, 0.2]),
        stomachPH: curve([0.6, 0.51, 0.43, 0.4, 0.46, 0.53]),
      },
      reactions: {
        fatBrakeSignal: curve([0.12, 0.44, 0.74, 0.82, 0.67, 0.38]),
        starchBreakdown: curve([0.95, 0.78, 0.57, 0.34, 0.18, 0.08]),
        spiceIrritation: curve([0.06, 0.18, 0.32, 0.28, 0.18, 0.1]),
        lactoseRemaining: curve([0.0, 0.0, 0.0, 0.0, 0.0, 0.0]),
      },
    },
    rootCauses: [
      { label: "Fat brake", impact: 54, color: "#F59E0B" },
      { label: "Meal bulk", impact: 27, color: "#7C3AED" },
      { label: "Spice load", impact: 11, color: "#E11D48" },
    ],
  },
  soda: {
    confidence: {
      level: "high",
      score: 0.79,
      reason: "Seeded carbonation and fat properties explain most of the response.",
    },
    openWorld: { substances: [] },
    symptoms: {
      reflux: curve([0.12, 0.51, 0.76, 0.58, 0.34, 0.17]),
      bloating: curve([0.11, 0.33, 0.55, 0.61, 0.5, 0.29]),
      pain: curve([0.05, 0.16, 0.28, 0.25, 0.17, 0.09]),
    },
    timeline: {
      physical: {
        gastricPressure: curve([0.18, 0.58, 0.86, 0.62, 0.34, 0.17]),
        gasVolume: curve([0.22, 0.78, 0.91, 0.57, 0.29, 0.13]),
        stomachPH: curve([0.56, 0.38, 0.29, 0.35, 0.45, 0.54]),
      },
      reactions: {
        co2Release: curve([0.12, 0.7, 0.86, 0.48, 0.22, 0.08]),
        fatBrakeSignal: curve([0.1, 0.32, 0.58, 0.66, 0.5, 0.24]),
        sugarOsmoticLoad: curve([0.18, 0.44, 0.63, 0.59, 0.4, 0.2]),
        lactoseRemaining: curve([0.0, 0.0, 0.0, 0.0, 0.0, 0.0]),
      },
    },
    rootCauses: [
      { label: "CO2 release", impact: 61, color: "#2563EB" },
      { label: "Fundus pressure", impact: 24, color: "#F97316" },
      { label: "Fat brake", impact: 9, color: "#F59E0B" },
    ],
  },
};

function isKnownMeal(mealId) {
  return Boolean(mealId) && Object.prototype.hasOwnProperty.call(meals, mealId);
}

function buildMockSimulation(mealId) {
  // The mock only knows the seeded sample meals. An imported photo is NOT one of
  // them, so return null rather than silently pretending it is ramen.
  if (!isKnownMeal(mealId)) {
    return null;
  }
  return {
    mealId,
    meal: meals[mealId],
    ...simulations[mealId],
  };
}

function curve(values) {
  const minutes = [0, 30, 60, 120, 180, 240];
  return values.map((value, index) => ({ minute: minutes[index], value }));
}

module.exports = { buildMockSimulation, isKnownMeal, meals };
