# Task 9: Phân cụm “Ground Zero” bằng Iceberg Cuboids

## 1. Mục tiêu

Sử dụng các vùng **Iceberg Cuboids** đã được trích xuất từ Star-Cubing để tìm ra các cụm lây nhiễm không gian - thời gian, từ đó xác định các vùng có khả năng là **ground zero** hoặc **ổ lây nhiễm siêu tốc**.

Theo issue, task này cần hoàn thành:

- Load dữ liệu từ bảng `Fact_Exposure` trong SQL vào `notebooks/clustering.ipynb`.
- Cài đặt thuật toán **DBSCAN** hoặc **K-Means** bằng `scikit-learn`.
- Trích xuất tọa độ trọng tâm `centroid` của các cụm lây nhiễm siêu tốc.

## 2. Trạng thái repo hiện tại liên quan đến issue

Repo hiện đã có nền tảng trước đó:

```text
sql/schema.sql
src/db_manager.py
src/data_loader.py
src/star_tree.py
src/star_cubing.py
src/algorithm/starcubing.py
notebook/00_ETL.ipynb
data/processed/sashts_final_dataset.csv
data/processed/mapping_dict.json
```

Các phần đã hoàn thiện trước task này:

- ETL dữ liệu SASHTS từ raw sang processed.
- Thiết kế Data Warehouse dạng Star Schema.
- Bảng `Fact_Exposure` lưu các cuboids vượt ngưỡng `min_support`.
- Star Tree / Prefix Tree đã có.
- Star-Cubing / Iceberg Cube đã có.
- Export cuboids sang SQL đã có.

Task 9 sẽ dùng kết quả từ các bước trên, tức là dùng `Fact_Exposure` làm đầu vào cho clustering.

## 3. Ý tưởng bài toán

Sau Star-Cubing, mỗi dòng trong `Fact_Exposure` có thể hiểu là một **khối dữ liệu dịch tễ** hoặc **cuboid cell** thỏa điều kiện hỗ trợ tối thiểu.

Ví dụ một cuboid có thể mô tả:

```text
time = week_03
location = district_A
age_group = adult
sex = female
count_exposure = 42
```

Nếu nhiều cuboids có `count_exposure` cao và gần nhau theo không gian - thời gian, chúng có thể tạo thành một cụm lây nhiễm đáng chú ý.

Do đó, clustering sẽ giúp gom các cuboids có đặc trưng tương tự để tìm:

```text
cụm nguy cơ cao
cụm lây nhiễm theo khu vực
cụm lây nhiễm theo thời gian
ground zero candidate
```

## 4. Vì sao dùng DBSCAN hoặc K-Means?

### 4.1. K-Means

K-Means phù hợp khi muốn chia dữ liệu thành số cụm cố định `k`.

Ưu điểm:

- Dễ hiểu.
- Dễ giải thích centroid.
- Có sẵn trong `scikit-learn`.
- Phù hợp để trích xuất trọng tâm cụm.

Nhược điểm:

- Phải chọn trước số cụm `k`.
- Không phát hiện noise/outlier tốt.
- Không phù hợp lắm nếu cụm có hình dạng bất thường.

### 4.2. DBSCAN

DBSCAN phù hợp hơn nếu muốn tìm cụm theo mật độ.

Ưu điểm:

- Không cần chọn trước số cụm.
- Có thể phát hiện outliers/noise.
- Hợp lý với bài toán ổ dịch vì ổ dịch thường là vùng mật độ cao.

Nhược điểm:

- Cần chọn `eps` và `min_samples` phù hợp.
- Nhạy với scale của dữ liệu.

### Khuyến nghị cho task này

Nên cài cả hai:

```text
K-Means: baseline dễ giải thích centroid.
DBSCAN: phương pháp chính để tìm ground zero theo mật độ.
```

Nếu issue chỉ yêu cầu một trong hai, ưu tiên **DBSCAN** vì “ground zero” thường gắn với vùng mật độ cao và outlier detection.

## 5. File nên tạo / chỉnh sửa

### 5.1. Tạo notebook mới

```text
notebook/clustering.ipynb
```

Notebook này cần có các phần:

```text
1. Load thư viện
2. Kết nối SQL / load Fact_Exposure
3. Kiểm tra dữ liệu
4. Chọn feature clustering
5. Tiền xử lý feature
6. K-Means clustering
7. DBSCAN clustering
8. Trích xuất centroid
9. Xuất kết quả ra reports/
10. Nhận xét kết quả
```

### 5.2. Có thể thêm module tùy chọn

Nếu muốn code sạch hơn, có thể tạo:

```text
src/clustering.py
```

Chứa các hàm:

```python
load_fact_exposure(...)
prepare_clustering_features(...)
run_kmeans(...)
run_dbscan(...)
extract_cluster_centroids(...)
export_cluster_results(...)
```

Nhưng nếu issue chỉ yêu cầu notebook, có thể làm trực tiếp trong `notebook/clustering.ipynb`.

## 6. Thiết kế input từ `Fact_Exposure`

Giả sử bảng `Fact_Exposure` có các cột dạng:

```text
fact_id
time_key
location_key
patient_key
count_exposure
support
cuboid_level
```

Hoặc có thể có thêm các thuộc tính sau khi join dimension:

```text
date / week / month
location_id / grid_id / latitude / longitude
age_group
sex
count_exposure
```

Cần join với dimension để lấy feature có ý nghĩa:

```sql
SELECT
    f.fact_id,
    f.count_exposure,
    t.day,
    t.week,
    t.month,
    l.grid_id,
    l.latitude,
    l.longitude,
    p.age_group,
    p.sex
FROM Fact_Exposure f
LEFT JOIN Dim_Time t ON f.time_id = t.time_id
LEFT JOIN Dim_Location l ON f.location_id = l.location_id
LEFT JOIN Dim_Patient p ON f.patient_id = p.patient_id;
```

Nếu schema hiện tại chưa có `latitude/longitude`, có thể dùng:

```text
grid_id
site_id
location_code
```

rồi encode thành numeric.

## 7. Feature dùng cho clustering

Feature nên gồm 3 nhóm:

### Nhóm không gian

```text
location_id / grid_id
latitude
longitude
```

### Nhóm thời gian

```text
time_id
week
month
```

### Nhóm cường độ dịch tễ

```text
count_exposure
support
```

Nếu có đặc trưng cá nhân:

```text
age_group
sex
```

thì one-hot encode.

Ví dụ feature matrix:

```text
[latitude, longitude, week, count_exposure, age_group_encoded, sex_encoded]
```

## 8. Code khung cho notebook

### 8.1. Import

```python
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

from sklearn.preprocessing import StandardScaler, OneHotEncoder
from sklearn.compose import ColumnTransformer
from sklearn.pipeline import Pipeline
from sklearn.cluster import KMeans, DBSCAN
from sklearn.metrics import silhouette_score, davies_bouldin_score
from sqlalchemy import create_engine
```

### 8.2. Load dữ liệu từ SQL

```python
from src.config import DATABASE_URL

engine = create_engine(DATABASE_URL)

query = """
SELECT *
FROM Fact_Exposure
"""

fact_df = pd.read_sql(query, engine)

print(fact_df.shape)
display(fact_df.head())
```

Nếu cần join dimension:

```python
query = """
SELECT
    f.*,
    t.week,
    t.month,
    l.grid_id,
    l.latitude,
    l.longitude,
    p.age_group,
    p.sex
FROM Fact_Exposure f
LEFT JOIN Dim_Time t ON f.time_id = t.time_id
LEFT JOIN Dim_Location l ON f.location_id = l.location_id
LEFT JOIN Dim_Patient p ON f.patient_id = p.patient_id
"""

cube_df = pd.read_sql(query, engine)
```

### 8.3. Chọn feature

```python
numeric_features = [
    "count_exposure",
    "week",
    "latitude",
    "longitude"
]

categorical_features = [
    "age_group",
    "sex"
]

numeric_features = [col for col in numeric_features if col in cube_df.columns]
categorical_features = [col for col in categorical_features if col in cube_df.columns]

feature_df = cube_df[numeric_features + categorical_features].copy()
```

### 8.4. Preprocessing

```python
preprocessor = ColumnTransformer(
    transformers=[
        ("num", StandardScaler(), numeric_features),
        ("cat", OneHotEncoder(handle_unknown="ignore"), categorical_features)
    ]
)

X = preprocessor.fit_transform(feature_df)
```

### 8.5. K-Means

```python
kmeans = KMeans(
    n_clusters=4,
    random_state=42,
    n_init=20
)

cube_df["kmeans_cluster"] = kmeans.fit_predict(X)
```

### 8.6. DBSCAN

```python
dbscan = DBSCAN(
    eps=0.8,
    min_samples=5
)

cube_df["dbscan_cluster"] = dbscan.fit_predict(X)
```

Trong DBSCAN:

```text
cluster = -1 nghĩa là noise/outlier.
```

### 8.7. Đánh giá clustering

```python
def evaluate_clustering(X, labels, method_name):
    valid_mask = labels != -1
    valid_labels = labels[valid_mask]
    valid_X = X[valid_mask]

    n_clusters = len(set(valid_labels))

    if n_clusters < 2:
        return {
            "method": method_name,
            "n_clusters": n_clusters,
            "silhouette": np.nan,
            "davies_bouldin": np.nan
        }

    return {
        "method": method_name,
        "n_clusters": n_clusters,
        "silhouette": silhouette_score(valid_X, valid_labels),
        "davies_bouldin": davies_bouldin_score(valid_X.toarray() if hasattr(valid_X, "toarray") else valid_X, valid_labels)
    }

results = [
    evaluate_clustering(X, cube_df["kmeans_cluster"].values, "K-Means"),
    evaluate_clustering(X, cube_df["dbscan_cluster"].values, "DBSCAN")
]

results_df = pd.DataFrame(results)
display(results_df)
```

### 8.8. Trích xuất centroid ground zero

Với K-Means:

```python
centroid_rows = []

for cluster_id, group in cube_df.groupby("kmeans_cluster"):
    row = {
        "method": "K-Means",
        "cluster_id": cluster_id,
        "n_cells": len(group),
        "total_exposure": group["count_exposure"].sum(),
        "avg_exposure": group["count_exposure"].mean()
    }

    for col in ["latitude", "longitude", "week"]:
        if col in group.columns:
            row[f"centroid_{col}"] = np.average(
                group[col],
                weights=group["count_exposure"]
            )

    centroid_rows.append(row)

centroids_df = pd.DataFrame(centroid_rows)
display(centroids_df)
```

Với DBSCAN:

```python
centroid_rows = []

for cluster_id, group in cube_df[cube_df["dbscan_cluster"] != -1].groupby("dbscan_cluster"):
    row = {
        "method": "DBSCAN",
        "cluster_id": cluster_id,
        "n_cells": len(group),
        "total_exposure": group["count_exposure"].sum(),
        "avg_exposure": group["count_exposure"].mean()
    }

    for col in ["latitude", "longitude", "week"]:
        if col in group.columns:
            row[f"centroid_{col}"] = np.average(
                group[col],
                weights=group["count_exposure"]
            )

    centroid_rows.append(row)

centroids_dbscan_df = pd.DataFrame(centroid_rows)
display(centroids_dbscan_df)
```

### 8.9. Xuất kết quả

```python
from pathlib import Path

REPORT_DIR = Path("reports")
FIGURE_DIR = REPORT_DIR / "figures"
REPORT_DIR.mkdir(exist_ok=True)
FIGURE_DIR.mkdir(exist_ok=True)

cube_df.to_csv(REPORT_DIR / "ground_zero_clustered_cuboids.csv", index=False)
centroids_df.to_csv(REPORT_DIR / "ground_zero_kmeans_centroids.csv", index=False)
centroids_dbscan_df.to_csv(REPORT_DIR / "ground_zero_dbscan_centroids.csv", index=False)
results_df.to_csv(REPORT_DIR / "ground_zero_clustering_metrics.csv", index=False)
```

## 9. Output mong đợi

Sau khi chạy notebook, cần có:

```text
notebook/clustering.ipynb
reports/ground_zero_clustered_cuboids.csv
reports/ground_zero_kmeans_centroids.csv
reports/ground_zero_dbscan_centroids.csv
reports/ground_zero_clustering_metrics.csv
reports/figures/ground_zero_clusters.png
```

## 10. Acceptance Criteria mapping

| Acceptance Criteria | Cách đáp ứng |
|---|---|
| Load dữ liệu bảng `Fact_Exposure` từ SQL vào `notebooks/clustering.ipynb` | Notebook dùng SQLAlchemy + `pd.read_sql` |
| Cài đặt DBSCAN hoặc K-Means | Dùng `sklearn.cluster.KMeans` và `DBSCAN` |
| Trích xuất centroid cụm lây nhiễm siêu tốc | Xuất `centroids_df` với weighted centroid theo `count_exposure` |

## 11. Kiểm thử

Nếu có module `src/clustering.py`, thêm test:

```text
src/clustering_tests.py
```

Test tối thiểu:

```python
def test_extract_cluster_centroids_returns_expected_columns():
    ...

def test_dbscan_labels_noise_as_minus_one():
    ...

def test_kmeans_cluster_count():
    ...
```

Nếu chỉ làm notebook, cần chạy thủ công và lưu output.

## 12. Nội dung báo cáo cho Task 9

Có thể viết:

```text
Sau khi các Iceberg Cuboids được trích xuất bằng Star-Cubing và lưu vào bảng Fact_Exposure, mỗi cuboid được xem như một điểm dữ liệu biểu diễn mức độ lây nhiễm theo không gian, thời gian và đặc trưng cá nhân. Các đặc trưng như location, week và count_exposure được chuẩn hóa, sau đó đưa vào K-Means và DBSCAN để tìm các cụm nguy cơ cao.

K-Means cung cấp các centroid rõ ràng cho từng cụm, trong khi DBSCAN giúp phát hiện các vùng mật độ cao và loại bỏ các điểm nhiễu. Centroid của mỗi cụm được tính có trọng số theo count_exposure, giúp xác định vị trí/thời điểm đại diện cho cụm lây nhiễm. Các cụm có tổng count_exposure cao được xem là ứng viên ground zero hoặc ổ lây nhiễm siêu tốc.
```

## 13. Definition of Done

Task 9 hoàn thành khi:

```text
[ ] Có notebook/clustering.ipynb.
[ ] Notebook load được Fact_Exposure từ SQL.
[ ] Có K-Means hoặc DBSCAN chạy được.
[ ] Có bảng kết quả cluster cho từng cuboid.
[ ] Có bảng centroid của từng cluster.
[ ] Có ít nhất một hình visualization trong reports/figures.
[ ] Có nhận xét trong notebook.
[ ] Không làm hỏng test cũ.
```
