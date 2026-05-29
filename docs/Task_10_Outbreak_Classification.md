# Task 10: Dự báo bùng phát dịch bằng Classification

## 1. Mục tiêu

Dự đoán xem một khu vực/cuboid có nguy cơ **bùng phát dịch trong chu kỳ tiếp theo** hay không dựa trên mật độ dữ liệu Cube.

Theo issue, task này cần hoàn thành:

- Gán nhãn `1 = Bùng phát`, `0 = An toàn` cho các khối dữ liệu.
- Huấn luyện mô hình phân loại `RandomForestClassifier` hoặc `XGBoost`.
- Đánh giá mô hình bằng các metric: `F1-score`, `Precision`, `Recall`.

## 2. Trạng thái repo hiện tại liên quan đến issue

Repo hiện đã có:

```text
data/processed/sashts_final_dataset.csv
sql/schema.sql
src/db_manager.py
src/data_loader.py
src/star_tree.py
src/star_cubing.py
src/algorithm/starcubing.py
```

Task 10 nên dùng đầu ra từ các bước trước:

```text
Fact_Exposure
Iceberg Cuboids
count_exposure
Time / Location / Patient dimensions
```

Task 10 nằm sau Task 9 vì có thể tận dụng kết quả cluster hoặc centroid làm feature bổ sung, nhưng không bắt buộc.

## 3. Ý tưởng bài toán

Mỗi dòng dữ liệu là một đơn vị phân tích dịch tễ, ví dụ:

```text
location = district_A
time = week_03
age_group = adult
sex = female
count_exposure = 42
```

Ta muốn dự đoán:

```text
Trong chu kỳ tiếp theo, khu vực/khối này có bùng phát không?
```

Nhãn:

```text
1 = Bùng phát
0 = An toàn
```

Có thể định nghĩa bùng phát bằng ngưỡng:

```text
Nếu count_exposure_next >= outbreak_threshold → label = 1
Ngược lại → label = 0
```

Hoặc dùng percentile:

```text
Top 20% count_exposure_next cao nhất → label = 1
Phần còn lại → label = 0
```

## 4. File nên tạo / chỉnh sửa

### 4.1. Notebook chính

Tạo:

```text
notebook/classification.ipynb
```

Notebook nên có các phần:

```text
1. Load dữ liệu cube/fact
2. Join dimension nếu cần
3. Tạo feature theo chu kỳ hiện tại
4. Tạo label theo chu kỳ tiếp theo
5. Train/test split theo thời gian
6. Train RandomForestClassifier
7. Train XGBoost nếu có
8. Evaluate Precision / Recall / F1-score
9. Feature importance
10. Lưu kết quả vào reports/
```

### 4.2. Module tùy chọn

Có thể tạo:

```text
src/classification.py
```

Chứa:

```python
load_cube_dataset(...)
create_outbreak_labels(...)
prepare_classification_features(...)
train_random_forest(...)
evaluate_classifier(...)
export_classification_results(...)
```

## 5. Thiết kế label bùng phát

### 5.1. Dữ liệu cần có

Cần dữ liệu dạng:

```text
location_id
time_id
count_exposure
```

Mục tiêu là tạo nhãn dựa trên `count_exposure` của chu kỳ tiếp theo.

### 5.2. Tạo next-cycle exposure

Nếu dùng `time_id` hoặc `week`:

```python
df = df.sort_values(["location_id", "time_id"])

df["next_count_exposure"] = (
    df.groupby("location_id")["count_exposure"]
    .shift(-1)
)
```

Nếu có nhiều dimension khác:

```python
group_keys = ["location_id", "age_group", "sex"]

df["next_count_exposure"] = (
    df.sort_values(group_keys + ["time_id"])
      .groupby(group_keys)["count_exposure"]
      .shift(-1)
)
```

### 5.3. Cách gán nhãn

Cách 1: dùng ngưỡng cố định

```python
OUTBREAK_THRESHOLD = 10

df["outbreak_label"] = (
    df["next_count_exposure"] >= OUTBREAK_THRESHOLD
).astype(int)
```

Cách 2: dùng percentile

```python
threshold = df["next_count_exposure"].quantile(0.80)

df["outbreak_label"] = (
    df["next_count_exposure"] >= threshold
).astype(int)
```

Khuyến nghị:

```text
Dùng percentile 80% hoặc 75% nếu dữ liệu mất cân bằng.
```

## 6. Feature đề xuất

Feature có thể gồm:

```text
count_exposure
rolling_mean_exposure
rolling_max_exposure
previous_count_exposure
location_id / grid_id
week / month
gender / age_group
cluster_id từ Task 9 nếu có
```

Ví dụ tạo feature xu hướng:

```python
df["prev_count_exposure"] = (
    df.groupby("location_id")["count_exposure"].shift(1)
)

df["rolling_mean_3"] = (
    df.groupby("location_id")["count_exposure"]
      .rolling(window=3, min_periods=1)
      .mean()
      .reset_index(level=0, drop=True)
)
```

## 7. Code khung notebook

### 7.1. Import

```python
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

from sqlalchemy import create_engine
from sklearn.model_selection import train_test_split
from sklearn.compose import ColumnTransformer
from sklearn.preprocessing import StandardScaler, OneHotEncoder
from sklearn.pipeline import Pipeline
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import (
    classification_report,
    confusion_matrix,
    precision_score,
    recall_score,
    f1_score,
    roc_auc_score
)
```

### 7.2. Load dữ liệu

```python
from src.config import DATABASE_URL

engine = create_engine(DATABASE_URL)

query = """
SELECT *
FROM Fact_Exposure
"""

df = pd.read_sql(query, engine)

display(df.head())
print(df.shape)
```

Nếu cần join:

```python
query = """
SELECT
    f.*,
    t.time_id,
    t.week,
    t.month,
    l.location_id,
    l.grid_id,
    p.patient_id,
    p.age_group,
    p.sex
FROM Fact_Exposure f
LEFT JOIN Dim_Time t ON f.time_id = t.time_id
LEFT JOIN Dim_Location l ON f.location_id = l.location_id
LEFT JOIN Dim_Patient p ON f.patient_id = p.patient_id
"""

df = pd.read_sql(query, engine)
```

### 7.3. Tạo label

```python
df = df.sort_values(["location_id", "time_id"])

df["next_count_exposure"] = (
    df.groupby("location_id")["count_exposure"]
    .shift(-1)
)

df = df.dropna(subset=["next_count_exposure"]).copy()

threshold = df["next_count_exposure"].quantile(0.80)

df["outbreak_label"] = (
    df["next_count_exposure"] >= threshold
).astype(int)

print("Outbreak threshold:", threshold)
print(df["outbreak_label"].value_counts(normalize=True))
```

### 7.4. Tạo feature

```python
df["prev_count_exposure"] = (
    df.groupby("location_id")["count_exposure"].shift(1)
)

df["prev_count_exposure"] = df["prev_count_exposure"].fillna(0)

numeric_features = [
    "count_exposure",
    "prev_count_exposure",
    "week",
    "month"
]

categorical_features = [
    "location_id",
    "age_group",
    "sex"
]

numeric_features = [col for col in numeric_features if col in df.columns]
categorical_features = [col for col in categorical_features if col in df.columns]

X = df[numeric_features + categorical_features]
y = df["outbreak_label"]
```

### 7.5. Split theo thời gian

Không nên shuffle nếu dự báo theo thời gian.

```python
df = df.sort_values("time_id")

split_idx = int(len(df) * 0.8)

train_df = df.iloc[:split_idx]
test_df = df.iloc[split_idx:]

X_train = train_df[numeric_features + categorical_features]
y_train = train_df["outbreak_label"]

X_test = test_df[numeric_features + categorical_features]
y_test = test_df["outbreak_label"]
```

### 7.6. Train Random Forest

```python
preprocessor = ColumnTransformer(
    transformers=[
        ("num", StandardScaler(), numeric_features),
        ("cat", OneHotEncoder(handle_unknown="ignore"), categorical_features)
    ]
)

rf_model = Pipeline(
    steps=[
        ("preprocess", preprocessor),
        ("classifier", RandomForestClassifier(
            n_estimators=200,
            max_depth=None,
            min_samples_leaf=2,
            random_state=42,
            class_weight="balanced"
        ))
    ]
)

rf_model.fit(X_train, y_train)
```

### 7.7. Evaluate

```python
y_pred = rf_model.predict(X_test)
y_proba = rf_model.predict_proba(X_test)[:, 1]

print(classification_report(y_test, y_pred))

metrics = {
    "precision": precision_score(y_test, y_pred, zero_division=0),
    "recall": recall_score(y_test, y_pred, zero_division=0),
    "f1_score": f1_score(y_test, y_pred, zero_division=0),
    "roc_auc": roc_auc_score(y_test, y_proba)
}

metrics_df = pd.DataFrame([metrics])
display(metrics_df)

cm = confusion_matrix(y_test, y_pred)
display(pd.DataFrame(cm, index=["Actual_0", "Actual_1"], columns=["Pred_0", "Pred_1"]))
```

### 7.8. Lưu kết quả

```python
from pathlib import Path

REPORT_DIR = Path("reports")
REPORT_DIR.mkdir(exist_ok=True)

metrics_df.to_csv(REPORT_DIR / "outbreak_classification_metrics.csv", index=False)

test_output = test_df.copy()
test_output["predicted_label"] = y_pred
test_output["predicted_probability"] = y_proba

test_output.to_csv(REPORT_DIR / "outbreak_classification_predictions.csv", index=False)
```

## 8. Metric cần giải thích

### Precision

Trong các vùng model dự đoán là bùng phát, có bao nhiêu vùng thật sự bùng phát.

```text
Precision cao → ít cảnh báo giả.
```

### Recall

Trong các vùng thật sự bùng phát, model phát hiện được bao nhiêu vùng.

```text
Recall cao → ít bỏ sót vùng nguy hiểm.
```

### F1-score

Trung bình điều hòa giữa Precision và Recall.

```text
F1 cao → mô hình cân bằng tốt giữa cảnh báo giả và bỏ sót.
```

Trong bài dịch tễ, **Recall** thường quan trọng vì bỏ sót vùng bùng phát có thể nguy hiểm hơn cảnh báo giả.

## 9. Acceptance Criteria mapping

| Acceptance Criteria | Cách đáp ứng |
|---|---|
| Gán nhãn `1 = Bùng phát`, `0 = An toàn` | Tạo `outbreak_label` từ `next_count_exposure` |
| Huấn luyện RandomForest hoặc XGBoost | Dùng `RandomForestClassifier` pipeline |
| Đánh giá bằng F1-score, Precision, Recall | Dùng `classification_report`, `precision_score`, `recall_score`, `f1_score` |

## 10. Output mong đợi

```text
notebook/classification.ipynb
reports/outbreak_classification_metrics.csv
reports/outbreak_classification_predictions.csv
reports/figures/outbreak_confusion_matrix.png
reports/figures/outbreak_feature_importance.png
```

## 11. Test đề xuất

Nếu tạo `src/classification.py`, thêm:

```text
src/classification_tests.py
```

Test:

```python
def test_create_outbreak_labels_binary():
    ...

def test_create_outbreak_labels_uses_next_cycle():
    ...

def test_evaluate_classifier_returns_required_metrics():
    ...
```

## 12. Nội dung báo cáo cho Task 10

Có thể viết:

```text
Sau khi trích xuất các cuboids từ Star-Cubing, mỗi cuboid được xem là một đơn vị quan sát mô tả mức độ tiếp xúc theo không gian, thời gian và đặc trưng cá nhân. Để chuyển bài toán sang phân loại, nhãn bùng phát được tạo dựa trên số lượng phơi nhiễm ở chu kỳ tiếp theo. Nếu `next_count_exposure` vượt ngưỡng percentile đã chọn, cuboid được gán nhãn 1, ngược lại là 0.

Mô hình Random Forest được sử dụng vì có khả năng xử lý dữ liệu phi tuyến, không yêu cầu giả định phân phối và cho phép phân tích feature importance. Kết quả được đánh giá bằng Precision, Recall và F1-score. Trong ngữ cảnh dịch tễ học, Recall đặc biệt quan trọng vì việc bỏ sót các vùng có nguy cơ bùng phát có thể gây hậu quả nghiêm trọng.
```

## 13. Definition of Done

```text
[ ] Có notebook/classification.ipynb.
[ ] Tạo được nhãn outbreak_label.
[ ] Train được RandomForestClassifier hoặc XGBoost.
[ ] Có Precision, Recall, F1-score.
[ ] Có confusion matrix.
[ ] Có file prediction output.
[ ] Có nhận xét trong notebook.
[ ] Không làm hỏng test cũ.
```
