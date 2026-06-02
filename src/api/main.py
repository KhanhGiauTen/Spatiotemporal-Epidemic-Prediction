"""FastAPI service for the Task 13 epidemic monitoring application.

The project currently contains model and analysis outputs in CSV form, but no
real administrative boundary geometry. The risk-map endpoint therefore creates
deterministic visual polygons from cluster output rows. These polygons are demo
zones for visualization only and should be replaced when real boundaries are
available.
"""

from __future__ import annotations

import csv
import math
from pathlib import Path
from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field


PROJECT_ROOT = Path(__file__).resolve().parents[2]
POWERBI_DATA = PROJECT_ROOT / "powerbi" / "data"

CLUSTER_SUMMARY_PATH = POWERBI_DATA / "ground_zero_clusters.csv"
CLASSIFICATION_METRICS_PATH = POWERBI_DATA / "classification_metrics.csv"
CONFUSION_MATRIX_PATH = POWERBI_DATA / "classification_confusion_matrix.csv"
FEATURE_IMPORTANCE_PATH = POWERBI_DATA / "classification_feature_importance.csv"
CONTACT_NETWORK_SUMMARY_PATH = POWERBI_DATA / "contact_network_summary.csv"
HIGH_RISK_NODES_PATH = POWERBI_DATA / "high_risk_nodes.csv"
OVERVIEW_KPIS_PATH = POWERBI_DATA / "overview_kpis.csv"


app = FastAPI(
    title="Spatiotemporal Epidemic Prediction API",
    description="Serves epidemic monitoring metrics, demo predictions, and GeoJSON risk zones.",
    version="0.2.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class PredictionInput(BaseModel):
    """Input fields for the deterministic demo outbreak predictor."""

    contacts: float = Field(ge=0)
    duration: float = Field(ge=0, description="Average exposure duration in seconds.")
    household_size: float = Field(ge=0)
    hcir: float = Field(ge=0, le=100, description="Household contact infection risk percentage.")
    location_risk_score: float = Field(ge=0, le=1)


def _read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8", newline="") as csv_file:
        rows = []
        for row in csv.DictReader(csv_file):
            rows.append({key.lstrip("\ufeff").strip(): value for key, value in row.items()})
        return rows


def _read_metric_csv(path: Path) -> dict[str, Any]:
    rows = _read_csv(path)
    return {row.get("metric", ""): _coerce_value(row.get("value")) for row in rows if row.get("metric")}


def _read_first_row(path: Path) -> dict[str, Any]:
    rows = _read_csv(path)
    if not rows:
        return {}
    return {key: _coerce_value(value) for key, value in rows[0].items()}


def _coerce_value(value: str | None) -> Any:
    if value in (None, ""):
        return None
    text = str(value).strip()
    try:
        if "." not in text and "e" not in text.lower():
            return int(text)
        return float(text)
    except ValueError:
        return text


def _to_float(value: Any, default: float = 0.0) -> float:
    if value in (None, ""):
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _risk_level(score: float) -> str:
    if score >= 0.75:
        return "high"
    if score >= 0.45:
        return "medium"
    return "low"


def _cluster_risk_score(row: dict[str, Any], max_records: float) -> float:
    hcir = _to_float(row.get("avg_hcir"))
    household_attack_rate = _to_float(row.get("avg_hh_ar"))
    infected = _to_float(row.get("total_contacts_infected"))
    contacts = _to_float(row.get("total_contacts"))
    infected_share = infected / contacts if contacts else 0.0
    record_weight = _to_float(row.get("record_count")) / max_records if max_records else 0.0
    return round(((hcir / 100) * 0.38) + ((household_attack_rate / 100) * 0.3) + (infected_share * 0.2) + (record_weight * 0.12), 3)


def _cluster_rows() -> list[dict[str, Any]]:
    raw_rows = _read_csv(CLUSTER_SUMMARY_PATH)
    max_records = max((_to_float(row.get("record_count")) for row in raw_rows), default=1.0) or 1.0
    rows: list[dict[str, Any]] = []

    for row in raw_rows:
        normalized = {key: _coerce_value(value) for key, value in row.items()}
        score = _cluster_risk_score(normalized, max_records)
        normalized["risk_score"] = score
        normalized["risk_level"] = _risk_level(score)
        normalized["predicted_outbreak"] = score >= 0.65
        rows.append(normalized)

    return rows


def _sample_zone(index: int, radius: float = 0.62, points: int = 12) -> list[list[float]]:
    """Return a larger circle-like polygon around Vietnam for demo display."""

    centers = [
        (106.70, 10.78),
        (105.85, 21.03),
        (108.22, 16.05),
        (106.05, 20.85),
        (107.58, 16.46),
        (104.98, 11.55),
        (105.78, 10.04),
        (109.19, 12.24),
    ]
    lng, lat = centers[index % len(centers)]
    offset = (index // len(centers)) * 0.12
    lng += offset
    lat += offset
    coordinates = []

    for point_index in range(points):
        angle = (2 * math.pi * point_index) / points
        coordinates.append([round(lng + (math.cos(angle) * radius), 6), round(lat + (math.sin(angle) * radius), 6)])

    coordinates.append(coordinates[0])
    return coordinates


def build_risk_geojson() -> dict[str, Any]:
    rows = _cluster_rows()
    if not rows:
        rows = [
            {
                "algorithm": "Placeholder",
                "cluster_id": 0,
                "risk_score": 0.82,
                "risk_level": "high",
                "predicted_outbreak": True,
            }
        ]

    features = []
    for index, row in enumerate(rows[:8]):
        algorithm = row.get("algorithm") or "Cluster"
        cluster_id = row.get("cluster_id", index)
        features.append(
            {
                "type": "Feature",
                "properties": {
                    "region": f"{algorithm} cluster {cluster_id}",
                    "risk_level": row.get("risk_level"),
                    "risk_score": row.get("risk_score"),
                    "predicted_outbreak": row.get("predicted_outbreak"),
                    "cluster_id": cluster_id,
                    "source": "powerbi/data/ground_zero_clusters.csv",
                },
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [_sample_zone(index)],
                },
            }
        )

    return {
        "type": "FeatureCollection",
        "metadata": {
            "source": "powerbi/data/ground_zero_clusters.csv",
            "placeholder_geometry": True,
            "note": "Generated polygons are deterministic visual zones from cluster outputs because real boundary geometry is not available yet.",
        },
        "features": features,
    }


def _top_high_risk_clusters(limit: int = 5) -> list[dict[str, Any]]:
    rows = sorted(_cluster_rows(), key=lambda row: _to_float(row.get("risk_score")), reverse=True)
    return rows[:limit]


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/risk-polygons")
def risk_polygons() -> dict[str, Any]:
    return build_risk_geojson()


@app.get("/api/overview")
def overview() -> dict[str, Any]:
    overview_row = _read_first_row(OVERVIEW_KPIS_PATH)
    classification = _read_metric_csv(CLASSIFICATION_METRICS_PATH)
    network = _read_metric_csv(CONTACT_NETWORK_SUMMARY_PATH)
    clusters = _cluster_rows()

    return {
        "total_records": overview_row.get("total_records"),
        "total_contacts": overview_row.get("total_contacts"),
        "infected_contacts": overview_row.get("total_infected_contacts"),
        "classification_accuracy": classification.get("accuracy", overview_row.get("classification_accuracy")),
        "precision": classification.get("precision_binary"),
        "recall": classification.get("recall_binary"),
        "f1_score": classification.get("f1_binary", overview_row.get("classification_f1_binary")),
        "network_nodes": network.get("num_nodes", overview_row.get("network_nodes")),
        "network_edges": network.get("num_edges", overview_row.get("network_edges")),
        "network_density": network.get("density", overview_row.get("network_density")),
        "connected_components": network.get("num_connected_components", overview_row.get("network_components")),
        "number_of_clusters": len(clusters) if clusters else None,
        "high_risk_zones": len([row for row in clusters if row.get("predicted_outbreak")]) if clusters else None,
        "unavailable_values": "Missing source files return null values or empty arrays.",
    }


@app.get("/api/classification")
def classification() -> dict[str, Any]:
    metrics = _read_metric_csv(CLASSIFICATION_METRICS_PATH)
    confusion_matrix = [{key: _coerce_value(value) for key, value in row.items()} for row in _read_csv(CONFUSION_MATRIX_PATH)]
    feature_importance = [{key: _coerce_value(value) for key, value in row.items()} for row in _read_csv(FEATURE_IMPORTANCE_PATH)]

    return {
        "model_name": "Random Forest",
        "accuracy": metrics.get("accuracy"),
        "precision": metrics.get("precision_binary"),
        "recall": metrics.get("recall_binary"),
        "f1_score": metrics.get("f1_binary"),
        "confusion_matrix": confusion_matrix,
        "feature_importance": feature_importance,
    }


@app.get("/api/clusters")
def clusters() -> dict[str, Any]:
    rows = _cluster_rows()
    return {
        "number_of_clusters": len(rows) if rows else 0,
        "cluster_records": rows,
        "kmeans_centroids": None,
        "dbscan_centroids": None,
        "top_high_risk_clusters": _top_high_risk_clusters(),
        "note": "Centroid coordinate files are not available in current outputs; values are null.",
    }


@app.get("/api/network-summary")
def network_summary() -> dict[str, Any]:
    network = _read_metric_csv(CONTACT_NETWORK_SUMMARY_PATH)
    return {
        "nodes": network.get("num_nodes"),
        "edges": network.get("num_edges"),
        "density": network.get("density"),
        "connected_components": network.get("num_connected_components"),
        "largest_component_size": network.get("largest_component_size"),
        "node_strategy": network.get("node_strategy"),
    }


@app.get("/api/top-risk-nodes")
def top_risk_nodes(limit: int = 15) -> dict[str, Any]:
    rows = [{key: _coerce_value(value) for key, value in row.items()} for row in _read_csv(HIGH_RISK_NODES_PATH)]
    rows = sorted(rows, key=lambda row: _to_float(row.get("risk_score")), reverse=True)
    return {
        "nodes": rows[: max(1, min(limit, 100))],
        "source": "powerbi/data/high_risk_nodes.csv",
    }


@app.post("/api/predict")
def predict(payload: PredictionInput) -> dict[str, Any]:
    """Return a documented deterministic demo prediction, not a trained model."""

    contact_factor = min(payload.contacts / 60, 1.0)
    duration_factor = min(payload.duration / 120, 1.0)
    household_factor = min(payload.household_size / 8, 1.0)
    hcir_factor = payload.hcir / 100
    location_factor = payload.location_risk_score
    probability = round(
        (contact_factor * 0.24)
        + (duration_factor * 0.18)
        + (household_factor * 0.14)
        + (hcir_factor * 0.28)
        + (location_factor * 0.16),
        3,
    )
    level = _risk_level(probability)

    return {
        "predicted_outbreak": probability >= 0.65,
        "risk_level": level,
        "probability": probability,
        "explanation": (
            "Demo heuristic only: probability is a weighted score using contacts, exposure duration, "
            "household size, HCIR, and location risk. It does not retrain or call the classification model."
        ),
    }
