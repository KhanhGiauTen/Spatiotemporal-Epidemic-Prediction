"""Publish aggregate analysis outputs only, using the existing FastAPI service."""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.api.main import clusters, network_summary, overview, risk_polygons


if __name__ == "__main__":
    cluster_snapshot = clusters()
    public_clusters = sorted((row for row in cluster_snapshot["cluster_records"] if (row.get("record_count") or 0) >= 20), key=lambda row: row["record_count"], reverse=True)[:50]
    cluster_snapshot["total_analyzed_clusters"] = cluster_snapshot["number_of_clusters"]
    cluster_snapshot["number_of_clusters"] = len(public_clusters)
    cluster_snapshot["cluster_records"] = public_clusters
    cluster_snapshot["top_high_risk_clusters"] = sorted(public_clusters, key=lambda row: row["risk_score"], reverse=True)[:5]
    cluster_snapshot["note"] = "Public excerpt: up to 50 aggregate clusters with at least 20 records. No individual rows or identifiers. Centroid coordinates are unavailable."
    snapshot = {
        "overview": overview(),
        "clusters": cluster_snapshot,
        "network-summary": network_summary(),
        "risk-polygons": risk_polygons(),
    }
    assert snapshot["overview"]["total_records"] > 0
    assert snapshot["clusters"]["number_of_clusters"] > 0
    output = ROOT / "web-map" / "data" / "public-demo.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(snapshot, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    print("Exported aggregate-only demo snapshot; no individual records or node IDs")
