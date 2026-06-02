"use client";

import { useEffect, useState } from "react";
import { fetchJson, formatValue } from "./api";

type Overview = Record<string, number | string | null>;

const cards = [
  ["Total Records", "total_records"],
  ["Total Contacts", "total_contacts"],
  ["Infected Contacts", "infected_contacts"],
  ["Classification Accuracy", "classification_accuracy"],
  ["Precision", "precision"],
  ["Recall", "recall"],
  ["F1 Score", "f1_score"],
  ["Network Nodes", "network_nodes"],
  ["Network Edges", "network_edges"],
  ["Network Density", "network_density"],
  ["Connected Components", "connected_components"],
  ["High Risk Zones", "high_risk_zones"],
];

export default function OverviewPage() {
  const [data, setData] = useState<Overview | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchJson<Overview>("/api/overview").then(setData).catch((fetchError: Error) => setError(fetchError.message));
  }, []);

  return (
    <main className="page">
      <header className="topbar">
        <h1>Overview Dashboard</h1>
        <p>Project-level epidemic, classification, and network indicators from exported analysis data.</p>
      </header>
      {error ? <div className="status">Unable to load overview: {error}</div> : null}
      {!error && !data ? <div className="status">Loading overview...</div> : null}
      {data ? (
        <section className="content grid">
          {cards.map(([label, key]) => (
            <article className="metricCard" key={key}>
              <span>{label}</span>
              <strong>{formatValue(data[key])}</strong>
            </article>
          ))}
        </section>
      ) : null}
    </main>
  );
}
