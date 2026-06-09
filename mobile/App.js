import React, { useMemo, useState } from "react";
import * as ImagePicker from "expo-image-picker";
import {
  ActivityIndicator,
  Alert,
  Image,
  SafeAreaView,
  ScrollView,
  StatusBar,
  StyleSheet,
  Text,
  TouchableOpacity,
  View,
} from "react-native";

const { buildMockSimulation, isKnownMeal, meals } = require("./src/mockEngine");
const { adaptSimulation } = require("./src/backendAdapter");
const { analyzeImage } = require("./src/apiClient");

const theme = {
  ink: "#201A17",
  muted: "#746861",
  canvas: "#FFF8F1",
  panel: "#FFFFFF",
  orange: "#F97316",
  orangeDark: "#C2410C",
  amber: "#FBBF24",
  teal: "#0F766E",
  blue: "#2563EB",
  rose: "#E11D48",
  violet: "#7C3AED",
  line: "#EADDD2",
};

const screens = ["Overview", "Meal", "Results"];

export default function App() {
  const [screen, setScreen] = useState("Overview");
  const [mealId, setMealId] = useState("ramen");
  const [photo, setPhoto] = useState(null);
  // A forecast produced by the real /analyze-image pipeline (image -> Gemini
  // ingredients -> chemicals -> simulation). When set, it takes precedence over
  // the offline sample meals.
  const [liveSimulation, setLiveSimulation] = useState(null);
  const [analysisStatus, setAnalysisStatus] = useState("idle"); // idle | loading | error
  const [analysisError, setAnalysisError] = useState(null);

  const mockSimulation = useMemo(() => buildMockSimulation(mealId), [mealId]);
  const simulation = liveSimulation || mockSimulation;

  const photoUnrecognized =
    Boolean(photo) && !liveSimulation && analysisStatus === "idle" && !isKnownMeal(mealId);

  // Selecting a sample meal switches off any live photo forecast.
  function selectMeal(id) {
    setLiveSimulation(null);
    setAnalysisStatus("idle");
    setAnalysisError(null);
    setMealId(id);
  }

  async function runAnalysis(asset) {
    setAnalysisError(null);
    setAnalysisStatus("loading");
    try {
      const raw = await analyzeImage(asset, { clinicalProfile: {} });
      const adapted = adaptSimulation(raw);
      if (!adapted) throw new Error("The engine returned an unexpected response.");
      setLiveSimulation(adapted);
      setAnalysisStatus("idle");
    } catch (err) {
      setAnalysisError(err.message || "Analysis failed.");
      setAnalysisStatus("error");
    }
  }

  async function choosePhoto(source) {
    const pickerOptions = {
      allowsEditing: true,
      aspect: [4, 3],
      quality: 0.82,
    };
    const permission =
      source === "camera"
        ? await ImagePicker.requestCameraPermissionsAsync()
        : await ImagePicker.requestMediaLibraryPermissionsAsync();

    if (permission.status !== "granted") {
      Alert.alert("Permission needed", "Allow photo access so TummyBuddy can analyze the meal.");
      return;
    }

    const result =
      source === "camera"
        ? await ImagePicker.launchCameraAsync(pickerOptions)
        : await ImagePicker.launchImageLibraryAsync(pickerOptions);

    if (result.canceled || !result.assets || !result.assets[0]) return;

    const asset = result.assets[0];
    setPhoto(asset);
    setLiveSimulation(null);
    setMealId(null);
    setScreen("Results");
    await runAnalysis(asset);
  }

  return (
    <SafeAreaView style={styles.safeArea}>
      <StatusBar barStyle="dark-content" backgroundColor={theme.canvas} />
      <View style={styles.shell}>
        <Header />
        <SegmentedControl value={screen} onChange={setScreen} />
        <ScrollView showsVerticalScrollIndicator={false} contentContainerStyle={styles.scrollBody}>
          {screen === "Overview" ? (
            <OverviewScreen simulation={simulation} onScan={() => setScreen("Meal")} />
          ) : null}
          {screen === "Meal" ? (
            <MealScreen
              mealId={mealId}
              onImportPhoto={() => choosePhoto("library")}
              onSelectMeal={selectMeal}
              onTakePhoto={() => choosePhoto("camera")}
              photo={photo}
              photoUnrecognized={photoUnrecognized}
              simulation={simulation}
            />
          ) : null}
          {screen === "Results" ? (
            <ResultsScreen
              analysisError={analysisError}
              analysisStatus={analysisStatus}
              onPickMeal={() => setScreen("Meal")}
              onRetry={() => photo && runAnalysis(photo)}
              photo={photo}
              simulation={simulation}
            />
          ) : null}
        </ScrollView>
      </View>
    </SafeAreaView>
  );
}

function Header() {
  return (
    <View style={styles.header}>
      <View>
        <Text style={styles.kicker}>TummyBuddy</Text>
        <Text style={styles.title}>Gut forecast</Text>
      </View>
      <View style={styles.avatar}>
        <Text style={styles.avatarText}>TB</Text>
      </View>
    </View>
  );
}

function SegmentedControl({ value, onChange }) {
  return (
    <View style={styles.segmented}>
      {screens.map((item) => {
        const active = value === item;
        return (
          <TouchableOpacity
            key={item}
            accessibilityRole="button"
            accessibilityState={{ selected: active }}
            onPress={() => onChange(item)}
            style={[styles.segmentButton, active ? styles.segmentButtonActive : null]}
          >
            <Text style={[styles.segmentText, active ? styles.segmentTextActive : null]}>
              {item}
            </Text>
          </TouchableOpacity>
        );
      })}
    </View>
  );
}

function OverviewScreen({ simulation, onScan }) {
  if (!simulation) {
    return (
      <View style={styles.stack}>
        <View style={styles.panel}>
          <Text style={styles.panelTitle}>No meal selected</Text>
          <Text style={styles.bodyCopy}>
            Pick a sample meal to see its gut forecast.
          </Text>
          <TouchableOpacity
            style={[styles.primaryButton, { marginTop: 14 }]}
            onPress={onScan}
            accessibilityRole="button"
          >
            <Text style={styles.primaryButtonText}>Choose a meal</Text>
          </TouchableOpacity>
        </View>
      </View>
    );
  }

  const highestSymptom = Object.keys(simulation.symptoms)
    .map((name) => ({
      name,
      peak: Math.max(...simulation.symptoms[name].map((point) => point.value)),
    }))
    .sort((a, b) => b.peak - a.peak)[0];

  return (
    <View style={styles.stack}>
      <View style={styles.heroPanel}>
        <View style={styles.heroArt}>
          <View style={[styles.orbit, { backgroundColor: theme.orange }]} />
          <View style={[styles.orbitSmall, { backgroundColor: theme.teal }]} />
          <View style={styles.stomachLine} />
        </View>
        <Text style={styles.heroLabel}>Next meal risk</Text>
        <Text style={styles.heroScore}>{Math.round(highestSymptom.peak * 100)}%</Text>
        <Text style={styles.heroCopy}>
          {capitalize(highestSymptom.name)} is the leading curve for {simulation.meal.shortName}.
        </Text>
        <TouchableOpacity style={styles.primaryButton} onPress={onScan} accessibilityRole="button">
          <Text style={styles.primaryButtonText}>Analyze meal</Text>
        </TouchableOpacity>
      </View>

      <View style={styles.twoColumn}>
        <Metric label="Confidence" value={simulation.confidence.level} tone={theme.teal} />
        <Metric label="Volume" value={simulation.meal.volume} tone={theme.blue} />
      </View>

      <SectionTitle title="Live physiology" subtitle="Property vectors driving the forecast" />
      <PropertyList chemicals={simulation.meal.chemicals} />
    </View>
  );
}

function MealScreen({
  mealId,
  onImportPhoto,
  onSelectMeal,
  onTakePhoto,
  photo,
  photoUnrecognized,
  simulation,
}) {
  return (
    <View style={styles.stack}>
      <SectionTitle title="Meal input" subtitle="Pick a sample or imagine this came from a photo scan" />
      {photoUnrecognized ? (
        <View style={styles.noticePanel}>
          <Text style={styles.panelTitle}>Couldn't identify this meal</Text>
          <Text style={styles.bodyCopy}>
            This demo has no on-device food recognition. Pick the closest sample
            below and the forecast will use that meal's seeded chemistry.
          </Text>
        </View>
      ) : null}
      <View style={styles.photoPanel}>
        <View style={styles.photoPreview}>
          {photo ? (
            <Image source={{ uri: photo.uri }} style={styles.photoImage} />
          ) : (
            <View style={styles.photoPlaceholder}>
              <Text style={styles.photoIcon}>+</Text>
              <Text style={styles.photoPlaceholderText}>Meal photo</Text>
            </View>
          )}
        </View>
        <View style={styles.photoActions}>
          <TouchableOpacity style={styles.secondaryButton} onPress={onTakePhoto} accessibilityRole="button">
            <Text style={styles.secondaryButtonText}>Take photo</Text>
          </TouchableOpacity>
          <TouchableOpacity style={styles.secondaryButton} onPress={onImportPhoto} accessibilityRole="button">
            <Text style={styles.secondaryButtonText}>Import photo</Text>
          </TouchableOpacity>
        </View>
      </View>

      <View style={styles.mealGrid}>
        {Object.keys(meals).map((id) => {
          const meal = meals[id];
          const active = mealId === id;
          return (
            <TouchableOpacity
              key={id}
              accessibilityRole="button"
              accessibilityState={{ selected: active }}
              onPress={() => onSelectMeal(id)}
              style={[styles.mealTile, active ? styles.mealTileActive : null]}
            >
              <View style={[styles.mealImage, { backgroundColor: meal.photoTone }]}>
                <Text style={styles.mealInitial}>{meal.shortName.slice(0, 1)}</Text>
              </View>
              <Text style={styles.mealName}>{meal.name}</Text>
              <Text style={styles.mealMeta}>{meal.volume}</Text>
            </TouchableOpacity>
          );
        })}
      </View>

      {simulation ? (
        <>
          <View style={styles.panel}>
            <Text style={styles.panelTitle}>{simulation.meal.name}</Text>
            <View style={styles.tagRow}>
              {simulation.meal.tags.map((tag) => (
                <View key={tag} style={styles.tag}>
                  <Text style={styles.tagText}>{tag}</Text>
                </View>
              ))}
            </View>
          </View>

          <SectionTitle title="Characterization" subtitle="Unknown inputs still enter the physics model" />
          <OpenWorld simulation={simulation} />
        </>
      ) : (
        <View style={styles.panel}>
          <Text style={styles.panelTitle}>No meal selected</Text>
          <Text style={styles.bodyCopy}>Tap a sample above to see its breakdown and forecast.</Text>
        </View>
      )}
    </View>
  );
}

function PhotoBanner({ photo, title, children }) {
  return (
    <View style={styles.scanBanner}>
      {photo ? <Image source={{ uri: photo.uri }} style={styles.scanThumb} /> : null}
      <View style={styles.scanCopy}>
        <Text style={styles.panelTitle}>{title}</Text>
        <Text style={styles.bodyCopy}>{children}</Text>
      </View>
    </View>
  );
}

function ResultsScreen({ analysisError, analysisStatus, onPickMeal, onRetry, photo, simulation }) {
  if (analysisStatus === "loading") {
    return (
      <View style={styles.stack}>
        <PhotoBanner photo={photo} title="Analyzing your meal…">
          Sending the photo to the engine: identifying ingredients, mapping them
          to compounds, then simulating digestion.
        </PhotoBanner>
        <View style={[styles.panel, styles.loadingPanel]}>
          <ActivityIndicator size="large" color={theme.orange} />
          <Text style={[styles.bodyCopy, { marginTop: 12 }]}>This usually takes a few seconds.</Text>
        </View>
      </View>
    );
  }

  if (analysisStatus === "error") {
    return (
      <View style={styles.stack}>
        <PhotoBanner photo={photo} title="Analysis failed">
          {analysisError || "Something went wrong analyzing this photo."}
        </PhotoBanner>
        <View style={styles.panel}>
          <View style={styles.photoActions}>
            <TouchableOpacity style={styles.secondaryButton} onPress={onRetry} accessibilityRole="button">
              <Text style={styles.secondaryButtonText}>Try again</Text>
            </TouchableOpacity>
            <TouchableOpacity style={styles.secondaryButton} onPress={onPickMeal} accessibilityRole="button">
              <Text style={styles.secondaryButtonText}>Pick a sample</Text>
            </TouchableOpacity>
          </View>
        </View>
      </View>
    );
  }

  if (!simulation) {
    return (
      <View style={styles.stack}>
        {photo ? (
          <PhotoBanner photo={photo} title="No forecast yet">
            Pick the closest sample meal to generate a forecast.
          </PhotoBanner>
        ) : null}
        <View style={styles.panel}>
          <Text style={styles.panelTitle}>Choose a meal</Text>
          <Text style={styles.bodyCopy}>Select one of the seeded sample meals to see its gut forecast.</Text>
          <TouchableOpacity
            style={[styles.primaryButton, { marginTop: 14 }]}
            onPress={onPickMeal}
            accessibilityRole="button"
          >
            <Text style={styles.primaryButtonText}>Pick a sample meal</Text>
          </TouchableOpacity>
        </View>
      </View>
    );
  }

  const isLive = simulation.mealId === "scanned";

  return (
    <View style={styles.stack}>
      {photo ? (
        <PhotoBanner photo={photo} title={`Forecast for ${simulation.meal.name}`}>
          {isLive
            ? "Identified from your photo, then run through the full digestion simulation."
            : `Using the ${simulation.meal.name} sample you picked.`}
        </PhotoBanner>
      ) : null}

      <View style={styles.panel}>
        <View style={styles.resultTop}>
          <View>
            <Text style={styles.panelTitle}>Symptom curves</Text>
            <Text style={styles.panelSubtitle}>0-240 min after meal</Text>
          </View>
          <ConfidencePill confidence={simulation.confidence} />
        </View>
        <CurveChart symptoms={simulation.symptoms} />
      </View>

      <SectionTitle title="Physical state over time" subtitle="Pressure, gas, and acidity through the stomach" />
      <TimelineChart
        curves={simulation.timeline.physical}
        labels={{
          gastricPressure: "Gastric pressure",
          gasVolume: "Gas volume",
          stomachPH: "Stomach pH",
        }}
        units={{
          gastricPressure: "pressure",
          gasVolume: "ml",
          stomachPH: "pH",
        }}
        colors={{
          gastricPressure: theme.orange,
          gasVolume: theme.blue,
          stomachPH: theme.teal,
        }}
      />

      <SectionTitle title="Reaction state over time" subtitle="Biochemistry and characterization signals, not only mechanics" />
      <TimelineChart
        curves={simulation.timeline.reactions}
        labels={{
          co2Release: "CO2 release",
          fatBrakeSignal: "Fat brake signal",
          lactoseRemaining: "Lactose remaining",
          spiceIrritation: "Spice irritation",
          starchBreakdown: "Starch breakdown",
          sugarOsmoticLoad: "Sugar osmotic load",
          yuzuCharacterization: "Yuzu confidence",
          irritation: "Mucosal irritation",
          cramping: "Cramping",
          intestinalGas: "Intestinal gas",
          acetaldehyde: "Acetaldehyde",
        }}
        colors={{
          co2Release: theme.blue,
          fatBrakeSignal: theme.amber,
          lactoseRemaining: theme.violet,
          spiceIrritation: theme.rose,
          starchBreakdown: theme.teal,
          sugarOsmoticLoad: theme.orangeDark,
          yuzuCharacterization: theme.blue,
          irritation: theme.rose,
          cramping: theme.violet,
          intestinalGas: theme.blue,
          acetaldehyde: theme.orangeDark,
        }}
      />

      <SectionTitle title="Why this happens" subtitle="Counterfactual root-cause ranking" />
      <View style={styles.panel}>
        {simulation.rootCauses.map((cause) => (
          <View key={cause.label} style={styles.causeRow}>
            <View style={styles.causeLabelWrap}>
              <View style={[styles.dot, { backgroundColor: cause.color }]} />
              <Text style={styles.causeLabel}>{cause.label}</Text>
            </View>
            <View style={styles.causeTrack}>
              <View
                style={[
                  styles.causeFill,
                  { width: `${cause.impact}%`, backgroundColor: cause.color },
                ]}
              />
            </View>
            <Text style={styles.causeImpact}>{cause.impact}%</Text>
          </View>
        ))}
      </View>

      <View style={styles.panel}>
        <Text style={styles.panelTitle}>Model confidence</Text>
        <Text style={styles.bodyCopy}>{simulation.confidence.reason}</Text>
        {simulation.advice ? <Text style={styles.bodyCopy}>{simulation.advice}</Text> : null}
      </View>
    </View>
  );
}

function Metric({ label, value, tone }) {
  return (
    <View style={styles.metric}>
      <View style={[styles.metricMark, { backgroundColor: tone }]} />
      <Text style={styles.metricLabel}>{label}</Text>
      <Text style={styles.metricValue}>{value}</Text>
    </View>
  );
}

function PropertyList({ chemicals }) {
  return (
    <View style={styles.panel}>
      {chemicals.map((chemical) => (
        <View key={chemical.name} style={styles.propertyRow}>
          <View style={styles.propertyNameWrap}>
            <View style={[styles.dot, { backgroundColor: chemical.color }]} />
            <Text style={styles.propertyName}>{chemical.name}</Text>
          </View>
          <Text style={styles.propertyValue}>{chemical.amount}</Text>
        </View>
      ))}
    </View>
  );
}

function OpenWorld({ simulation }) {
  if (simulation.openWorld.substances.length === 0) {
    return (
      <View style={styles.panel}>
        <Text style={styles.panelTitle}>All substances are known</Text>
        <Text style={styles.bodyCopy}>The forecast uses seeded property vectors for this meal.</Text>
      </View>
    );
  }

  return (
    <View style={styles.panel}>
      {simulation.openWorld.substances.map((substance) => (
        <View key={substance.name} style={styles.openWorldRow}>
          <View>
            <Text style={styles.panelTitle}>{substance.name}</Text>
            <Text style={styles.bodyCopy}>Source: {substance.source}</Text>
          </View>
          <Text style={styles.openWorldScore}>{Math.round(substance.confidence * 100)}%</Text>
        </View>
      ))}
    </View>
  );
}

function ConfidencePill({ confidence }) {
  const color = confidence.level === "high" ? theme.teal : theme.orangeDark;
  return (
    <View style={[styles.confidencePill, { borderColor: color }]}>
      <Text style={[styles.confidenceText, { color }]}>{Math.round(confidence.score * 100)}%</Text>
    </View>
  );
}

function formatTimelinePeak(value, unit) {
  if (!Number.isFinite(value)) return "-";
  if (unit === "ml") return `${Math.round(value)} ml`;
  if (unit === "pH") return `${value.toFixed(1)} pH`;
  if (unit === "pressure") return value.toFixed(2);
  return `${Math.round(value * 100)}%`;
}

function TimelineChart({ colors, curves, labels, units = {} }) {
  const minuteLabels = [0, 30, 60, 120, 180, 240];
  return (
    <View style={styles.panel}>
      {Object.keys(curves).map((key) => {
        const points = curves[key];
        const peak = Math.max(...points.map((point) => point.value));
        const rawValues = points
          .map((point) => point.rawValue)
          .filter((value) => typeof value === "number");
        const peakLabel = rawValues.length
          ? formatTimelinePeak(Math.max(...rawValues), units[key])
          : formatTimelinePeak(peak, units[key]);
        return (
          <View key={key} style={styles.timelineCurve}>
            <View style={styles.chartLabelRow}>
              <View style={styles.timelineLabelWrap}>
                <View style={[styles.dot, { backgroundColor: colors[key] || theme.orange }]} />
                <Text style={styles.chartLabel}>{labels[key] || key}</Text>
              </View>
              <Text style={styles.chartPeak}>{peakLabel}</Text>
            </View>
            <View style={styles.timelineRow}>
              {points.map((point) => (
                <View key={`${key}-${point.minute}`} style={styles.timelinePointSlot}>
                  <View
                    style={[
                      styles.timelinePoint,
                      {
                        height: 8 + point.value * 64,
                        backgroundColor: colors[key] || theme.orange,
                      },
                    ]}
                  />
                </View>
              ))}
            </View>
          </View>
        );
      })}
      <View style={styles.minuteRow}>
        {minuteLabels.map((minute) => (
          <Text key={minute} style={styles.minuteText}>
            {minute}
          </Text>
        ))}
      </View>
    </View>
  );
}

function CurveChart({ symptoms }) {
  const colors = {
    reflux: theme.blue,
    bloating: theme.orange,
    pain: theme.rose,
    diarrhea: theme.teal,
  };
  const minutes = [0, 30, 60, 120, 180, 240];
  return (
    <View style={styles.chart}>
      {Object.keys(symptoms).map((name) => {
        const points = symptoms[name];
        return (
          <View key={name} style={styles.chartBand}>
            <View style={styles.chartLabelRow}>
              <Text style={styles.chartLabel}>{capitalize(name)}</Text>
              <Text style={styles.chartPeak}>
                {Math.round(Math.max(...points.map((point) => point.value)) * 100)}%
              </Text>
            </View>
            <View style={styles.barRow}>
              {points.map((point) => (
                <View key={`${name}-${point.minute}`} style={styles.barSlot}>
                  <View
                    style={[
                      styles.bar,
                      {
                        height: 18 + point.value * 82,
                        backgroundColor: colors[name],
                      },
                    ]}
                  />
                </View>
              ))}
            </View>
          </View>
        );
      })}
      <View style={styles.minuteRow}>
        {minutes.map((minute) => (
          <Text key={minute} style={styles.minuteText}>
            {minute}
          </Text>
        ))}
      </View>
    </View>
  );
}

function SectionTitle({ title, subtitle }) {
  return (
    <View>
      <Text style={styles.sectionTitle}>{title}</Text>
      <Text style={styles.sectionSubtitle}>{subtitle}</Text>
    </View>
  );
}

function capitalize(value) {
  return value.charAt(0).toUpperCase() + value.slice(1);
}

const styles = StyleSheet.create({
  safeArea: {
    flex: 1,
    backgroundColor: theme.canvas,
  },
  shell: {
    flex: 1,
    paddingHorizontal: 18,
    paddingTop: 10,
  },
  header: {
    alignItems: "center",
    flexDirection: "row",
    justifyContent: "space-between",
    marginBottom: 14,
  },
  kicker: {
    color: theme.orangeDark,
    fontSize: 13,
    fontWeight: "800",
    letterSpacing: 0,
    textTransform: "uppercase",
  },
  title: {
    color: theme.ink,
    fontSize: 31,
    fontWeight: "900",
    letterSpacing: 0,
    lineHeight: 36,
  },
  avatar: {
    alignItems: "center",
    backgroundColor: theme.ink,
    borderRadius: 22,
    height: 44,
    justifyContent: "center",
    width: 44,
  },
  avatarText: {
    color: "#FFFFFF",
    fontSize: 13,
    fontWeight: "900",
  },
  segmented: {
    backgroundColor: "#FFEAD8",
    borderRadius: 8,
    flexDirection: "row",
    marginBottom: 16,
    padding: 4,
  },
  segmentButton: {
    alignItems: "center",
    borderRadius: 6,
    flex: 1,
    minHeight: 40,
    justifyContent: "center",
  },
  segmentButtonActive: {
    backgroundColor: theme.orange,
  },
  segmentText: {
    color: theme.orangeDark,
    fontSize: 14,
    fontWeight: "800",
  },
  segmentTextActive: {
    color: "#FFFFFF",
  },
  scrollBody: {
    paddingBottom: 32,
  },
  stack: {
    gap: 16,
  },
  heroPanel: {
    backgroundColor: theme.panel,
    borderColor: theme.line,
    borderRadius: 8,
    borderWidth: 1,
    padding: 18,
  },
  heroArt: {
    alignItems: "center",
    alignSelf: "stretch",
    backgroundColor: "#FFF1E6",
    borderRadius: 8,
    height: 132,
    justifyContent: "center",
    marginBottom: 16,
    overflow: "hidden",
  },
  orbit: {
    borderRadius: 48,
    height: 96,
    opacity: 0.9,
    position: "absolute",
    right: 70,
    top: 18,
    width: 96,
  },
  orbitSmall: {
    borderRadius: 28,
    height: 56,
    left: 82,
    opacity: 0.9,
    position: "absolute",
    top: 54,
    width: 56,
  },
  stomachLine: {
    borderBottomColor: theme.ink,
    borderBottomWidth: 6,
    borderLeftColor: theme.ink,
    borderLeftWidth: 6,
    borderRadius: 32,
    height: 72,
    transform: [{ rotate: "-18deg" }],
    width: 98,
  },
  heroLabel: {
    color: theme.muted,
    fontSize: 14,
    fontWeight: "800",
  },
  heroScore: {
    color: theme.ink,
    fontSize: 52,
    fontWeight: "900",
    letterSpacing: 0,
    lineHeight: 58,
  },
  heroCopy: {
    color: theme.muted,
    fontSize: 15,
    lineHeight: 21,
    marginBottom: 16,
  },
  primaryButton: {
    alignItems: "center",
    backgroundColor: theme.orange,
    borderRadius: 8,
    minHeight: 48,
    justifyContent: "center",
  },
  primaryButtonText: {
    color: "#FFFFFF",
    fontSize: 16,
    fontWeight: "900",
  },
  secondaryButton: {
    alignItems: "center",
    backgroundColor: theme.ink,
    borderRadius: 8,
    flex: 1,
    minHeight: 44,
    justifyContent: "center",
    paddingHorizontal: 10,
  },
  secondaryButtonText: {
    color: "#FFFFFF",
    fontSize: 14,
    fontWeight: "900",
  },
  photoPanel: {
    backgroundColor: theme.panel,
    borderColor: theme.line,
    borderRadius: 8,
    borderWidth: 1,
    padding: 12,
  },
  photoPreview: {
    backgroundColor: "#FFF1E6",
    borderRadius: 8,
    height: 170,
    marginBottom: 10,
    overflow: "hidden",
  },
  photoImage: {
    height: "100%",
    width: "100%",
  },
  photoPlaceholder: {
    alignItems: "center",
    flex: 1,
    justifyContent: "center",
  },
  photoIcon: {
    color: theme.orange,
    fontSize: 46,
    fontWeight: "900",
    lineHeight: 50,
  },
  photoPlaceholderText: {
    color: theme.orangeDark,
    fontSize: 14,
    fontWeight: "900",
    marginTop: 4,
  },
  photoActions: {
    flexDirection: "row",
    gap: 10,
  },
  noticePanel: {
    backgroundColor: "#FFF1E6",
    borderColor: theme.orange,
    borderRadius: 8,
    borderWidth: 1,
    padding: 16,
  },
  loadingPanel: {
    alignItems: "center",
    paddingVertical: 28,
  },
  scanBanner: {
    alignItems: "center",
    backgroundColor: theme.panel,
    borderColor: theme.line,
    borderRadius: 8,
    borderWidth: 1,
    flexDirection: "row",
    padding: 12,
  },
  scanThumb: {
    backgroundColor: "#FFF1E6",
    borderRadius: 8,
    height: 70,
    marginRight: 12,
    width: 86,
  },
  scanCopy: {
    flex: 1,
  },
  twoColumn: {
    flexDirection: "row",
    gap: 12,
  },
  metric: {
    backgroundColor: theme.panel,
    borderColor: theme.line,
    borderRadius: 8,
    borderWidth: 1,
    flex: 1,
    minHeight: 104,
    padding: 14,
  },
  metricMark: {
    borderRadius: 8,
    height: 8,
    marginBottom: 14,
    width: 44,
  },
  metricLabel: {
    color: theme.muted,
    fontSize: 13,
    fontWeight: "800",
  },
  metricValue: {
    color: theme.ink,
    fontSize: 22,
    fontWeight: "900",
    marginTop: 4,
    textTransform: "capitalize",
  },
  sectionTitle: {
    color: theme.ink,
    fontSize: 19,
    fontWeight: "900",
    letterSpacing: 0,
  },
  sectionSubtitle: {
    color: theme.muted,
    fontSize: 14,
    lineHeight: 20,
    marginTop: 3,
  },
  panel: {
    backgroundColor: theme.panel,
    borderColor: theme.line,
    borderRadius: 8,
    borderWidth: 1,
    padding: 16,
  },
  panelTitle: {
    color: theme.ink,
    fontSize: 17,
    fontWeight: "900",
  },
  panelSubtitle: {
    color: theme.muted,
    fontSize: 13,
    marginTop: 3,
  },
  bodyCopy: {
    color: theme.muted,
    fontSize: 14,
    lineHeight: 20,
    marginTop: 5,
  },
  propertyRow: {
    alignItems: "center",
    borderBottomColor: "#F1E6DC",
    borderBottomWidth: 1,
    flexDirection: "row",
    justifyContent: "space-between",
    minHeight: 44,
  },
  propertyNameWrap: {
    alignItems: "center",
    flex: 1,
    flexDirection: "row",
    gap: 9,
    paddingRight: 10,
  },
  dot: {
    borderRadius: 5,
    height: 10,
    width: 10,
  },
  propertyName: {
    color: theme.ink,
    flexShrink: 1,
    fontSize: 14,
    fontWeight: "800",
  },
  propertyValue: {
    color: theme.muted,
    fontSize: 13,
    fontWeight: "800",
  },
  mealGrid: {
    flexDirection: "row",
    gap: 10,
  },
  mealTile: {
    backgroundColor: theme.panel,
    borderColor: theme.line,
    borderRadius: 8,
    borderWidth: 1,
    flex: 1,
    minHeight: 166,
    padding: 10,
  },
  mealTileActive: {
    borderColor: theme.orange,
    borderWidth: 2,
  },
  mealImage: {
    alignItems: "center",
    borderRadius: 8,
    height: 72,
    justifyContent: "center",
    marginBottom: 10,
  },
  mealInitial: {
    color: "#FFFFFF",
    fontSize: 28,
    fontWeight: "900",
  },
  mealName: {
    color: theme.ink,
    fontSize: 13,
    fontWeight: "900",
    lineHeight: 17,
  },
  mealMeta: {
    color: theme.muted,
    fontSize: 12,
    fontWeight: "800",
    marginTop: 5,
  },
  tagRow: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: 8,
    marginTop: 12,
  },
  tag: {
    backgroundColor: "#FFF1E6",
    borderRadius: 8,
    paddingHorizontal: 10,
    paddingVertical: 7,
  },
  tagText: {
    color: theme.orangeDark,
    fontSize: 12,
    fontWeight: "900",
  },
  openWorldRow: {
    alignItems: "center",
    flexDirection: "row",
    justifyContent: "space-between",
  },
  openWorldScore: {
    color: theme.orangeDark,
    fontSize: 24,
    fontWeight: "900",
  },
  resultTop: {
    alignItems: "center",
    flexDirection: "row",
    justifyContent: "space-between",
    marginBottom: 12,
  },
  confidencePill: {
    alignItems: "center",
    borderRadius: 8,
    borderWidth: 2,
    minWidth: 64,
    paddingHorizontal: 10,
    paddingVertical: 7,
  },
  confidenceText: {
    fontSize: 15,
    fontWeight: "900",
  },
  timelineCurve: {
    borderBottomColor: "#F1E6DC",
    borderBottomWidth: 1,
    paddingBottom: 12,
    paddingTop: 2,
  },
  timelineLabelWrap: {
    alignItems: "center",
    flex: 1,
    flexDirection: "row",
    gap: 8,
    paddingRight: 8,
  },
  timelineRow: {
    alignItems: "flex-end",
    flexDirection: "row",
    gap: 7,
    height: 78,
    marginTop: 9,
  },
  timelinePointSlot: {
    alignItems: "center",
    backgroundColor: "#FFF5EC",
    borderRadius: 8,
    flex: 1,
    height: 78,
    justifyContent: "flex-end",
    overflow: "hidden",
  },
  timelinePoint: {
    borderRadius: 8,
    width: "100%",
  },
  chart: {
    gap: 12,
  },
  chartBand: {
    gap: 8,
  },
  chartLabelRow: {
    alignItems: "center",
    flexDirection: "row",
    justifyContent: "space-between",
  },
  chartLabel: {
    color: theme.ink,
    fontSize: 14,
    fontWeight: "900",
  },
  chartPeak: {
    color: theme.muted,
    fontSize: 13,
    fontWeight: "900",
  },
  barRow: {
    alignItems: "flex-end",
    flexDirection: "row",
    gap: 7,
    height: 112,
  },
  barSlot: {
    alignItems: "center",
    backgroundColor: "#FFF5EC",
    borderRadius: 8,
    flex: 1,
    height: 112,
    justifyContent: "flex-end",
    overflow: "hidden",
  },
  bar: {
    borderRadius: 8,
    width: "100%",
  },
  minuteRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    paddingHorizontal: 2,
  },
  minuteText: {
    color: theme.muted,
    fontSize: 10,
    fontWeight: "800",
  },
  causeRow: {
    alignItems: "center",
    flexDirection: "row",
    gap: 9,
    minHeight: 42,
  },
  causeLabelWrap: {
    alignItems: "center",
    flexDirection: "row",
    gap: 8,
    width: 128,
  },
  causeLabel: {
    color: theme.ink,
    flexShrink: 1,
    fontSize: 13,
    fontWeight: "900",
  },
  causeTrack: {
    backgroundColor: "#F3E7DC",
    borderRadius: 8,
    flex: 1,
    height: 10,
    overflow: "hidden",
  },
  causeFill: {
    borderRadius: 8,
    height: 10,
  },
  causeImpact: {
    color: theme.muted,
    fontSize: 12,
    fontWeight: "900",
    textAlign: "right",
    width: 34,
  },
});
