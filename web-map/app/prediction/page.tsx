"use client";

import { FormEvent, useState } from "react";
import { API_BASE_URL, formatValue } from "../api";

type PredictionResult = {
  predicted_outbreak: boolean;
  risk_level: string;
  probability: number;
  explanation: string;
};

const initialForm = {
  contacts: 30,
  duration: 45,
  household_size: 4,
  hcir: 50,
  location_risk_score: 0.6,
};

export default function PredictionPage() {
  const [form, setForm] = useState(initialForm);
  const [result, setResult] = useState<PredictionResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    setResult(null);
    try {
      const response = await fetch(`${API_BASE_URL}/api/predict`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(form),
      });
      if (!response.ok) {
        setError(`API returned ${response.status}`);
        return;
      }
      setResult((await response.json()) as PredictionResult);
    } catch (fetchError) {
      setError(fetchError instanceof Error ? fetchError.message : "Network error");
    }
  }

  return (
    <main className="page">
      <header className="topbar">
        <h1>Outbreak Prediction Demo</h1>
        <p>Submit exposure factors to a deterministic demo scoring endpoint.</p>
      </header>
      <section className="content twoColumn">
        <form className="panel form" onSubmit={submit}>
          {Object.entries(form).map(([key, value]) => (
            <label key={key}>
              <span>{key.replaceAll("_", " ")}</span>
              <input
                max={key === "hcir" ? 100 : key === "location_risk_score" ? 1 : undefined}
                min={0}
                step={key === "location_risk_score" ? 0.05 : 1}
                type="number"
                value={value}
                onChange={(event) => setForm((current) => ({ ...current, [key]: Number(event.target.value) }))}
              />
            </label>
          ))}
          <button type="submit">Run Prediction</button>
        </form>
        <section className="panel">
          <h2>Result</h2>
          {error ? <p className="error">Unable to predict: {error}</p> : null}
          {result ? (
            <div className="result">
              <p>Predicted outbreak: {result.predicted_outbreak ? "Yes" : "No"}</p>
              <p>Risk level: {result.risk_level}</p>
              <p>Probability: {formatValue(result.probability)}</p>
              <p>{result.explanation}</p>
            </div>
          ) : (
            <p className="muted">No prediction submitted yet.</p>
          )}
        </section>
      </section>
    </main>
  );
}
