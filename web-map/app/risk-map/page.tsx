"use client";

import { useEffect, useState } from "react";
import dynamic from "next/dynamic";
import type { FeatureCollection, Geometry } from "geojson";
import { fetchJson } from "../api";

type RiskProperties = {
  region: string;
  risk_level: string;
  risk_score: number;
  predicted_outbreak: boolean;
  cluster_id: string | number;
  source: string;
};

type RiskGeoJson = FeatureCollection<Geometry, RiskProperties>;

const RiskMapView = dynamic(() => import("../components/risk-map-view"), { ssr: false });

export default function RiskMapPage() {
  const [data, setData] = useState<RiskGeoJson | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchJson<RiskGeoJson>("/api/risk-polygons").then(setData).catch((fetchError: Error) => setError(fetchError.message));
  }, []);

  return (
    <main className="page">
      <header className="topbar">
        <h1>Interactive Risk Map</h1>
        <p>Illustrative geometry for coursework cluster outputs. These shapes are not real geographic outbreak boundaries.</p>
      </header>
      <section className="mapWrap">
        <div className="legend">
          <span className="legendSwatch" />
          illustrative cluster zones
        </div>
        {error ? <div className="status">Unable to load risk polygons: {error}</div> : null}
        {!error && !data ? <div className="status">Loading risk polygons...</div> : null}
        {data ? <RiskMapView data={data} /> : null}
      </section>
    </main>
  );
}
