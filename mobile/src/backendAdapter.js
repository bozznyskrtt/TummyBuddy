// Maps a /analyze-image backend response onto the shape the UI screens consume
// (the same shape buildMockSimulation produces). Kept pure and dependency-free
// so it can be unit-tested under plain `node`.

const PALETTE = ["#E11D48", "#F59E0B", "#0F766E", "#2563EB", "#7C3AED", "#C2410C", "#F97316"];

// The backend simulates 0-360 min in 10-min steps. The charts were designed for
// this coarse grid, so we downsample to it and keep the existing axis labels.
const TARGET_MINUTES = [0, 30, 60, 120, 180, 240];

const LEVEL_SCORE = { high: 0.85, medium: 0.6, low: 0.3 };
const PHYSICAL_SCALE_MAX = {
  gastricPressure: 1.5,
  gasVolume: 500,
  stomachPH: 7,
};

// Absolute reference maxima for reaction signals so bar height reflects true
// magnitude. Without these the curves self-normalize and a near-zero value (e.g.
// irritation 0.06 on its 0-2 scale) renders as a misleading flat "100%".
const REACTION_SCALE_MAX = {
  lactoseRemaining: 30, // g
  irritation: 1.0, // engine clamps 0-2; >=1 is severe
  cramping: 1.0, // 0-1 index
  intestinalGas: 200, // ml
  acetaldehyde: 1.0, // g
};

// Backend symptom keys -> the keys the UI charts/colors expect.
const SYMPTOM_MAP = { reflux: "reflux", bloating: "bloating", diarrhea: "diarrhea", upper_pain: "pain" };

function nearestIndex(timeMin, target) {
  let best = 0;
  let bestDist = Infinity;
  timeMin.forEach((t, i) => {
    const dist = Math.abs(t - target);
    if (dist < bestDist) {
      bestDist = dist;
      best = i;
    }
  });
  return best;
}

// Sample a backend curve at the UI's coarse minute grid. Mechanism curves are in
// physical units, so `normalize` rescales each series to 0-1 for the bar charts;
// symptom curves are already 0-1 sigmoids and pass through raw.
function sampleCurve(timeMin, values, { includeRaw = false, normalize = false, scaleMax = null } = {}) {
  if (!Array.isArray(timeMin) || !Array.isArray(values) || values.length === 0) {
    return TARGET_MINUTES.map((minute) => ({ minute, value: 0 }));
  }
  const max = normalize ? scaleMax || Math.max(...values.map((v) => Math.abs(v)), 0) : 1;
  const scale = normalize && max > 0 ? 1 / max : 1;
  return TARGET_MINUTES.map((minute) => {
    const raw = values[nearestIndex(timeMin, minute)] ?? 0;
    const point = { minute, value: Math.max(0, Math.min(1, raw * scale)) };
    if (includeRaw) point.rawValue = raw;
    return point;
  });
}

function seriesPeak(values) {
  return Array.isArray(values) && values.length ? Math.max(...values) : 0;
}

function formatAmount(value) {
  const n = Number(value);
  if (!Number.isFinite(n)) return String(value);
  if (Math.abs(n) >= 10) return String(Math.round(n));
  if (Math.abs(n) >= 1) return n.toFixed(1);
  return n.toFixed(2);
}

function prettyName(key) {
  return String(key).replace(/_/g, " ");
}

function shortName(dish) {
  if (!dish) return "Scan";
  const first = String(dish).split(/\s+/)[0];
  return first.length > 10 ? `${first.slice(0, 10)}…` : first;
}

function adaptSimulation(result) {
  if (!result || typeof result !== "object") return null;

  const sc = result.symptom_curves || {};
  const symptomTime = sc.time_min || [];
  const symptoms = {};
  for (const [src, dst] of Object.entries(SYMPTOM_MAP)) {
    if (Array.isArray(sc[src])) symptoms[dst] = sampleCurve(symptomTime, sc[src]);
  }

  const mc = result.mechanism_curves || {};
  const mechTime = mc.time_min || [];
  const physical = {
    gastricPressure: sampleCurve(mechTime, mc.gastric_pressure || [], {
      includeRaw: true,
      normalize: true,
      scaleMax: PHYSICAL_SCALE_MAX.gastricPressure,
    }),
    gasVolume: sampleCurve(mechTime, mc.gas_volume_ml || [], {
      includeRaw: true,
      normalize: true,
      scaleMax: PHYSICAL_SCALE_MAX.gasVolume,
    }),
    stomachPH: sampleCurve(mechTime, mc.pH || [], {
      includeRaw: true,
      normalize: true,
      scaleMax: PHYSICAL_SCALE_MAX.stomachPH,
    }),
  };

  // Reaction/biochemistry signals — drop series that never leave zero so the
  // chart isn't cluttered with flat lines for compounds this meal didn't have.
  const reactionSources = {
    lactoseRemaining: mc.lactose_remaining_g,
    irritation: mc.irritation,
    cramping: mc.cramping,
    intestinalGas: mc.intestine_gas_ml,
    acetaldehyde: mc.acetaldehyde_g,
  };
  const reactions = {};
  for (const [key, values] of Object.entries(reactionSources)) {
    if (seriesPeak(values) > 1e-6) {
      reactions[key] = sampleCurve(mechTime, values, {
        normalize: true,
        scaleMax: REACTION_SCALE_MAX[key],
      });
    }
  }

  // Root causes: take the drivers of the symptom that peaks highest among those
  // the backend actually attributed.
  const rc = result.root_causes || {};
  let chosen = null;
  let chosenPeak = -1;
  for (const key of Object.keys(rc)) {
    const peak = seriesPeak(sc[key]);
    if (peak > chosenPeak) {
      chosenPeak = peak;
      chosen = key;
    }
  }
  const drivers = chosen && Array.isArray(rc[chosen].drivers) ? rc[chosen].drivers : [];
  const rootCauses = drivers.map((d, i) => ({
    label: prettyName(d.chemical),
    impact: Math.round((d.contribution || 0) * 100),
    color: PALETTE[i % PALETTE.length],
  }));

  const chemicals = result.chemicals || {};
  const mealChemicals = Object.keys(chemicals).map((name, i) => ({
    name,
    amount: formatAmount(chemicals[name]),
    color: PALETTE[i % PALETTE.length],
  }));

  const mp = result.meal_physical || {};
  const volume = (Number(mp.solid_volume_ml) || 0) + (Number(mp.liquid_volume_ml) || 0);
  const ingredients = Array.isArray(result.ingredients) ? result.ingredients : [];
  const tags = ingredients.slice(0, 6).map((x) => x.name).filter(Boolean);

  const meal = {
    name: result.dish || "Scanned meal",
    shortName: shortName(result.dish),
    volume: volume > 0 ? `${Math.round(volume)} ml` : "—",
    tags: tags.length ? tags : Object.keys(chemicals),
    chemicals: mealChemicals,
  };

  const unknown = Array.isArray(result.unknown_compounds) ? result.unknown_compounds : [];
  const level = result.summary?.confidence || "medium";
  const confidence = {
    level,
    score: LEVEL_SCORE[level] ?? 0.6,
    reason: unknown.length
      ? `${unknown.length} input(s) could not be characterized: ${unknown.join(", ")}.`
      : "All inputs mapped to seeded property vectors.",
  };

  const openWorld = {
    substances: unknown.map((name) => ({ name, source: "gemini vision", confidence: 0.2 })),
  };

  const advice = chosen && rc[chosen] ? rc[chosen].advice || null : null;

  return {
    mealId: "scanned",
    meal,
    confidence,
    openWorld,
    symptoms,
    timeline: { physical, reactions },
    rootCauses,
    advice,
  };
}

module.exports = { adaptSimulation };
