"use client";

import { useEffect, useState } from "react";
import { fetchJson, formatValue } from "../api";

type Summary = Record<string, number | string | null>;
type NodeRow = Record<string, number | string | null>;

const nodeColumns = ["risk_rank", "node_id", "degree", "weighted_degree", "degree_centrality", "betweenness_centrality", "risk_score"];

export default function NetworkPage() {
  const [summary, setSummary] = useState<Summary | null>(null);
  const [nodes, setNodes] = useState<NodeRow[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([fetchJson<Summary>("/api/network-summary"), fetchJson<{ nodes: NodeRow[] }>("/api/top-risk-nodes")])
      .then(([summaryData, nodeData]) => {
        setSummary(summaryData);
        setNodes(nodeData.nodes);
      })
      .catch((fetchError: Error) => setError(fetchError.message));
  }, []);

  return (
    <main className="page">
      <header className="topbar">
        <h1>Contact Network Explorer</h1>
        <p>Inspect network structure and top risk nodes from Task 11 outputs.</p>
      </header>
      {error ? <div className="status">Unable to load network data: {error}</div> : null}
      {summary ? (
        <section className="content">
          <div className="grid compact">
            {["nodes", "edges", "density", "connected_components", "largest_component_size"].map((key) => (
              <article className="metricCard" key={key}>
                <span>{key.replaceAll("_", " ")}</span>
                <strong>{formatValue(summary[key])}</strong>
              </article>
            ))}
          </div>
          <h2>Top Risk Nodes</h2>
          <div className="tableWrap">
            <table>
              <thead>
                <tr>{nodeColumns.map((column) => <th key={column}>{column.replaceAll("_", " ")}</th>)}</tr>
              </thead>
              <tbody>
                {nodes.map((row, index) => (
                  <tr key={index}>{nodeColumns.map((column) => <td key={column}>{formatValue(row[column])}</td>)}</tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      ) : !error ? (
        <div className="status">Loading network data...</div>
      ) : null}
    </main>
  );
}
