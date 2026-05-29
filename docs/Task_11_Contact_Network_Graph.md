# Task 11: Phân tích mạng lưới tiếp xúc bằng Graph Network

## 1. Mục tiêu

Xây dựng mô hình đồ thị để tìm các node **siêu lây nhiễm** dựa trên dữ liệu di chuyển/giao cắt hoặc mạng tiếp xúc.

Theo issue, task này cần hoàn thành:

- Sử dụng thư viện `NetworkX` để tạo đồ thị.
- Node: `Grid ID` hoặc `Patient ID`.
- Edge: lượt tiếp xúc.
- Tính `Degree Centrality` và `Betweenness Centrality`.
- Xuất danh sách **Top 5% node nguy hiểm nhất hệ thống**.

## 2. Trạng thái repo hiện tại liên quan đến issue

Repo hiện có dữ liệu raw:

```text
data/raw/sashts_contact_network.csv
data/raw/sashts_metadata.csv
```

Và dữ liệu processed:

```text
data/processed/sashts_final_dataset.csv
data/processed/mapping_dict.json
```

Task 11 có thể dùng trực tiếp:

```text
data/raw/sashts_contact_network.csv
```

hoặc dùng dataset đã ETL:

```text
data/processed/sashts_final_dataset.csv
```

Nếu `sashts_contact_network.csv` đã có edge list, nên dùng file này làm input chính.

## 3. Ý tưởng bài toán

Dữ liệu contact network có thể biểu diễn thành đồ thị:

```text
Node = Patient ID hoặc Grid ID
Edge = có tiếp xúc / giao cắt / cùng vị trí trong một khoảng thời gian
Weight = số lần tiếp xúc hoặc cường độ tiếp xúc
```

Sau đó dùng centrality để tìm node quan trọng.

### Degree Centrality

Đo một node có bao nhiêu kết nối trực tiếp.

```text
Degree centrality cao → node tiếp xúc với nhiều node khác.
```

Trong dịch tễ học:

```text
Node có degree cao có khả năng lan bệnh trực tiếp đến nhiều người/khu vực.
```

### Betweenness Centrality

Đo một node nằm trên bao nhiêu đường đi ngắn nhất giữa các node khác.

```text
Betweenness cao → node là cầu nối giữa nhiều nhóm.
```

Trong dịch tễ học:

```text
Node có betweenness cao có thể là cầu nối lan bệnh giữa các cộng đồng/khu vực.
```

## 4. File nên tạo / chỉnh sửa

### 4.1. Notebook chính

Tạo:

```text
notebook/contact_network_analysis.ipynb
```

Notebook gồm:

```text
1. Load contact network data
2. Chuẩn hóa cột source/target/weight
3. Tạo graph bằng NetworkX
4. Tính degree centrality
5. Tính betweenness centrality
6. Tính risk score tổng hợp
7. Xuất Top 5% node nguy hiểm
8. Visualize graph hoặc subgraph
9. Lưu kết quả vào reports/
```

### 4.2. Module tùy chọn

Có thể tạo:

```text
src/graph_analysis.py
```

Chứa:

```python
load_contact_edges(...)
build_contact_graph(...)
compute_graph_centrality(...)
rank_high_risk_nodes(...)
export_top_nodes(...)
```

Nếu muốn giữ đơn giản, làm trực tiếp trong notebook.

## 5. Input cần kiểm tra

Mở `data/raw/sashts_contact_network.csv`, cần xác định các cột:

```text
source
 target
 patient_id_a
 patient_id_b
 grid_id_a
 grid_id_b
 contact_count
 timestamp
 weight
```

Vì chưa chắc tên cột chính xác, nên notebook cần robust:

```python
possible_source_cols = ["source", "src", "patient_id_a", "from", "node_a", "grid_id_a"]
possible_target_cols = ["target", "dst", "patient_id_b", "to", "node_b", "grid_id_b"]
possible_weight_cols = ["weight", "contact_count", "count", "num_contacts"]
```

Nếu không có weight, mặc định:

```text
weight = 1
```

## 6. Code khung notebook

### 6.1. Import

```python
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import networkx as nx

from pathlib import Path
```

### 6.2. Load data

```python
DATA_PATH = Path("data/raw/sashts_contact_network.csv")

edges_df = pd.read_csv(DATA_PATH)

print(edges_df.shape)
display(edges_df.head())
print(edges_df.columns.tolist())
```

### 6.3. Auto-detect source/target/weight

```python
def find_column(columns, candidates):
    lower_map = {col.lower(): col for col in columns}
    for cand in candidates:
        if cand.lower() in lower_map:
            return lower_map[cand.lower()]
    return None

source_col = find_column(
    edges_df.columns,
    ["source", "src", "from", "patient_id_a", "node_a", "grid_id_a"]
)

target_col = find_column(
    edges_df.columns,
    ["target", "dst", "to", "patient_id_b", "node_b", "grid_id_b"]
)

weight_col = find_column(
    edges_df.columns,
    ["weight", "contact_count", "count", "num_contacts"]
)

if source_col is None or target_col is None:
    raise ValueError("Không tìm thấy cột source/target trong contact network data.")

if weight_col is None:
    edges_df["weight"] = 1
    weight_col = "weight"

print("source_col:", source_col)
print("target_col:", target_col)
print("weight_col:", weight_col)
```

### 6.4. Tạo graph

```python
G = nx.Graph()

for _, row in edges_df.iterrows():
    source = row[source_col]
    target = row[target_col]
    weight = row[weight_col]

    if pd.isna(source) or pd.isna(target):
        continue

    if G.has_edge(source, target):
        G[source][target]["weight"] += weight
    else:
        G.add_edge(source, target, weight=weight)

print("Number of nodes:", G.number_of_nodes())
print("Number of edges:", G.number_of_edges())
print("Density:", nx.density(G))
```

### 6.5. Tính centrality

```python
degree_centrality = nx.degree_centrality(G)

betweenness_centrality = nx.betweenness_centrality(
    G,
    weight="weight",
    normalized=True
)
```

Lưu ý:

```text
Nếu weight là số lần tiếp xúc, weight lớn nghĩa là quan hệ mạnh.
Trong shortest path, NetworkX hiểu weight lớn là đường dài hơn.
Nếu muốn weight lớn = gần hơn, cần tạo distance = 1 / weight.
```

Phiên bản tốt hơn:

```python
for u, v, data in G.edges(data=True):
    data["distance"] = 1 / data["weight"] if data["weight"] > 0 else 1

betweenness_centrality = nx.betweenness_centrality(
    G,
    weight="distance",
    normalized=True
)
```

### 6.6. Tạo bảng ranking

```python
centrality_df = pd.DataFrame({
    "node": list(G.nodes()),
    "degree_centrality": [degree_centrality[n] for n in G.nodes()],
    "betweenness_centrality": [betweenness_centrality[n] for n in G.nodes()],
    "weighted_degree": [G.degree(n, weight="weight") for n in G.nodes()]
})

# Chuẩn hóa min-max để tạo risk score
for col in ["degree_centrality", "betweenness_centrality", "weighted_degree"]:
    min_val = centrality_df[col].min()
    max_val = centrality_df[col].max()
    if max_val > min_val:
        centrality_df[f"norm_{col}"] = (centrality_df[col] - min_val) / (max_val - min_val)
    else:
        centrality_df[f"norm_{col}"] = 0

centrality_df["risk_score"] = (
    0.4 * centrality_df["norm_degree_centrality"] +
    0.4 * centrality_df["norm_betweenness_centrality"] +
    0.2 * centrality_df["norm_weighted_degree"]
)

centrality_df = centrality_df.sort_values("risk_score", ascending=False)

display(centrality_df.head(20))
```

### 6.7. Xuất top 5% node nguy hiểm

```python
top_k = max(1, int(np.ceil(len(centrality_df) * 0.05)))

top_nodes_df = centrality_df.head(top_k).copy()

display(top_nodes_df)

print("Top 5% nodes:", top_k)
```

### 6.8. Lưu kết quả

```python
REPORT_DIR = Path("reports")
FIGURE_DIR = REPORT_DIR / "figures"
REPORT_DIR.mkdir(exist_ok=True)
FIGURE_DIR.mkdir(exist_ok=True)

centrality_df.to_csv(REPORT_DIR / "contact_network_centrality.csv", index=False)
top_nodes_df.to_csv(REPORT_DIR / "top_5_percent_high_risk_nodes.csv", index=False)
```

### 6.9. Visualize graph

Nếu graph lớn, chỉ vẽ subgraph top nodes:

```python
top_nodes = set(top_nodes_df["node"])
neighbor_nodes = set()

for node in top_nodes:
    neighbor_nodes.update(G.neighbors(node))

sub_nodes = list(top_nodes | neighbor_nodes)
H = G.subgraph(sub_nodes).copy()

plt.figure(figsize=(12, 8))
pos = nx.spring_layout(H, seed=42)

node_colors = [
    1 if node in top_nodes else 0
    for node in H.nodes()
]

nx.draw_networkx_nodes(H, pos, node_color=node_colors, cmap="coolwarm", node_size=80)
nx.draw_networkx_edges(H, pos, alpha=0.3)
nx.draw_networkx_labels(H, pos, font_size=7)

plt.title("Contact Network - Top 5% High-Risk Nodes and Neighbors")
plt.axis("off")
plt.savefig(FIGURE_DIR / "contact_network_top_nodes.png", dpi=300, bbox_inches="tight")
plt.show()
```

## 7. Acceptance Criteria mapping

| Acceptance Criteria | Cách đáp ứng |
|---|---|
| Sử dụng NetworkX tạo đồ thị | `G = nx.Graph()` và add edge từ contact data |
| Node: Grid ID / Patient ID, Edge: lượt tiếp xúc | source/target lấy từ contact network, weight là contact count |
| Tính Degree Centrality và Betweenness Centrality | `nx.degree_centrality`, `nx.betweenness_centrality` |
| Xuất Top 5% node nguy hiểm nhất | `top_nodes_df = centrality_df.head(top_k)` |

## 8. Output mong đợi

```text
notebook/contact_network_analysis.ipynb
reports/contact_network_centrality.csv
reports/top_5_percent_high_risk_nodes.csv
reports/figures/contact_network_top_nodes.png
```

## 9. Test đề xuất

Nếu tạo `src/graph_analysis.py`, thêm:

```text
src/graph_analysis_tests.py
```

Test:

```python
def test_build_contact_graph_node_edge_count():
    ...

def test_compute_centrality_has_required_columns():
    ...

def test_top_5_percent_at_least_one_node():
    ...
```

## 10. Nội dung báo cáo cho Task 11

Có thể viết:

```text
Dữ liệu tiếp xúc được biểu diễn dưới dạng đồ thị, trong đó mỗi node là một cá nhân hoặc một ô không gian, còn edge biểu diễn sự tiếp xúc hoặc giao cắt giữa hai node. Trọng số cạnh được xác định bằng số lượt tiếp xúc. Sau khi xây dựng đồ thị bằng NetworkX, hai chỉ số trung tâm được tính: Degree Centrality và Betweenness Centrality.

Degree Centrality phản ánh số lượng kết nối trực tiếp của một node, cho biết node đó có khả năng tiếp xúc với nhiều node khác hay không. Betweenness Centrality đo mức độ một node nằm trên các đường đi ngắn nhất giữa các node khác, từ đó phát hiện các node đóng vai trò cầu nối giữa các cộng đồng.

Các node có điểm tổng hợp cao nhất được xem là nhóm nguy cơ cao hoặc siêu lây nhiễm tiềm năng. Top 5% node có risk score cao nhất được xuất ra để phục vụ phân tích và can thiệp.
```

## 11. Definition of Done

```text
[ ] Có notebook/contact_network_analysis.ipynb.
[ ] Load được contact network data.
[ ] Tạo được NetworkX graph.
[ ] Tính được Degree Centrality.
[ ] Tính được Betweenness Centrality.
[ ] Tạo được risk_score.
[ ] Xuất top 5% node nguy hiểm nhất.
[ ] Có ít nhất một visualization.
[ ] Có file CSV trong reports/.
[ ] Không làm hỏng test cũ.
```
