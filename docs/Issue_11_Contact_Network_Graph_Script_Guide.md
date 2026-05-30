# Issue 11 — Phân tích mạng lưới tiếp xúc (Graph Network)

## 1. Issue summary

**GitHub issue:** `Task 11: Phân tích mạng lưới tiếp xúc (Graph Network) #11`

### Mục tiêu

Xây dựng mô hình đồ thị từ dữ liệu tiếp xúc để tìm ra các node có nguy cơ “siêu lây nhiễm” dựa trên dữ liệu di chuyển/giao cắt/contact.

### Acceptance Criteria từ issue

- [ ] Sử dụng thư viện `NetworkX` để tạo đồ thị.
  - Node: `Grid ID` hoặc `Patient ID`.
  - Edge: lượt tiếp xúc.
- [ ] Tính toán chỉ số:
  - `Degree Centrality`
  - `Betweenness Centrality`
- [ ] Xuất file danh sách **Top 5% node nguy hiểm nhất** hệ thống.

---

## 2. Bối cảnh repo hiện tại

Trước khi code, Copilot **phải đọc và kiểm tra repo hiện tại**, không tự viết độc lập.

Repo hiện tại có cấu trúc chính:

```text
README.md
requirements.txt
.env.example

data/
  raw/
    sashts_contact_network.csv
    sashts_metadata.csv
  processed/
    sashts_final_dataset.csv
    mapping_dict.json
  external/

docs/
  STAR_CUBING.md
  STAR_TREE.md

notebook/
  00_ETL.ipynb

reports/
  figures/

sql/
  schema.sql

src/
  __init__.py
  config.py
  data_loader.py
  db_manager.py
  star_tree.py
  star_cubing.py
  star_tree_tests.py
  star_cubing_tests.py
  algorithm/
    starcubing.py
    starcubing_tests.py
```

### Trạng thái các phase trước

Repo đã có:

- ETL notebook: `notebook/00_ETL.ipynb`
- Processed dataset: `data/processed/sashts_final_dataset.csv`
- Mapping dictionary: `data/processed/mapping_dict.json`
- Star Tree: `src/star_tree.py`
- Star-Cubing: `src/algorithm/starcubing.py`
- Data warehouse schema: `sql/schema.sql`
- Tests cho Star Tree / Star-Cubing

Issue 11 phải **tận dụng kết quả ETL hiện có**, không tạo dataset giả và không phá vỡ code các phase trước.

---

## 3. Dataset hiện tại cần kiểm tra

Dataset đã gửi hiện có:

```text
data/processed/sashts_final_dataset.csv
Shape: 140,542 rows × 26 columns
Missing values: cần kiểm tra lại trong script
```

Các cột hiện có trong processed dataset:

```text
ind1_site
ind1_sex
ind1_index
ind1_sars
ind1_sus
ind2_site
ind2_sex
ind2_index
ind2_sars
ind2_sus
pair_sars
ind1_smokecignow1
ind2_smokecignow1
ind1_bmicat
ind2_bmicat
ind1_agegrp9
ind1_ixesarsvarf1
ind2_agegrp9
ind2_ixesarsvarf1
month_id
duration_sec
no_ts
contacts
contacts_infected
hcir
hh_ar
```

`mapping_dict.json` hiện có mapping cho các cột categorical đã encoded, ví dụ:

```text
pair_sars:
  Both negative -> 0
  No transmission -> 1
  Transmission -> 2
```

---

## 4. Vấn đề quan trọng: processed dataset có thể chưa có Patient ID / Grid ID

Issue yêu cầu:

```text
Node: Grid ID / Patient ID
Edge: lượt tiếp xúc
```

Tuy nhiên, `sashts_final_dataset.csv` hiện tại theo dữ liệu đã kiểm tra **không thấy cột rõ ràng tên `patient_id`, `grid_id`, `ind1_id`, `ind2_id`, `location_id`**.

Vì vậy Copilot phải làm theo thứ tự sau:

### Bước kiểm tra bắt buộc

1. Kiểm tra `data/raw/sashts_contact_network.csv`
2. Kiểm tra `data/raw/sashts_metadata.csv`
3. Kiểm tra `data/processed/sashts_final_dataset.csv`
4. Tìm các cột ID khả dụng:

```python
POSSIBLE_ID_COLUMNS = [
    "patient_id", "person_id", "participant_id",
    "ind1_id", "ind2_id",
    "p1_id", "p2_id",
    "source_id", "target_id",
    "grid_id", "location_id", "site_id"
]
```

### Nếu có ID thật

Nếu raw/processed data có cột ID cho 2 cá nhân hoặc 2 vị trí tiếp xúc, dùng ID thật làm node.

Ví dụ:

```text
node_u = ind1_id
node_v = ind2_id
```

hoặc:

```text
node_u = source_grid_id
node_v = target_grid_id
```

### Nếu không có ID thật

Nếu không có Patient ID/Grid ID rõ ràng, không được tự bịa random ID. Khi đó tạo **profile node** ổn định từ các thuộc tính cá nhân đã có:

```text
ind1_profile_id = hash/site_age_sex_index_bmi_smoking
ind2_profile_id = hash/site_age_sex_index_bmi_smoking
```

Ví dụ:

```python
ind1_profile_columns = [
    "ind1_site",
    "ind1_agegrp9",
    "ind1_sex",
    "ind1_index",
    "ind1_bmicat",
    "ind1_smokecignow1",
]

ind2_profile_columns = [
    "ind2_site",
    "ind2_agegrp9",
    "ind2_sex",
    "ind2_index",
    "ind2_bmicat",
    "ind2_smokecignow1",
]
```

Khi dùng profile node, báo cáo phải ghi rõ:

```text
Because the processed dataset does not contain explicit patient_id/grid_id columns,
nodes are constructed as epidemiological profile nodes based on available individual attributes.
```

---

## 5. Ý tưởng thuật toán

### 5.1. Xây dựng graph

Dùng `networkx.Graph()`.

Mỗi dòng dữ liệu là một contact/exposure record.

- Node: cá nhân, grid, hoặc profile node.
- Edge: tiếp xúc giữa `ind1` và `ind2`.

Nếu một cặp node xuất hiện nhiều lần, không tạo nhiều edge rời rạc mà aggregate:

```text
edge_weight = tổng số contacts
duration_sum = tổng duration_sec
record_count = số dòng tạo ra edge
infected_contact_sum = tổng contacts_infected
months = danh sách/thống kê month_id
```

### 5.2. Centrality

Tính:

```python
nx.degree_centrality(G)
nx.betweenness_centrality(G)
```

Ngoài ra nên tính thêm để báo cáo đẹp hơn:

```text
weighted_degree = tổng weight của các edge nối với node
contact_count = tổng contacts liên quan node
duration_sum = tổng duration_sec liên quan node
infected_contact_sum = tổng contacts_infected liên quan node
```

### 5.3. Risk score

Top 5% node nguy hiểm nhất nên dựa trên score tổng hợp:

```text
risk_score =
  normalized_degree_centrality
+ normalized_betweenness_centrality
+ normalized_weighted_degree
+ normalized_infected_contact_sum
```

Nếu muốn tránh dùng outcome/infection-derived columns trong graph risk score, có thể tạo option:

```bash
--include-infection-risk
```

Mặc định nên dùng structural score:

```text
degree_centrality + betweenness_centrality + weighted_degree
```

vì đây là graph/network analysis, không phải classification.

---

## 6. File cần tạo/chỉnh sửa

### Bắt buộc tạo

```text
src/contact_network_analysis.py
src/contact_network_analysis_tests.py
```

### Có thể tạo thêm

```text
reports/issue_11_contact_network/
  graph_summary.json
  node_centrality.csv
  edge_list.csv
  top_5_percent_risk_nodes.csv
  top_nodes_readable.csv
  graph_components.csv
```

### Cập nhật nếu cần

```text
requirements.txt
README.md
```

Thêm dependency nếu chưa có:

```text
networkx
```

---

## 7. Script CLI yêu cầu

Không dùng notebook cho issue này. Tạo script chạy được bằng CLI:

```bash
python src/contact_network_analysis.py \
  --processed-data data/processed/sashts_final_dataset.csv \
  --mapping-path data/processed/mapping_dict.json \
  --raw-contact-data data/raw/sashts_contact_network.csv \
  --raw-metadata data/raw/sashts_metadata.csv \
  --output-dir reports/issue_11_contact_network \
  --top-percent 0.05
```

Script phải chạy được ngay cả khi không truyền raw data:

```bash
python src/contact_network_analysis.py \
  --processed-data data/processed/sashts_final_dataset.csv \
  --mapping-path data/processed/mapping_dict.json \
  --output-dir reports/issue_11_contact_network
```

---

## 8. Code khung đề xuất cho `src/contact_network_analysis.py`

Copilot nên tạo script theo cấu trúc này.

```python
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

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
        lambda row: make_profile_id(row, IND1_PROFILE_COLUMNS, "ind1_profile"),
        axis=1,
    )
    df["node_v"] = df.apply(
        lambda row: make_profile_id(row, IND2_PROFILE_COLUMNS, "ind2_profile"),
        axis=1,
    )
    node_strategy = "profile_nodes_from_encoded_individual_attributes"
    return df, node_strategy


def build_contact_graph(df: pd.DataFrame) -> nx.Graph:
    graph = nx.Graph()

    for _, row in df.iterrows():
        u = row["node_u"]
        v = row["node_v"]

        if u == v:
            continue

        contacts = float(row.get("contacts", 1.0))
        duration = float(row.get("duration_sec", 0.0))
        contacts_infected = float(row.get("contacts_infected", 0.0))

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

    # Betweenness centrality can be expensive, but dataset after aggregation
    # should be manageable. For very large graph, add k-sampling later.
    betweenness_centrality = nx.betweenness_centrality(graph, normalized=True)

    rows = []

    for node in graph.nodes():
        weighted_degree = sum(
            graph[node][neighbor].get("weight", 1.0)
            for neighbor in graph.neighbors(node)
        )

        duration_sum = sum(
            graph[node][neighbor].get("duration_sum", 0.0)
            for neighbor in graph.neighbors(node)
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
                "degree_centrality": degree_centrality[node],
                "betweenness_centrality": betweenness_centrality[node],
                "duration_sum": duration_sum,
                "contacts_infected_sum": infected_contact_sum,
            }
        )

    metrics_df = pd.DataFrame(rows)

    metrics_df["norm_degree_centrality"] = minmax_normalize(
        metrics_df["degree_centrality"]
    )
    metrics_df["norm_betweenness_centrality"] = minmax_normalize(
        metrics_df["betweenness_centrality"]
    )
    metrics_df["norm_weighted_degree"] = minmax_normalize(
        metrics_df["weighted_degree"]
    )

    metrics_df["risk_score"] = (
        metrics_df["norm_degree_centrality"]
        + metrics_df["norm_betweenness_centrality"]
        + metrics_df["norm_weighted_degree"]
    )

    metrics_df = metrics_df.sort_values(
        by="risk_score",
        ascending=False,
    ).reset_index(drop=True)

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

    pd.DataFrame(rows).to_csv(output_path, index=False)


def export_graph_summary(
    graph: nx.Graph,
    output_path: Path,
    node_strategy: str,
    top_percent: float,
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

    metrics_df.to_csv(output_dir / "node_centrality.csv", index=False)
    top_nodes_df.to_csv(output_dir / "top_5_percent_risk_nodes.csv", index=False)
    export_edge_list(graph, output_dir / "edge_list.csv")
    export_graph_summary(
        graph,
        output_dir / "graph_summary.json",
        node_strategy=node_strategy,
        top_percent=args.top_percent,
    )

    print("Contact network analysis completed.")
    print("Node strategy:", node_strategy)
    print("Nodes:", graph.number_of_nodes())
    print("Edges:", graph.number_of_edges())
    print("Top nodes exported:", len(top_nodes_df))
    print("Output directory:", output_dir.resolve())


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Task 11: Contact network graph analysis"
    )

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
```

---

## 9. Tests cần có

Tạo file:

```text
src/contact_network_analysis_tests.py
```

Test tối thiểu:

```python
import unittest
import pandas as pd
import networkx as nx

from src.contact_network_analysis import (
    add_node_columns,
    build_contact_graph,
    compute_node_metrics,
)


class ContactNetworkAnalysisTests(unittest.TestCase):
    def test_profile_nodes_created_when_no_explicit_ids(self):
        df = pd.DataFrame(
            {
                "ind1_site": [0],
                "ind1_agegrp9": [1],
                "ind1_sex": [0],
                "ind1_index": [1],
                "ind1_bmicat": [2],
                "ind1_smokecignow1": [0],
                "ind2_site": [1],
                "ind2_agegrp9": [2],
                "ind2_sex": [1],
                "ind2_index": [0],
                "ind2_bmicat": [1],
                "ind2_smokecignow1": [2],
                "month_id": [1],
                "duration_sec": [120],
                "contacts": [3],
            }
        )

        result_df, strategy = add_node_columns(df)

        self.assertIn("node_u", result_df.columns)
        self.assertIn("node_v", result_df.columns)
        self.assertEqual(strategy, "profile_nodes_from_encoded_individual_attributes")

    def test_graph_aggregates_repeated_edges(self):
        df = pd.DataFrame(
            {
                "node_u": ["A", "A"],
                "node_v": ["B", "B"],
                "contacts": [2, 3],
                "duration_sec": [10, 20],
                "contacts_infected": [1, 0],
            }
        )

        graph = build_contact_graph(df)

        self.assertEqual(graph.number_of_nodes(), 2)
        self.assertEqual(graph.number_of_edges(), 1)
        self.assertEqual(graph["A"]["B"]["weight"], 5)
        self.assertEqual(graph["A"]["B"]["record_count"], 2)
        self.assertEqual(graph["A"]["B"]["duration_sum"], 30)

    def test_compute_node_metrics_contains_required_columns(self):
        graph = nx.Graph()
        graph.add_edge("A", "B", weight=2, duration_sum=10, contacts_infected_sum=0)
        graph.add_edge("B", "C", weight=3, duration_sum=20, contacts_infected_sum=1)

        metrics_df = compute_node_metrics(graph)

        required_cols = [
            "node_id",
            "degree_centrality",
            "betweenness_centrality",
            "weighted_degree",
            "risk_score",
            "risk_rank",
        ]

        for col in required_cols:
            self.assertIn(col, metrics_df.columns)


if __name__ == "__main__":
    unittest.main()
```

Chạy test:

```bash
python -m unittest src.contact_network_analysis_tests -v
```

hoặc:

```bash
python -m pytest -q
```

---

## 10. Output mong đợi

Sau khi chạy script, thư mục output phải có:

```text
reports/issue_11_contact_network/
  graph_summary.json
  node_centrality.csv
  edge_list.csv
  top_5_percent_risk_nodes.csv
```

### `graph_summary.json`

Nội dung gồm:

```json
{
  "node_strategy": "profile_nodes_from_encoded_individual_attributes",
  "num_nodes": 120,
  "num_edges": 450,
  "density": 0.063,
  "num_connected_components": 3,
  "largest_component_size": 95,
  "top_percent": 0.05
}
```

### `node_centrality.csv`

Phải có các cột:

```text
node_id
degree
weighted_degree
degree_centrality
betweenness_centrality
duration_sum
contacts_infected_sum
risk_score
risk_rank
```

### `top_5_percent_risk_nodes.csv`

Phải chứa top 5% node có `risk_score` cao nhất.

---

## 11. Acceptance Criteria mapping

| Acceptance Criteria | Cách đáp ứng |
|---|---|
| Sử dụng `NetworkX` tạo đồ thị | `nx.Graph()` trong `build_contact_graph()` |
| Node là Grid ID / Patient ID | Script kiểm tra ID thật; nếu không có thì dùng profile node và ghi rõ strategy |
| Edge là lượt tiếp xúc | Mỗi dòng contact tạo/aggregate edge, weight = `contacts` |
| Tính Degree Centrality | `nx.degree_centrality(graph)` |
| Tính Betweenness Centrality | `nx.betweenness_centrality(graph)` |
| Xuất Top 5% node nguy hiểm | `top_5_percent_risk_nodes.csv` |

---

## 12. Nội dung báo cáo cho issue 11

Khi viết báo cáo, trình bày:

### 12.1. Mô hình graph

```text
Each node represents either an explicit patient/grid identifier if available,
or an epidemiological profile constructed from available individual attributes.
Each edge represents contact/exposure between two nodes.
The edge weight is aggregated from the `contacts` field.
```

### 12.2. Degree Centrality

```text
Degree Centrality measures how many direct neighbors a node has.
A node with high degree centrality has many direct contact connections and may spread infection to many others.
```

### 12.3. Betweenness Centrality

```text
Betweenness Centrality measures how often a node lies on shortest paths between other nodes.
A node with high betweenness can act as a bridge between contact groups and may facilitate cross-community transmission.
```

### 12.4. Top 5% risk nodes

```text
The top 5% nodes are selected using a combined risk score based on degree centrality,
betweenness centrality, and weighted contact degree.
These nodes are interpreted as potentially high-risk spreader nodes.
```

---

## 13. PR description gợi ý

```markdown
## Summary

This PR implements Task 11: Contact Network Graph Analysis.

The implementation builds a contact graph from the processed SASHTS dataset using NetworkX, computes graph centrality metrics, and exports the top 5% highest-risk nodes.

## What was added

- Added `src/contact_network_analysis.py`.
- Added script-based graph construction pipeline.
- Added automatic node strategy detection:
  - explicit ID columns if available
  - profile-based nodes if patient/grid IDs are not available
- Computed:
  - Degree Centrality
  - Betweenness Centrality
  - Weighted degree
  - Risk score
- Exported:
  - `graph_summary.json`
  - `node_centrality.csv`
  - `edge_list.csv`
  - `top_5_percent_risk_nodes.csv`
- Added unit tests for node creation, edge aggregation, and centrality output.

## How to run

```bash
python src/contact_network_analysis.py \
  --processed-data data/processed/sashts_final_dataset.csv \
  --mapping-path data/processed/mapping_dict.json \
  --output-dir reports/issue_11_contact_network \
  --top-percent 0.05
```

## How to test

```bash
python -m pytest -q
```

or:

```bash
python -m unittest src.contact_network_analysis_tests -v
```

## Related Issue

Closes #11
```

---

## 14. Definition of Done

Issue 11 chỉ được xem là hoàn thành khi:

- [ ] Script `src/contact_network_analysis.py` chạy được từ CLI.
- [ ] Script tự kiểm tra dataset và các cột bắt buộc.
- [ ] Script dùng NetworkX để tạo graph.
- [ ] Có node strategy rõ ràng:
  - explicit patient/grid ID nếu có,
  - fallback profile node nếu không có.
- [ ] Edge được aggregate theo contacts/duration.
- [ ] Có `degree_centrality`.
- [ ] Có `betweenness_centrality`.
- [ ] Có `top_5_percent_risk_nodes.csv`.
- [ ] Có `graph_summary.json`.
- [ ] Có unit tests.
- [ ] `python -m pytest -q` chạy qua.
- [ ] PR description có `Closes #11`.

---

## 15. Lưu ý quan trọng cho Copilot

Copilot không được:

- Tạo dữ liệu giả.
- Bỏ qua `README.md`.
- Bỏ qua `data/processed/sashts_final_dataset.csv`.
- Bỏ qua `mapping_dict.json`.
- Giả định có Patient ID nếu dataset không có.
- Viết notebook thay vì script.
- Xóa/sửa lung tung `star_tree.py`, `star_cubing.py`, hoặc các tests cũ.
- Làm hỏng pipeline các phase trước.

Copilot phải:

- Đọc repo hiện tại.
- Kiểm tra dataset thật.
- Kiểm tra code phase trước.
- Bám sát acceptance criteria của issue.
- Tạo script chạy được.
- Xuất file kết quả rõ ràng.
- Viết test tối thiểu.
