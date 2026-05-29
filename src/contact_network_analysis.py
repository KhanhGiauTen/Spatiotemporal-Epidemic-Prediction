"""
Task 11: Contact network graph analysis

Creates a NetworkX graph from processed data, computes centrality metrics,
and exports top-risk nodes and edge list.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import networkx as nx
import numpy as np
import pandas as pd


REQUIRED_PROCESSED_COLUMNS = [
    "ind1_site",
    "ind1_sex",
    "ind1_index",
    "ind2_site",
    "ind2_sex",
    "ind2_index",
    "month_id",
    "duration_sec",
    "contacts",
]

OPTIONAL_EDGE_MEASURE_COLUMNS = [
    "contacts_infected",
    "pair_sars",
    "hcir",
    "hh_ar",
]

IND1_PROFILE_COLUMNS = [
    "ind1_site",
    "ind1_agegrp9",
    "ind1_sex",
    "ind1_index",
    "ind1_bmicat",
    "ind1_smokecignow1",
]

IND2_PROFILE_COLUMNS = [
    "ind2_site",
    "ind2_agegrp9",
    "ind2_sex",
    "ind2_index",
    "ind2_bmicat",
    "ind2_smokecignow1",
]

ID_CANDIDATE_PAIRS = [
    ("ind1_id", "ind2_id"),
    ("patient1_id", "patient2_id"),
    ("source_id", "target_id"),
    ("from_id", "to_id"),
    ("grid_id_1", "grid_id_2"),
    ("source_grid_id", "target_grid_id"),
]


def load_processed_data(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"Processed dataset not found: {path}")

    df = pd.read_csv(path)

    missing = [col for col in REQUIRED_PROCESSED_COLUMNS if col not in df.columns]
    if missing:
        raise ValueError(f"Processed dataset is missing required columns: {missing}")

    return df


def load_mapping(path: Optional[Path]) -> Dict:
    if path is None:
        return {}

    if not path.exists():
        raise FileNotFoundError(f"Mapping file not found: {path}")

    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def find_id_pair(df: pd.DataFrame) -> Optional[Tuple[str, str]]:
    for left_col, right_col in ID_CANDIDATE_PAIRS:
        if left_col in df.columns and right_col in df.columns:
            return left_col, right_col
    return None


def make_profile_id(row: pd.Series, columns: List[str], prefix: str) -> str:
    values = [str(row.get(col, "NA")) for col in columns]
    return prefix + "::" + "|".join(values)


def add_node_columns(df: pd.DataFrame) -> Tuple[pd.DataFrame, str]:
    df = df.copy()

    id_pair = find_id_pair(df)
    if id_pair is not None:
        left_col, right_col = id_pair
        df["node_u"] = df[left_col].astype(str)
        df["node_v"] = df[right_col].astype(str)
        node_strategy = f"explicit_id:{left_col},{right_col}"
        return df, node_strategy

    df["node_u"] = df.apply(
        lambda row: make_profile_id(row, IND1_PROFILE_COLUMNS, "ind1_profile"), axis=1
    )
    df["node_v"] = df.apply(
        lambda row: make_profile_id(row, IND2_PROFILE_COLUMNS, "ind2_profile"), axis=1
    )
    node_strategy = "profile_nodes_from_encoded_individual_attributes"
    return df, node_strategy


def build_contact_graph(df: pd.DataFrame) -> nx.Graph:
    graph = nx.Graph()

    for _, row in df.iterrows():
        u = row["node_u"]
        v = row["node_v"]

        if pd.isna(u) or pd.isna(v):
            continue

        u = str(u)
        v = str(v)

        if u == v:
            continue

        contacts = float(row.get("contacts", 1.0) or 0.0)
        duration = float(row.get("duration_sec", 0.0) or 0.0)
        contacts_infected = float(row.get("contacts_infected", 0.0) or 0.0)

        if graph.has_edge(u, v):
            graph[u][v]["weight"] += contacts
            graph[u][v]["record_count"] += 1
            graph[u][v]["duration_sum"] += duration
            graph[u][v]["contacts_infected_sum"] += contacts_infected
        else:
            graph.add_edge(
                u,
                v,
                weight=contacts,
                record_count=1,
                duration_sum=duration,
                contacts_infected_sum=contacts_infected,
            )

    return graph


def minmax_normalize(series: pd.Series) -> pd.Series:
    min_value = series.min()
    max_value = series.max()

    if max_value == min_value:
        return pd.Series(np.zeros(len(series)), index=series.index)

    return (series - min_value) / (max_value - min_value)


def compute_node_metrics(graph: nx.Graph) -> pd.DataFrame:
    degree_centrality = nx.degree_centrality(graph)

    # Betweenness centrality can be expensive for large graphs.
    betweenness_centrality = nx.betweenness_centrality(graph, normalized=True)

    rows = []

    for node in graph.nodes():
        weighted_degree = sum(
            graph[node][neighbor].get("weight", 1.0) for neighbor in graph.neighbors(node)
        )

        duration_sum = sum(
            graph[node][neighbor].get("duration_sum", 0.0) for neighbor in graph.neighbors(node)
        )

        infected_contact_sum = sum(
            graph[node][neighbor].get("contacts_infected_sum", 0.0)
            for neighbor in graph.neighbors(node)
        )

        rows.append(
            {
                "node_id": node,
                "degree": graph.degree(node),
                "weighted_degree": weighted_degree,
                "degree_centrality": degree_centrality.get(node, 0.0),
                "betweenness_centrality": betweenness_centrality.get(node, 0.0),
                "duration_sum": duration_sum,
                "contacts_infected_sum": infected_contact_sum,
            }
        )

    metrics_df = pd.DataFrame(rows)

    if metrics_df.empty:
        return metrics_df

    metrics_df["norm_degree_centrality"] = minmax_normalize(metrics_df["degree_centrality"])
    metrics_df["norm_betweenness_centrality"] = minmax_normalize(
        metrics_df["betweenness_centrality"]
    )
    metrics_df["norm_weighted_degree"] = minmax_normalize(metrics_df["weighted_degree"])

    metrics_df["risk_score"] = (
        metrics_df["norm_degree_centrality"]
        + metrics_df["norm_betweenness_centrality"]
        + metrics_df["norm_weighted_degree"]
    )

    metrics_df = metrics_df.sort_values(by="risk_score", ascending=False).reset_index(drop=True)

    metrics_df["risk_rank"] = np.arange(1, len(metrics_df) + 1)

    return metrics_df


def export_edge_list(graph: nx.Graph, output_path: Path) -> None:
    rows = []

    for u, v, data in graph.edges(data=True):
        rows.append(
            {
                "node_u": u,
                "node_v": v,
                "weight": data.get("weight", 1.0),
                "record_count": data.get("record_count", 1),
                "duration_sum": data.get("duration_sum", 0.0),
                "contacts_infected_sum": data.get("contacts_infected_sum", 0.0),
            }
        )

    pd.DataFrame(rows).to_csv(output_path, index=False, encoding="utf-8-sig")


def export_graph_summary(
    graph: nx.Graph, output_path: Path, node_strategy: str, top_percent: float
) -> None:
    components = list(nx.connected_components(graph))
    component_sizes = sorted([len(c) for c in components], reverse=True)

    summary = {
        "node_strategy": node_strategy,
        "num_nodes": graph.number_of_nodes(),
        "num_edges": graph.number_of_edges(),
        "density": nx.density(graph),
        "num_connected_components": len(components),
        "largest_component_size": component_sizes[0] if component_sizes else 0,
        "top_percent": top_percent,
    }

    with output_path.open("w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)


def run_contact_network_analysis(args: argparse.Namespace) -> None:
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    df = load_processed_data(Path(args.processed_data))
    mapping = load_mapping(Path(args.mapping_path) if args.mapping_path else None)

    df, node_strategy = add_node_columns(df)

    graph = build_contact_graph(df)
    metrics_df = compute_node_metrics(graph)

    n_top = max(1, int(np.ceil(len(metrics_df) * args.top_percent)))
    top_nodes_df = metrics_df.head(n_top).copy()

    metrics_df.to_csv(output_dir / "node_centrality.csv", index=False, encoding="utf-8-sig")
    top_nodes_df.to_csv(output_dir / "top_5_percent_risk_nodes.csv", index=False, encoding="utf-8-sig")
    export_edge_list(graph, output_dir / "edge_list.csv")
    export_graph_summary(
        graph, output_dir / "graph_summary.json", node_strategy=node_strategy, top_percent=args.top_percent
    )

    print("Contact network analysis completed.")
    print("Node strategy:", node_strategy)
    print("Nodes:", graph.number_of_nodes())
    print("Edges:", graph.number_of_edges())
    print("Top nodes exported:", len(top_nodes_df))
    print("Output directory:", output_dir.resolve())


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Task 11: Contact network graph analysis")

    parser.add_argument(
        "--processed-data",
        default="data/processed/sashts_final_dataset.csv",
        help="Path to processed SASHTS dataset.",
    )
    parser.add_argument(
        "--mapping-path",
        default="data/processed/mapping_dict.json",
        help="Path to mapping dictionary.",
    )
    parser.add_argument(
        "--raw-contact-data",
        default=None,
        help="Optional raw contact network dataset for ID inspection.",
    )
    parser.add_argument(
        "--raw-metadata",
        default=None,
        help="Optional raw metadata dataset for ID inspection.",
    )
    parser.add_argument(
        "--output-dir",
        default="reports/issue_11_contact_network",
        help="Directory to save graph outputs.",
    )
    parser.add_argument(
        "--top-percent",
        type=float,
        default=0.05,
        help="Top percentage of nodes to export as high-risk nodes.",
    )

    return parser.parse_args()


if __name__ == "__main__":
    run_contact_network_analysis(parse_args())
