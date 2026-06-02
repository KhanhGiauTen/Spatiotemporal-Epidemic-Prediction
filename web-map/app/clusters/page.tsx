"use client";

import { useEffect, useState } from "react";
import { fetchJson, formatValue } from "../api";

type ClusterRow = Record<string, number | string | boolean | null>;

type ClusterResponse = {
  number_of_clusters: number;
  cluster_records: ClusterRow[];
  kmeans_centroids: ClusterRow[] | null;
  dbscan_centroids: ClusterRow[] | null;
  top_high_risk_clusters: ClusterRow[];
  note: string;
};

const columns = ["algorithm", "cluster_id", "record_count", "total_contacts", "total_contacts_infected", "avg_hcir", "risk_score", "risk_level"];

export default function ClustersPage() {
  const [data, setData] = useState<ClusterResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchJson<ClusterResponse>("/api/clusters").then(setData).catch((fetchError: Error) => setError(fetchError.message));
  }, []);

  return (
    <main className="page">
      <header className="topbar">
        <h1>Cluster Explorer</h1>
        <p>Browse K-Means and DBSCAN cluster summaries with computed demo risk scores.</p>
      </header>
      {error ? <div className="status">Unable to load clusters: {error}</div> : null}
      {data ? (
        <section className="content">
          <div className="summaryLine">Number of clusters: {formatValue(data.number_of_clusters, 0)}</div>
          <h2>Top High-Risk Clusters</h2>
          <DataTable columns={columns} rows={data.top_high_risk_clusters} />
          <h2>All Cluster Records</h2>
          <DataTable columns={columns} rows={data.cluster_records} />
          <p className="muted">{data.note}</p>
        </section>
      ) : !error ? (
        <div className="status">Loading clusters...</div>
      ) : null}
    </main>
  );
}

function DataTable({ columns, rows }: { columns: string[]; rows: ClusterRow[] }) {
  return (
    <div className="tableWrap">
      <table>
        <thead>
          <tr>{columns.map((column) => <th key={column}>{column.replaceAll("_", " ")}</th>)}</tr>
        </thead>
        <tbody>
          {rows.map((row, index) => (
            <tr key={index}>
              {columns.map((column) => <td key={column}>{formatValue(row[column])}</td>)}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
