"""
Lightweight clustering utilities for Task 9: Ground Zero Clustering.
Provides functions to load Fact_Exposure via SQLAlchemy, prepare features,
run K-Means / DBSCAN, extract weighted centroids, and export results.

Usage (from repository root):
python -m src.clustering --db-url "sqlite:///db.sqlite" --kmeans 4

This module is intentionally conservative about schema assumptions and will
work with or without latitude/longitude if grid/location keys exist.
"""
from pathlib import Path
import argparse
import warnings

import pandas as pd
import numpy as np

try:
    from sqlalchemy import create_engine
except Exception as e:
    create_engine = None

from sklearn.preprocessing import StandardScaler, OneHotEncoder
from sklearn.compose import ColumnTransformer
from sklearn.pipeline import Pipeline
from sklearn.cluster import KMeans, DBSCAN


REPORT_DIR = Path("reports")
FIGURE_DIR = REPORT_DIR / "figures"
REPORT_DIR.mkdir(exist_ok=True)
FIGURE_DIR.mkdir(exist_ok=True)


def load_fact_exposure(sqlalchemy_url: str, query: str = None) -> pd.DataFrame:
    if create_engine is None:
        raise RuntimeError("SQLAlchemy is required to load from SQL. Install sqlalchemy.")
    engine = create_engine(sqlalchemy_url)
    if query is None:
        query = "SELECT * FROM Fact_Exposure"
    df = pd.read_sql(query, engine)
    return df


def prepare_clustering_features(df: pd.DataFrame,
                                numeric_features=None,
                                categorical_features=None) -> (pd.DataFrame, Pipeline):
    df = df.copy()
    if numeric_features is None:
        numeric_features = [c for c in df.columns if pd.api.types.is_numeric_dtype(df[c])]
        preferred = ["count_exposure", "support", "contacts", "contacts_infected", "month_id", "duration_sec", "no_ts", "hcir", "hh_ar"]
        ordered = [c for c in preferred if c in numeric_features]
        remaining = [c for c in numeric_features if c not in ordered]
        numeric_features = ordered + remaining
    if categorical_features is None:
        categorical_features = [c for c in df.columns if df[c].dtype == "object" or str(df[c].dtype).startswith("category")]

    # If lat/lon present, prefer them for spatial clustering
    spatial = []
    for col in ("latitude", "longitude", "lat", "lon"):
        if col in df.columns:
            spatial.append(col)
    # ensure spatial columns are numeric
    numeric_features = list(dict.fromkeys(spatial + numeric_features))

    # Build ColumnTransformer
    transformers = []
    if numeric_features:
        transformers.append(("num", StandardScaler(), numeric_features))
    if categorical_features:
        transformers.append(("cat", OneHotEncoder(handle_unknown="ignore", sparse_output=False), categorical_features))

    if not transformers:
        raise ValueError("No suitable features found for clustering")

    preprocessor = ColumnTransformer(transformers=transformers)
    X = preprocessor.fit_transform(df)

    return df, X, preprocessor, numeric_features, categorical_features


def run_kmeans(X, n_clusters=4, random_state=42, **kwargs):
    k = KMeans(n_clusters=n_clusters, random_state=random_state, n_init=kwargs.get("n_init", 20))
    labels = k.fit_predict(X)
    return k, labels


def run_dbscan(X, eps=0.8, min_samples=5, **kwargs):
    db = DBSCAN(eps=eps, min_samples=min_samples)
    labels = db.fit_predict(X)
    return db, labels


def extract_weighted_centroids(df: pd.DataFrame, labels: pd.Series, coord_cols=None, weight_col="count_exposure") -> pd.DataFrame:
    df = df.copy()
    df["_cluster"] = labels
    rows = []
    for cid, group in df.groupby("_cluster"):
        if cid == -1:
            continue
        row = {
            "cluster_id": int(cid),
            "n_cells": int(len(group)),
            "total_exposure": float(group.get(weight_col, pd.Series(0)).sum()),
            "avg_exposure": float(group.get(weight_col, pd.Series(0)).mean()) if len(group) else 0.0,
        }
        if coord_cols:
            for col in coord_cols:
                if col in group.columns:
                    weights = group.get(weight_col, None)
                    if weights is None or weights.sum() == 0:
                        val = group[col].mean()
                    else:
                        val = np.average(group[col].astype(float), weights=weights.astype(float))
                    row[f"centroid_{col}"] = float(val)
        rows.append(row)
    return pd.DataFrame(rows)


def export_results(df: pd.DataFrame, centroids: pd.DataFrame, prefix="ground_zero"):
    REPORT_DIR.mkdir(exist_ok=True)
    df.to_csv(REPORT_DIR / f"{prefix}_clustered_cuboids.csv", index=False)
    centroids.to_csv(REPORT_DIR / f"{prefix}_centroids.csv", index=False)


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--db-url", required=True, help="SQLAlchemy database URL to load Fact_Exposure")
    parser.add_argument("--kmeans", type=int, default=0, help="Run KMeans with this k (0 to skip)")
    parser.add_argument("--dbscan", action="store_true", help="Run DBSCAN")
    parser.add_argument("--eps", type=float, default=0.8, help="DBSCAN eps")
    parser.add_argument("--min-samples", type=int, default=5, help="DBSCAN min_samples")
    parser.add_argument("--kmeans-k", type=int, default=4, help="KMeans k")
    args = parser.parse_args(argv)

    df = load_fact_exposure(args.db_url)
    print(f"Loaded Fact_Exposure: {df.shape[0]} rows")

    df_pre, X, preproc, numeric_features, categorical_features = prepare_clustering_features(df)
    print("Prepared features:", numeric_features, "+", ", ".join(categorical_features) if categorical_features else "")

    if args.kmeans:
        _, klabels = run_kmeans(X, n_clusters=args.kmeans_k)
        df_pre["kmeans_cluster"] = klabels
        coord_cols = [c for c in ("latitude", "longitude") if c in df_pre.columns]
        centroids = extract_weighted_centroids(df_pre, klabels, coord_cols=coord_cols)
        export_results(df_pre, centroids, prefix="ground_zero_kmeans")
        print("KMeans done. Results exported to reports/")

    if args.dbscan:
        _, dlabels = run_dbscan(X, eps=args.eps, min_samples=args.min_samples)
        df_pre["dbscan_cluster"] = dlabels
        coord_cols = [c for c in ("latitude", "longitude") if c in df_pre.columns]
        centroids = extract_weighted_centroids(df_pre, dlabels, coord_cols=coord_cols)
        export_results(df_pre, centroids, prefix="ground_zero_dbscan")
        print("DBSCAN done. Results exported to reports/")


if __name__ == "__main__":
    main()


__all__ = [
    "load_fact_exposure",
    "prepare_clustering_features",
    "run_kmeans",
    "run_dbscan",
    "extract_weighted_centroids",
    "export_results",
    "main",
]