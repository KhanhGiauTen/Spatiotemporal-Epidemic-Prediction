"use client";

import { useEffect } from "react";
import { GeoJSON, MapContainer, TileLayer, useMap } from "react-leaflet";
import type { FeatureCollection, Geometry } from "geojson";
import type { LeafletMouseEvent, PathOptions } from "leaflet";
import L from "leaflet";

type RiskProperties = {
  region: string;
  risk_level: string;
  risk_score: number;
  predicted_outbreak: boolean;
  cluster_id: string | number;
  source: string;
};

type RiskGeoJson = FeatureCollection<Geometry, RiskProperties>;

function FitBounds({ data }: { data: RiskGeoJson }) {
  const map = useMap();

  useEffect(() => {
    const bounds = L.geoJSON(data).getBounds();
    if (bounds.isValid()) {
      map.fitBounds(bounds, { padding: [24, 24] });
    }
  }, [data, map]);

  return null;
}

function polygonStyle(): PathOptions {
  return {
    color: "#991b1b",
    fillColor: "#ef4444",
    fillOpacity: 0.45,
    opacity: 0.95,
    weight: 2,
  };
}

export default function RiskMapView({ data }: { data: RiskGeoJson }) {
  return (
    <MapContainer className="map" center={[16.05, 106.7]} zoom={6} scrollWheelZoom>
      <TileLayer
        attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
        url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
      />
      <GeoJSON
        data={data}
        style={polygonStyle}
        onEachFeature={(feature, layer) => {
          const properties = feature.properties as RiskProperties;
          layer.bindPopup(
            `<div class="popupTitle">${properties.region}</div>` +
              `<div class="popupRow">Risk level: ${properties.risk_level}</div>` +
              `<div class="popupRow">Risk score: ${properties.risk_score}</div>` +
              `<div class="popupRow">Predicted outbreak: ${properties.predicted_outbreak ? "yes" : "no"}</div>` +
              `<div class="popupRow">Cluster ID: ${properties.cluster_id}</div>`
          );
          layer.on("mouseover", (event: LeafletMouseEvent) => {
            event.target.setStyle({ fillOpacity: 0.65, weight: 3 });
          });
          layer.on("mouseout", (event: LeafletMouseEvent) => {
            event.target.setStyle(polygonStyle());
          });
        }}
      />
      <FitBounds data={data} />
    </MapContainer>
  );
}
