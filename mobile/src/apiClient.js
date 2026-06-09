// Talks to the gastric engine's /analyze-image endpoint.
//
// Host resolution (first hit wins):
//   1. EXPO_PUBLIC_API_URL  — explicit override (tunnels, deployed backend, or a
//      LAN IP that auto-detect gets wrong). Set it in mobile/.env.
//   2. expo-constants hostUri/debuggerHost — the dev-machine host Expo Go used to
//      load this bundle. Reliable on a physical phone; we just swap to the API port.
//   3. NativeModules.SourceCode.scriptURL — fallback for non-Expo-Go runtimes.
//   4. localhost — last resort (only correct in a simulator/web).

import Constants from "expo-constants";
import { NativeModules } from "react-native";

const API_PORT = 8000;

// hostUri looks like "192.168.1.5:8081" or "exp://192.168.1.5:8081"; we want the
// bare host. debuggerHost has the same "host:port" form.
function hostFromExpo() {
  const candidates = [
    Constants.expoConfig?.hostUri,
    Constants.expoGoConfig?.debuggerHost,
    Constants.manifest2?.extra?.expoGo?.debuggerHost,
    Constants.manifest?.debuggerHost,
    Constants.manifest?.hostUri,
  ];
  for (const candidate of candidates) {
    if (typeof candidate === "string" && candidate.length) {
      const host = candidate.replace(/^\w+:\/\//, "").split(":")[0];
      if (host && host !== "localhost" && host !== "127.0.0.1") return host;
    }
  }
  return null;
}

function hostFromScriptURL() {
  const scriptURL = NativeModules.SourceCode && NativeModules.SourceCode.scriptURL;
  const match = scriptURL ? /https?:\/\/([^:/]+)(?::\d+)?/.exec(scriptURL) : null;
  return match ? match[1] : null;
}

function resolveBaseUrl() {
  const override = process.env.EXPO_PUBLIC_API_URL;
  if (override) return override.replace(/\/$/, "");

  const host = hostFromExpo() || hostFromScriptURL();
  if (host) return `http://${host}:${API_PORT}`;

  return `http://localhost:${API_PORT}`;
}

export const API_BASE_URL = resolveBaseUrl();

export async function analyzeImage(asset, { clinicalProfile = {}, simulationConfig = null } = {}) {
  const form = new FormData();
  form.append("image", {
    uri: asset.uri,
    name: asset.fileName || "meal.jpg",
    type: asset.mimeType || "image/jpeg",
  });
  form.append("clinical_profile", JSON.stringify(clinicalProfile));
  form.append("simulation_config", JSON.stringify(simulationConfig));

  let response;
  try {
    // Let fetch set the multipart boundary; do not set Content-Type manually.
    response = await fetch(`${API_BASE_URL}/analyze-image`, { method: "POST", body: form });
  } catch (err) {
    throw new Error(
      `Couldn't reach the engine at ${API_BASE_URL}. Is the backend running and on the same network? (${err.message})`
    );
  }

  if (!response.ok) {
    const detail = await response.text().catch(() => "");
    throw new Error(`Engine returned ${response.status}. ${detail.slice(0, 200)}`);
  }
  return response.json();
}
