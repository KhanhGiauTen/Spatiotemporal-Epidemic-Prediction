export type PredictionInput = { contacts: number; duration: number; household_size: number; hcir: number; location_risk_score: number };

const limits: Record<keyof PredictionInput, number> = { contacts: 100000, duration: 86400, household_size: 1000, hcir: 100, location_risk_score: 1 };

export function validInput(value: unknown): value is PredictionInput {
  if (!value || typeof value !== "object" || Array.isArray(value)) return false;
  const record = value as Record<string, unknown>;
  return Object.keys(record).length === 5 && Object.entries(limits).every(([key, max]) => typeof record[key] === "number" && Number.isFinite(record[key]) && (record[key] as number) >= 0 && (record[key] as number) <= max);
}

// Same deterministic demonstration formula as src/api/main.py; not a trained model.
export function predictDemo(input: PredictionInput) {
  const probability = Number((Math.min(input.contacts / 60, 1) * 0.24 + Math.min(input.duration / 120, 1) * 0.18 + Math.min(input.household_size / 8, 1) * 0.14 + input.hcir / 100 * 0.28 + input.location_risk_score * 0.16).toFixed(3));
  return {
    predicted_outbreak: probability >= 0.65,
    risk_level: probability >= 0.75 ? "high" : probability >= 0.45 ? "medium" : "low",
    probability,
    explanation: "Illustrative heuristic score only, not a calibrated probability or a trained model prediction. Not medical or public-health advice.",
  };
}
