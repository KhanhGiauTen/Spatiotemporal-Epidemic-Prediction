"""Prepare Power BI-ready CSV datasets for Task 12.

The script reads processed project outputs from data/processed/ and reports/,
then exports small, import-friendly CSV tables to powerbi/data/.

Usage:
    python scripts/prepare_powerbi_data.py --project-root .
"""
from __future__ import annotations

import argparse
import json
import warnings
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

import pandas as pd


NA_VALUE = "N/A"


def warn(message: str) -> None:
    """Print a visible warning without stopping the whole preparation run."""
    warnings.warn(message, RuntimeWarning, stacklevel=2)


def ensure_output_dir(project_root: Path) -> Path:
    output_dir = project_root / "powerbi" / "data"
    output_dir.mkdir(parents=True, exist_ok=True)
    return output_dir


def read_csv_optional(path: Path, label: str) -> Optional[pd.DataFrame]:
    if not path.exists():
        warn(f"Missing {label}: {path}")
        return None

    try:
        return pd.read_csv(path)
    except Exception as exc:  # pragma: no cover - defensive IO branch
        warn(f"Could not read {label} at {path}: {exc}")
        return None


def read_json_optional(path: Path, label: str) -> Dict[str, Any]:
    if not path.exists():
        warn(f"Missing {label}: {path}")
        return {}

    try:
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as exc:  # pragma: no cover - defensive IO branch
        warn(f"Could not read {label} at {path}: {exc}")
        return {}


def write_csv(df: pd.DataFrame, output_dir: Path, filename: str) -> None:
    path = output_dir / filename
    df.to_csv(path, index=False, encoding="utf-8-sig")
    print(f"[OK] Wrote {path}")


def safe_metric(metrics: Dict[str, Any], key: str, default: Any = NA_VALUE) -> Any:
    value = metrics.get(key, default)
    if value is None:
        return default
    if isinstance(value, (list, dict)):
        return json.dumps(value, ensure_ascii=False)
    return value


def numeric_columns(df: pd.DataFrame, candidates: Iterable[str]) -> List[str]:
    return [col for col in candidates if col in df.columns and pd.api.types.is_numeric_dtype(df[col])]


def prepare_overview_kpis(
    processed_df: Optional[pd.DataFrame],
    metrics: Dict[str, Any],
    graph_summary: Dict[str, Any],
    output_dir: Path,
) -> None:
    row: Dict[str, Any] = {
        "total_records": NA_VALUE,
        "total_months": NA_VALUE,
        "min_month_id": NA_VALUE,
        "max_month_id": NA_VALUE,
        "total_contacts": NA_VALUE,
        "total_infected_contacts": NA_VALUE,
        "transmission_records": NA_VALUE,
        "avg_duration_sec": NA_VALUE,
        "classification_accuracy": safe_metric(metrics, "accuracy"),
        "classification_f1_binary": safe_metric(metrics, "f1_binary"),
        "classification_train_rows": safe_metric(metrics, "train_rows"),
        "classification_test_rows": safe_metric(metrics, "test_rows"),
        "network_nodes": graph_summary.get("num_nodes", NA_VALUE),
        "network_edges": graph_summary.get("num_edges", NA_VALUE),
        "network_density": graph_summary.get("density", NA_VALUE),
        "network_components": graph_summary.get("num_connected_components", NA_VALUE),
    }

    if processed_df is not None and not processed_df.empty:
        row["total_records"] = int(len(processed_df))
        if "month_id" in processed_df.columns:
            row["total_months"] = int(processed_df["month_id"].nunique())
            row["min_month_id"] = processed_df["month_id"].min()
            row["max_month_id"] = processed_df["month_id"].max()
        if "contacts" in processed_df.columns:
            row["total_contacts"] = float(processed_df["contacts"].sum())
        if "contacts_infected" in processed_df.columns:
            row["total_infected_contacts"] = float(processed_df["contacts_infected"].sum())
        if "pair_sars" in processed_df.columns:
            row["transmission_records"] = int((processed_df["pair_sars"] == 2).sum())
        if "duration_sec" in processed_df.columns:
            row["avg_duration_sec"] = float(processed_df["duration_sec"].mean())

    write_csv(pd.DataFrame([row]), output_dir, "overview_kpis.csv")


def prepare_exposure_summary(processed_df: Optional[pd.DataFrame], output_dir: Path) -> None:
    columns = [
        "month_id",
        "pair_sars",
        "record_count",
        "total_contacts",
        "total_contacts_infected",
        "avg_duration_sec",
        "avg_hcir",
        "avg_hh_ar",
    ]

    if processed_df is None or processed_df.empty:
        write_csv(pd.DataFrame(columns=columns), output_dir, "exposure_summary.csv")
        return

    group_cols = [col for col in ["month_id", "pair_sars"] if col in processed_df.columns]
    if not group_cols:
        warn("Cannot build exposure_summary.csv because month_id/pair_sars columns are unavailable.")
        write_csv(pd.DataFrame(columns=columns), output_dir, "exposure_summary.csv")
        return

    summary = processed_df.groupby(group_cols, dropna=False).size().reset_index(name="record_count")

    aggregations = {
        "contacts": "sum",
        "contacts_infected": "sum",
        "duration_sec": "mean",
        "hcir": "mean",
        "hh_ar": "mean",
    }
    available_aggs = {col: agg for col, agg in aggregations.items() if col in processed_df.columns}

    if available_aggs:
        agg_df = processed_df.groupby(group_cols, dropna=False).agg(available_aggs).reset_index()
        summary = summary.merge(agg_df, on=group_cols, how="left")

    summary = summary.rename(
        columns={
            "contacts": "total_contacts",
            "contacts_infected": "total_contacts_infected",
            "duration_sec": "avg_duration_sec",
            "hcir": "avg_hcir",
            "hh_ar": "avg_hh_ar",
        }
    )

    for col in columns:
        if col not in summary.columns:
            summary[col] = pd.NA

    write_csv(summary[columns], output_dir, "exposure_summary.csv")


def prepare_cube_analytics(project_root: Path, output_dir: Path) -> None:
    clustered_path = project_root / "reports" / "ground_zero_clustered_cuboids.csv"
    df = read_csv_optional(clustered_path, "ground zero clustered cuboids")

    output_columns = [
        "month_id",
        "ind1_site",
        "ind2_site",
        "pair_sars",
        "kmeans_cluster",
        "dbscan_cluster",
        "cuboid_count",
        "total_contacts",
        "total_contacts_infected",
        "avg_duration_sec",
        "avg_hcir",
        "avg_hh_ar",
    ]

    if df is None or df.empty:
        write_csv(pd.DataFrame(columns=output_columns), output_dir, "cube_analytics.csv")
        return

    group_cols = [
        col
        for col in ["month_id", "ind1_site", "ind2_site", "pair_sars", "kmeans_cluster", "dbscan_cluster"]
        if col in df.columns
    ]

    if not group_cols:
        warn("Cannot build cube_analytics.csv because no cube grouping columns are available.")
        write_csv(pd.DataFrame(columns=output_columns), output_dir, "cube_analytics.csv")
        return

    cube = df.groupby(group_cols, dropna=False).size().reset_index(name="cuboid_count")
    available_aggs = {
        col: agg
        for col, agg in {
            "contacts": "sum",
            "contacts_infected": "sum",
            "duration_sec": "mean",
            "hcir": "mean",
            "hh_ar": "mean",
        }.items()
        if col in df.columns
    }

    if available_aggs:
        measures = df.groupby(group_cols, dropna=False).agg(available_aggs).reset_index()
        cube = cube.merge(measures, on=group_cols, how="left")

    cube = cube.rename(
        columns={
            "contacts": "total_contacts",
            "contacts_infected": "total_contacts_infected",
            "duration_sec": "avg_duration_sec",
            "hcir": "avg_hcir",
            "hh_ar": "avg_hh_ar",
        }
    )

    for col in output_columns:
        if col not in cube.columns:
            cube[col] = pd.NA

    write_csv(cube[output_columns], output_dir, "cube_analytics.csv")


def prepare_ground_zero_clusters(project_root: Path, output_dir: Path) -> None:
    clustered_path = project_root / "reports" / "ground_zero_clustered_cuboids.csv"
    dbscan_centroids_path = project_root / "reports" / "ground_zero_dbscan_centroids.csv"
    kmeans_centroids_path = project_root / "reports" / "ground_zero_kmeans_centroids.csv"

    clustered = read_csv_optional(clustered_path, "ground zero clustered cuboids")
    cluster_rows: List[pd.DataFrame] = []

    if clustered is not None and not clustered.empty:
        for cluster_col in ["kmeans_cluster", "dbscan_cluster"]:
            if cluster_col not in clustered.columns:
                continue

            group_cols = [cluster_col]
            summary = clustered.groupby(group_cols, dropna=False).size().reset_index(name="record_count")
            for source_col, output_col, agg in [
                ("contacts", "total_contacts", "sum"),
                ("contacts_infected", "total_contacts_infected", "sum"),
                ("duration_sec", "avg_duration_sec", "mean"),
                ("hcir", "avg_hcir", "mean"),
                ("hh_ar", "avg_hh_ar", "mean"),
            ]:
                if source_col in clustered.columns:
                    measure = clustered.groupby(group_cols, dropna=False)[source_col].agg(agg).reset_index(name=output_col)
                    summary = summary.merge(measure, on=group_cols, how="left")

            summary = summary.rename(columns={cluster_col: "cluster_id"})
            summary["algorithm"] = "KMeans" if cluster_col == "kmeans_cluster" else "DBSCAN"
            cluster_rows.append(summary)

    for path, algorithm in [(kmeans_centroids_path, "KMeans"), (dbscan_centroids_path, "DBSCAN")]:
        centroids = read_csv_optional(path, f"{algorithm} centroids")
        if centroids is not None and not centroids.empty:
            centroids = centroids.copy()
            centroids["algorithm"] = algorithm
            if "cluster_id" not in centroids.columns:
                centroids["cluster_id"] = pd.NA
            cluster_rows.append(centroids)

    if not cluster_rows:
        output = pd.DataFrame(
            columns=[
                "algorithm",
                "cluster_id",
                "record_count",
                "total_contacts",
                "total_contacts_infected",
                "avg_duration_sec",
                "avg_hcir",
                "avg_hh_ar",
                "n_cells",
                "total_exposure",
                "avg_exposure",
            ]
        )
    else:
        output = pd.concat(cluster_rows, ignore_index=True, sort=False)
        preferred = ["algorithm", "cluster_id"]
        remaining = [col for col in output.columns if col not in preferred]
        output = output[preferred + remaining]

    write_csv(output, output_dir, "ground_zero_clusters.csv")


def prepare_classification_outputs(project_root: Path, output_dir: Path, metrics: Dict[str, Any]) -> None:
    metric_rows = []
    metric_order = [
        "accuracy",
        "precision_macro",
        "recall_macro",
        "f1_macro",
        "precision_binary",
        "recall_binary",
        "f1_binary",
        "train_rows",
        "test_rows",
        "train_months",
        "test_months",
        "duplicate_feature_hashes_across_split",
    ]

    for key in metric_order:
        metric_rows.append({"metric": key, "value": safe_metric(metrics, key)})

    write_csv(pd.DataFrame(metric_rows), output_dir, "classification_metrics.csv")

    feature_importance = read_csv_optional(
        project_root / "reports" / "issue_10_outbreak_classification" / "feature_importance.csv",
        "classification feature importance",
    )
    if feature_importance is None:
        feature_importance = pd.DataFrame(columns=["feature", "importance"])
    write_csv(feature_importance, output_dir, "classification_feature_importance.csv")

    confusion = read_csv_optional(
        project_root / "reports" / "issue_10_outbreak_classification" / "confusion_matrix.csv",
        "classification confusion matrix",
    )
    if confusion is None or confusion.empty:
        output = pd.DataFrame(columns=["actual_class", "predicted_class", "count"])
    else:
        confusion = confusion.rename(columns={confusion.columns[0]: "actual_class"})
        output = confusion.melt(
            id_vars="actual_class",
            var_name="predicted_class",
            value_name="count",
        )
    write_csv(output, output_dir, "classification_confusion_matrix.csv")


def prepare_contact_network_outputs(
    project_root: Path,
    output_dir: Path,
    graph_summary: Dict[str, Any],
) -> None:
    summary_keys = [
        "node_strategy",
        "num_nodes",
        "num_edges",
        "density",
        "num_connected_components",
        "largest_component_size",
        "top_percent",
    ]
    summary = pd.DataFrame(
        [{"metric": key, "value": graph_summary.get(key, NA_VALUE)} for key in summary_keys]
    )
    write_csv(summary, output_dir, "contact_network_summary.csv")

    high_risk_nodes = read_csv_optional(
        project_root / "reports" / "issue_11_contact_network" / "top_5_percent_risk_nodes.csv",
        "high risk nodes",
    )
    if high_risk_nodes is None:
        high_risk_nodes = pd.DataFrame(
            columns=[
                "node_id",
                "degree",
                "weighted_degree",
                "degree_centrality",
                "betweenness_centrality",
                "duration_sum",
                "contacts_infected_sum",
                "risk_score",
                "risk_rank",
            ]
        )
    write_csv(high_risk_nodes, output_dir, "high_risk_nodes.csv")

    network_edges = read_csv_optional(
        project_root / "reports" / "issue_11_contact_network" / "edge_list.csv",
        "network edge list",
    )
    if network_edges is None:
        network_edges = pd.DataFrame(
            columns=["node_u", "node_v", "weight", "record_count", "duration_sum", "contacts_infected_sum"]
        )
    write_csv(network_edges, output_dir, "network_edges.csv")


def prepare_powerbi_data(project_root: Path) -> None:
    project_root = project_root.resolve()
    output_dir = ensure_output_dir(project_root)

    processed_df = read_csv_optional(
        project_root / "data" / "processed" / "sashts_final_dataset.csv",
        "processed SASHTS dataset",
    )
    metrics = read_json_optional(
        project_root / "reports" / "issue_10_outbreak_classification" / "metrics.json",
        "classification metrics JSON",
    )
    graph_summary = read_json_optional(
        project_root / "reports" / "issue_11_contact_network" / "graph_summary.json",
        "contact network graph summary JSON",
    )

    prepare_overview_kpis(processed_df, metrics, graph_summary, output_dir)
    prepare_exposure_summary(processed_df, output_dir)
    prepare_cube_analytics(project_root, output_dir)
    prepare_ground_zero_clusters(project_root, output_dir)
    prepare_classification_outputs(project_root, output_dir, metrics)
    prepare_contact_network_outputs(project_root, output_dir, graph_summary)

    print(f"\nPower BI data preparation completed. Output directory: {output_dir}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Prepare Power BI CSV datasets for Task 12.")
    parser.add_argument(
        "--project-root",
        default=".",
        help="Path to the repository root. Defaults to current working directory.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    prepare_powerbi_data(Path(args.project_root))


if __name__ == "__main__":
    main()
