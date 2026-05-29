# Issue 10 — Dự báo bùng phát dịch (Classification)

## 0. Tóm tắt issue

**Issue:** Task 10 — Dự báo bùng phát dịch (Classification)  
**Mục tiêu:** Dự đoán xem một khối dữ liệu/case tiếp xúc có nguy cơ bùng phát dịch trong chu kỳ tiếp theo hay không dựa trên dữ liệu đã xử lý và các kết quả từ các phase trước.

Issue gốc yêu cầu:

- Gán nhãn `1` = **Bùng phát** và `0` = **An toàn** cho các khối dữ liệu.
- Huấn luyện mô hình phân loại `RandomForestClassifier` hoặc `XGBoost`.
- Đánh giá mô hình bằng các metric: `F1-score`, `Precision`, `Recall`.

Yêu cầu triển khai trong repo hiện tại:

- **Không tạo notebook mới.**
- Triển khai bằng **script Python**.
- Trước khi train classification, script phải kiểm tra đầy đủ:
  - Dataset ETL đã tồn tại và đúng schema.
  - Mapping dictionary đúng và giải mã được target.
  - Các output phase trước như Star Tree, Star-Cubing/Data Warehouse nếu có.
  - Không dùng các cột gây **data leakage**.
  - Train/test phải split theo thời gian để mô phỏng dự báo chu kỳ sau.
- Có test tự động.
- Có output lưu trong `reports/`.

---

## 1. Bối cảnh repo hiện tại

Repo hiện có cấu trúc chính:

```text
data/
  raw/
    sashts_contact_network.csv
    sashts_metadata.csv
  processed/
    sashts_final_dataset.csv
    mapping_dict.json
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

Dữ liệu đã được ETL ở phase trước:

```text
data/processed/sashts_final_dataset.csv
data/processed/mapping_dict.json
```

Dataset hiện tại có:

```text
140,542 rows
26 columns
0 missing values
```

Các cột hiện có:

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

Target gốc:

```text
pair_sars
```

Mapping trong `mapping_dict.json`:

```text
Both negative  -> 0
No transmission -> 1
Transmission -> 2
```

Đối với issue này, ta chuyển target thành binary classification:

```text
pair_sars == 2  -> outbreak_label = 1  (Bùng phát / Transmission)
pair_sars != 2  -> outbreak_label = 0  (An toàn / Non-outbreak)
```

Class distribution hiện tại:

```text
pair_sars = 0: 24,334 rows
pair_sars = 1: 52,328 rows
pair_sars = 2: 63,880 rows
```

Sau khi chuyển binary:

```text
outbreak_label = 1: 63,880 rows
outbreak_label = 0: 76,662 rows
```

---

## 2. Nguyên tắc quan trọng: chống data leakage

### 2.1. Vì sao phải chống leakage?

Classification trong issue này là **dự báo nguy cơ bùng phát**, không phải đọc lại kết quả đã biết.

Nếu dùng các cột liên quan trực tiếp đến trạng thái nhiễm hoặc số ca nhiễm làm feature, model sẽ học gần như trực tiếp từ đáp án. Khi đó metric sẽ cao nhưng không có giá trị dự báo thực tế.

Ví dụ các cột gây leakage:

```text
pair_sars
ind1_sars
ind2_sars
ind1_sus
ind2_sus
ind1_ixesarsvarf1
ind2_ixesarsvarf1
contacts_infected
hcir
hh_ar
```

Lý do:

| Cột | Vì sao leakage |
|---|---|
| `pair_sars` | target gốc, dùng nó làm feature là dùng đáp án |
| `ind1_sars`, `ind2_sars` | trạng thái SARS của từng cá nhân, gần trực tiếp quyết định `pair_sars` |
| `ind1_sus`, `ind2_sus` | trạng thái susceptible/self-index liên quan trực tiếp diễn giải nhiễm |
| `ind1_ixesarsvarf1`, `ind2_ixesarsvarf1` | biến thể virus, chỉ có ý nghĩa sau khi biết nhiễm |
| `contacts_infected` | số contact infected, là thông tin hậu nghiệm |
| `hcir` | household/contact infection rate, gần với kết quả bùng phát |
| `hh_ar` | household attack rate, là chỉ số sau khi có outcome |

### 2.2. Leakage policy bắt buộc

Script phải khai báo:

```python
LEAKAGE_COLUMNS = [
    "pair_sars",
    "outbreak_label",
    "ind1_sars",
    "ind2_sars",
    "ind1_sus",
    "ind2_sus",
    "ind1_ixesarsvarf1",
    "ind2_ixesarsvarf1",
    "contacts_infected",
    "hcir",
    "hh_ar",
]
```

Feature an toàn đề xuất:

```python
SAFE_FEATURE_COLUMNS = [
    "ind1_site",
    "ind1_sex",
    "ind1_index",
    "ind1_smokecignow1",
    "ind1_bmicat",
    "ind1_agegrp9",

    "ind2_site",
    "ind2_sex",
    "ind2_index",
    "ind2_smokecignow1",
    "ind2_bmicat",
    "ind2_agegrp9",

    "month_id",
    "duration_sec",
    "no_ts",
    "contacts",
]
```

Có thể thêm feature từ cube/phase trước nếu feature đó **không được tính bằng outcome tương lai hoặc outcome test set**.

### 2.3. Không dùng random row split

Không dùng:

```python
train_test_split(df, test_size=0.2, random_state=42)
```

Lý do:

- Dữ liệu dịch tễ có yếu tố thời gian.
- Dự báo outbreak phải dùng dữ liệu quá khứ để dự báo tương lai.
- Random split có thể đưa các mẫu rất giống nhau vào cả train và test.
- Random split dễ gây temporal leakage.

Bắt buộc dùng:

```text
Temporal split theo month_id
```

Ví dụ:

```text
Train: các tháng cũ
Test : các tháng mới
```

---

## 3. Kiểm tra bắt buộc trước khi cài đặt classification

Copilot/script phải kiểm tra toàn bộ phần này trước khi train.

### 3.1. Kiểm tra file dataset và mapping

Bắt buộc kiểm tra tồn tại:

```text
data/processed/sashts_final_dataset.csv
data/processed/mapping_dict.json
```

Nếu thiếu, báo lỗi:

```text
Processed dataset or mapping dictionary not found.
Run ETL phase first: notebook/00_ETL.ipynb
```

### 3.2. Kiểm tra schema dataset

Bắt buộc có các cột:

```python
REQUIRED_COLUMNS = [
    "pair_sars",
    "month_id",
    "duration_sec",
    "no_ts",
    "contacts",

    "ind1_site",
    "ind1_sex",
    "ind1_index",
    "ind1_smokecignow1",
    "ind1_bmicat",
    "ind1_agegrp9",

    "ind2_site",
    "ind2_sex",
    "ind2_index",
    "ind2_smokecignow1",
    "ind2_bmicat",
    "ind2_agegrp9",
]
```

Nếu thiếu cột nào, dừng script và báo rõ.

### 3.3. Kiểm tra mapping target

`mapping_dict.json` phải có:

```python
mapping["pair_sars"]["Transmission"] == 2
```

Nếu không đúng, dừng script.

### 3.4. Kiểm tra missing value

Dataset hiện tại không có missing value. Tuy nhiên script vẫn phải kiểm tra:

```python
missing_count = df.isna().sum().sum()
```

Nếu có missing:

- Với numeric/categorical encoded columns: có thể fill bằng median/mode.
- Nhưng tốt nhất issue này nên dừng và yêu cầu kiểm tra lại ETL nếu missing xuất hiện ở required columns.

### 3.5. Kiểm tra phase trước

Trước khi train classification, script hoặc hướng dẫn phải kiểm tra:

```bash
python -m pytest -q
```

Các test phase trước cần pass:

```text
src/star_tree_tests.py
src/star_cubing_tests.py
src/algorithm/starcubing_tests.py
```

Ngoài ra kiểm tra các file phase trước có tồn tại:

```text
src/star_tree.py
src/star_cubing.py
src/algorithm/starcubing.py
src/db_manager.py
src/data_loader.py
sql/schema.sql
docs/STAR_TREE.md
docs/STAR_CUBING.md
```

Nếu các phase trước chưa pass, không nên tiếp tục classification.

---

## 4. File cần tạo cho Issue 10

Tạo mới:

```text
src/outbreak_classification.py
src/outbreak_classification_tests.py
```

Tạo thư mục output khi chạy:

```text
reports/issue_10_outbreak_classification/
```

Output kỳ vọng:

```text
reports/issue_10_outbreak_classification/
  metrics.json
  classification_report.txt
  confusion_matrix.csv
  feature_importance.csv
  predictions.csv
  model.joblib
```

Không cần tạo notebook.

---

## 5. Thiết kế script `src/outbreak_classification.py`

### 5.1. CLI đề xuất

Script phải chạy được bằng lệnh:

```bash
python src/outbreak_classification.py \
  --data-path data/processed/sashts_final_dataset.csv \
  --mapping-path data/processed/mapping_dict.json \
  --output-dir reports/issue_10_outbreak_classification \
  --model random_forest \
  --test-size 0.2 \
  --random-state 42
```

Tùy chọn model:

```text
random_forest
xgboost
```

Nếu chưa muốn thêm dependency XGBoost, mặc định dùng `random_forest`.

### 5.2. Luồng script

Script phải chạy theo thứ tự:

```text
1. Parse CLI arguments.
2. Check previous phase files.
3. Load processed dataset.
4. Load mapping dictionary.
5. Validate dataset schema.
6. Validate mapping dictionary.
7. Create binary outbreak label.
8. Select safe feature columns.
9. Validate no leakage columns are used.
10. Temporal train/test split by month_id.
11. Validate temporal split.
12. Train classifier.
13. Evaluate with Precision, Recall, F1-score.
14. Save metrics, report, confusion matrix, predictions, feature importance, model.
```

---

## 6. Code khung chuẩn cho script

Copilot nên cài đặt theo khung dưới đây.

```python
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Dict, List, Tuple

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import (
    classification_report,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
    accuracy_score,
)
from sklearn.utils.class_weight import compute_class_weight


REQUIRED_COLUMNS = [
    "pair_sars",
    "month_id",
    "duration_sec",
    "no_ts",
    "contacts",

    "ind1_site",
    "ind1_sex",
    "ind1_index",
    "ind1_smokecignow1",
    "ind1_bmicat",
    "ind1_agegrp9",

    "ind2_site",
    "ind2_sex",
    "ind2_index",
    "ind2_smokecignow1",
    "ind2_bmicat",
    "ind2_agegrp9",
]

LEAKAGE_COLUMNS = [
    "pair_sars",
    "outbreak_label",
    "ind1_sars",
    "ind2_sars",
    "ind1_sus",
    "ind2_sus",
    "ind1_ixesarsvarf1",
    "ind2_ixesarsvarf1",
    "contacts_infected",
    "hcir",
    "hh_ar",
]

SAFE_FEATURE_COLUMNS = [
    "ind1_site",
    "ind1_sex",
    "ind1_index",
    "ind1_smokecignow1",
    "ind1_bmicat",
    "ind1_agegrp9",

    "ind2_site",
    "ind2_sex",
    "ind2_index",
    "ind2_smokecignow1",
    "ind2_bmicat",
    "ind2_agegrp9",

    "month_id",
    "duration_sec",
    "no_ts",
    "contacts",
]


def check_previous_phase_files(project_root: Path) -> None:
    required_paths = [
        project_root / "src" / "star_tree.py",
        project_root / "src" / "star_cubing.py",
        project_root / "src" / "algorithm" / "starcubing.py",
        project_root / "src" / "db_manager.py",
        project_root / "src" / "data_loader.py",
        project_root / "sql" / "schema.sql",
        project_root / "docs" / "STAR_TREE.md",
        project_root / "docs" / "STAR_CUBING.md",
    ]

    missing = [str(path) for path in required_paths if not path.exists()]

    if missing:
        raise FileNotFoundError(
            "Previous phase files are missing. "
            "Please complete/check ETL, Star Tree, Star-Cubing and Data Warehouse phases first: "
            f"{missing}"
        )


def load_dataset(data_path: Path) -> pd.DataFrame:
    if not data_path.exists():
        raise FileNotFoundError(
            f"Dataset not found: {data_path}. Run ETL phase first."
        )

    df = pd.read_csv(data_path)

    if df.empty:
        raise ValueError("Dataset is empty.")

    return df


def load_mapping(mapping_path: Path) -> Dict:
    if not mapping_path.exists():
        raise FileNotFoundError(
            f"Mapping dictionary not found: {mapping_path}. Run ETL phase first."
        )

    with mapping_path.open("r", encoding="utf-8") as f:
        mapping = json.load(f)

    return mapping


def validate_dataset_schema(df: pd.DataFrame) -> None:
    missing_cols = [col for col in REQUIRED_COLUMNS if col not in df.columns]

    if missing_cols:
        raise ValueError(f"Dataset is missing required columns: {missing_cols}")

    missing_values = df[REQUIRED_COLUMNS].isna().sum()
    bad_missing = missing_values[missing_values > 0]

    if len(bad_missing) > 0:
        raise ValueError(
            "Required columns contain missing values. "
            f"Missing summary: {bad_missing.to_dict()}"
        )


def validate_mapping(mapping: Dict) -> None:
    if "pair_sars" not in mapping:
        raise ValueError("mapping_dict.json must contain 'pair_sars' mapping.")

    pair_mapping = mapping["pair_sars"]

    if "Transmission" not in pair_mapping:
        raise ValueError("'pair_sars' mapping must contain 'Transmission'.")

    if pair_mapping["Transmission"] != 2:
        raise ValueError(
            "Expected mapping['pair_sars']['Transmission'] == 2. "
            f"Got: {pair_mapping['Transmission']}"
        )


def create_outbreak_label(
    df: pd.DataFrame,
    target_col: str = "pair_sars",
    output_col: str = "outbreak_label",
) -> pd.DataFrame:
    df = df.copy()
    df[output_col] = (df[target_col] == 2).astype(int)
    return df


def select_feature_columns(df: pd.DataFrame) -> List[str]:
    available = [col for col in SAFE_FEATURE_COLUMNS if col in df.columns]

    if not available:
        raise ValueError("No safe feature columns are available.")

    return available


def validate_no_leakage(feature_cols: List[str]) -> None:
    leakage_used = sorted(set(feature_cols) & set(LEAKAGE_COLUMNS))

    if leakage_used:
        raise ValueError(
            "Data leakage detected. These leakage columns are used as features: "
            f"{leakage_used}"
        )


def temporal_train_test_split(
    df: pd.DataFrame,
    time_col: str = "month_id",
    test_size: float = 0.2,
) -> Tuple[pd.DataFrame, pd.DataFrame, List[int], List[int]]:
    if time_col not in df.columns:
        raise ValueError(f"Missing time column for temporal split: {time_col}")

    unique_times = sorted(df[time_col].unique())

    if len(unique_times) < 2:
        raise ValueError(
            "Temporal split requires at least two unique time periods."
        )

    n_test_times = max(1, int(len(unique_times) * test_size))
    n_test_times = min(n_test_times, len(unique_times) - 1)

    train_times = unique_times[:-n_test_times]
    test_times = unique_times[-n_test_times:]

    train_df = df[df[time_col].isin(train_times)].copy()
    test_df = df[df[time_col].isin(test_times)].copy()

    return train_df, test_df, train_times, test_times


def validate_temporal_split(
    train_df: pd.DataFrame,
    test_df: pd.DataFrame,
    time_col: str = "month_id",
) -> None:
    max_train_time = train_df[time_col].max()
    min_test_time = test_df[time_col].min()

    if max_train_time >= min_test_time:
        raise ValueError(
            "Temporal leakage detected. "
            f"max_train_time={max_train_time}, min_test_time={min_test_time}"
        )


def validate_no_duplicate_feature_rows(
    X_train: pd.DataFrame,
    X_test: pd.DataFrame,
) -> int:
    train_hash = pd.util.hash_pandas_object(X_train, index=False)
    test_hash = pd.util.hash_pandas_object(X_test, index=False)

    overlap = set(train_hash) & set(test_hash)
    return len(overlap)


def build_random_forest(random_state: int = 42) -> RandomForestClassifier:
    return RandomForestClassifier(
        n_estimators=300,
        max_depth=None,
        min_samples_split=4,
        min_samples_leaf=2,
        class_weight="balanced",
        random_state=random_state,
        n_jobs=-1,
    )


def evaluate_model(model, X_test, y_test) -> Dict:
    y_pred = model.predict(X_test)

    metrics = {
        "accuracy": accuracy_score(y_test, y_pred),
        "precision_macro": precision_score(y_test, y_pred, average="macro", zero_division=0),
        "recall_macro": recall_score(y_test, y_pred, average="macro", zero_division=0),
        "f1_macro": f1_score(y_test, y_pred, average="macro", zero_division=0),
        "precision_binary": precision_score(y_test, y_pred, zero_division=0),
        "recall_binary": recall_score(y_test, y_pred, zero_division=0),
        "f1_binary": f1_score(y_test, y_pred, zero_division=0),
    }

    report = classification_report(
        y_test,
        y_pred,
        target_names=["Safe", "Outbreak"],
        zero_division=0,
    )

    cm = confusion_matrix(y_test, y_pred)

    return metrics, report, cm, y_pred


def save_outputs(
    output_dir: Path,
    model,
    metrics: Dict,
    report: str,
    cm: np.ndarray,
    y_pred: np.ndarray,
    test_df: pd.DataFrame,
    feature_cols: List[str],
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)

    with (output_dir / "metrics.json").open("w", encoding="utf-8") as f:
        json.dump(metrics, f, ensure_ascii=False, indent=2)

    with (output_dir / "classification_report.txt").open("w", encoding="utf-8") as f:
        f.write(report)

    pd.DataFrame(
        cm,
        index=["Actual_Safe", "Actual_Outbreak"],
        columns=["Pred_Safe", "Pred_Outbreak"],
    ).to_csv(output_dir / "confusion_matrix.csv", encoding="utf-8-sig")

    predictions_df = test_df.copy()
    predictions_df["prediction"] = y_pred
    predictions_df.to_csv(output_dir / "predictions.csv", index=False, encoding="utf-8-sig")

    if hasattr(model, "feature_importances_"):
        fi_df = pd.DataFrame({
            "feature": feature_cols,
            "importance": model.feature_importances_,
        }).sort_values("importance", ascending=False)

        fi_df.to_csv(output_dir / "feature_importance.csv", index=False, encoding="utf-8-sig")

    joblib.dump(model, output_dir / "model.joblib")


def run_pipeline(args: argparse.Namespace) -> None:
    project_root = Path(args.project_root).resolve()

    check_previous_phase_files(project_root)

    df = load_dataset(Path(args.data_path))
    mapping = load_mapping(Path(args.mapping_path))

    validate_dataset_schema(df)
    validate_mapping(mapping)

    df = create_outbreak_label(df)

    feature_cols = select_feature_columns(df)
    validate_no_leakage(feature_cols)

    train_df, test_df, train_times, test_times = temporal_train_test_split(
        df,
        time_col="month_id",
        test_size=args.test_size,
    )

    validate_temporal_split(train_df, test_df, time_col="month_id")

    X_train = train_df[feature_cols]
    y_train = train_df["outbreak_label"]

    X_test = test_df[feature_cols]
    y_test = test_df["outbreak_label"]

    duplicate_count = validate_no_duplicate_feature_rows(X_train, X_test)

    model = build_random_forest(random_state=args.random_state)
    model.fit(X_train, y_train)

    metrics, report, cm, y_pred = evaluate_model(model, X_test, y_test)

    metrics.update({
        "train_rows": int(len(train_df)),
        "test_rows": int(len(test_df)),
        "train_months": [int(x) for x in train_times],
        "test_months": [int(x) for x in test_times],
        "feature_columns": feature_cols,
        "duplicate_feature_hashes_across_split": int(duplicate_count),
    })

    save_outputs(
        output_dir=Path(args.output_dir),
        model=model,
        metrics=metrics,
        report=report,
        cm=cm,
        y_pred=y_pred,
        test_df=test_df,
        feature_cols=feature_cols,
    )

    print("Issue 10 outbreak classification completed.")
    print("Output directory:", Path(args.output_dir).resolve())
    print(json.dumps(metrics, indent=2))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Issue 10: Outbreak classification without data leakage."
    )

    parser.add_argument("--project-root", default=".")
    parser.add_argument("--data-path", default="data/processed/sashts_final_dataset.csv")
    parser.add_argument("--mapping-path", default="data/processed/mapping_dict.json")
    parser.add_argument("--output-dir", default="reports/issue_10_outbreak_classification")
    parser.add_argument("--model", default="random_forest", choices=["random_forest"])
    parser.add_argument("--test-size", type=float, default=0.2)
    parser.add_argument("--random-state", type=int, default=42)

    return parser.parse_args()


if __name__ == "__main__":
    run_pipeline(parse_args())
```

---

## 7. Test cần tạo: `src/outbreak_classification_tests.py`

Test cần kiểm tra:

```text
1. Target binary được tạo đúng.
2. Leakage columns không xuất hiện trong feature list.
3. Temporal split không chồng thời gian.
4. Mapping pair_sars hợp lệ.
5. Script có thể chạy với sample dataframe nhỏ.
```

Code test đề xuất:

```python
import json
from pathlib import Path

import pandas as pd
import pytest

from src.outbreak_classification import (
    create_outbreak_label,
    validate_no_leakage,
    temporal_train_test_split,
    validate_temporal_split,
    validate_mapping,
    SAFE_FEATURE_COLUMNS,
)


def test_create_outbreak_label():
    df = pd.DataFrame({"pair_sars": [0, 1, 2, 2]})
    out = create_outbreak_label(df)

    assert out["outbreak_label"].tolist() == [0, 0, 1, 1]


def test_validate_no_leakage_passes_for_safe_features():
    validate_no_leakage(SAFE_FEATURE_COLUMNS)


def test_validate_no_leakage_raises_for_target():
    with pytest.raises(ValueError):
        validate_no_leakage(["pair_sars", "month_id"])


def test_temporal_split_is_ordered():
    df = pd.DataFrame({
        "month_id": [202001, 202001, 202002, 202002, 202003, 202003],
        "pair_sars": [0, 1, 2, 0, 1, 2],
    })

    train_df, test_df, train_times, test_times = temporal_train_test_split(
        df,
        time_col="month_id",
        test_size=0.34,
    )

    validate_temporal_split(train_df, test_df, time_col="month_id")

    assert max(train_times) < min(test_times)


def test_validate_mapping_accepts_transmission_code():
    mapping = {
        "pair_sars": {
            "Both negative": 0,
            "No transmission": 1,
            "Transmission": 2,
        }
    }

    validate_mapping(mapping)


def test_validate_mapping_rejects_wrong_transmission_code():
    mapping = {
        "pair_sars": {
            "Both negative": 0,
            "No transmission": 1,
            "Transmission": 99,
        }
    }

    with pytest.raises(ValueError):
        validate_mapping(mapping)
```

Chạy test:

```bash
python -m pytest -q
```

---

## 8. Acceptance Criteria Mapping

### AC1 — Gán nhãn `1` bùng phát và `0` an toàn

Đáp ứng bằng:

```python
df["outbreak_label"] = (df["pair_sars"] == 2).astype(int)
```

Mapping:

```text
pair_sars == 2 -> Transmission -> outbreak_label = 1
pair_sars in {0, 1} -> Safe/Non-outbreak -> outbreak_label = 0
```

### AC2 — Huấn luyện mô hình phân loại RandomForestClassifier hoặc XGBoost

Đáp ứng bằng:

```python
RandomForestClassifier(...)
```

File:

```text
src/outbreak_classification.py
```

### AC3 — Đánh giá bằng F1-score, Precision, Recall

Đáp ứng bằng:

```python
precision_score
recall_score
f1_score
classification_report
confusion_matrix
```

Output:

```text
metrics.json
classification_report.txt
confusion_matrix.csv
```

---

## 9. Lệnh chạy hoàn chỉnh

### 9.1. Chạy toàn bộ tests phase trước và Issue 10

```bash
python -m pytest -q
```

### 9.2. Chạy classification script

```bash
python src/outbreak_classification.py \
  --project-root . \
  --data-path data/processed/sashts_final_dataset.csv \
  --mapping-path data/processed/mapping_dict.json \
  --output-dir reports/issue_10_outbreak_classification \
  --model random_forest \
  --test-size 0.2 \
  --random-state 42
```

### 9.3. Kiểm tra output

```bash
dir reports\issue_10_outbreak_classification
```

hoặc Linux/macOS:

```bash
ls -lah reports/issue_10_outbreak_classification
```

Expected files:

```text
metrics.json
classification_report.txt
confusion_matrix.csv
feature_importance.csv
predictions.csv
model.joblib
```

---

## 10. Nội dung báo cáo cho Issue 10

Phần báo cáo nên viết theo cấu trúc:

### 10.1. Mục tiêu

Mục tiêu của Issue 10 là xây dựng mô hình classification để dự báo nguy cơ bùng phát dịch trong chu kỳ tiếp theo dựa trên dữ liệu cube/contact đã được xử lý ở các phase trước.

### 10.2. Target labeling

Target gốc `pair_sars` có ba trạng thái:

```text
0 = Both negative
1 = No transmission
2 = Transmission
```

Để phục vụ bài toán classification nhị phân, label được chuyển thành:

```text
1 = Outbreak / Transmission
0 = Safe / Non-outbreak
```

### 10.3. Leakage prevention

Các cột liên quan trực tiếp đến outcome như `pair_sars`, `ind1_sars`, `ind2_sars`, `contacts_infected`, `hcir`, `hh_ar` bị loại khỏi feature set để tránh data leakage. Ngoài ra, dữ liệu được chia train/test theo `month_id` thay vì random split để mô phỏng tình huống dự báo tương lai.

### 10.4. Model

Mô hình chính là `RandomForestClassifier` với `class_weight="balanced"` để xử lý mất cân bằng lớp. Model học từ các feature an toàn như site, giới tính, age group, BMI, smoking status, duration, contact count và month id.

### 10.5. Evaluation

Mô hình được đánh giá bằng:

```text
Precision
Recall
F1-score
Confusion Matrix
```

Trong đó F1-score được ưu tiên vì bài toán outbreak thường cần cân bằng giữa phát hiện đúng ca bùng phát và giảm cảnh báo sai.

---

## 11. Definition of Done

Issue 10 hoàn thành khi:

```text
[ ] Có file src/outbreak_classification.py.
[ ] Có file src/outbreak_classification_tests.py.
[ ] Script chạy được bằng CLI, không cần notebook.
[ ] Script kiểm tra dữ liệu processed và mapping dictionary.
[ ] Script kiểm tra file/code phase trước.
[ ] Script tạo binary label đúng từ pair_sars.
[ ] Script loại toàn bộ leakage columns.
[ ] Script split train/test theo month_id.
[ ] Script validate không temporal leakage.
[ ] Script train RandomForestClassifier.
[ ] Script xuất Precision, Recall, F1-score.
[ ] Script lưu metrics/report/confusion matrix/predictions/model.
[ ] pytest pass.
[ ] PR description có `Closes #10`.
```

---

## 12. PR description đề xuất

```markdown
## Summary

This PR implements Issue #10: outbreak classification.

### Main changes
- Add `src/outbreak_classification.py` script.
- Add binary outbreak labeling from `pair_sars`.
- Add strict leakage prevention policy.
- Use temporal train/test split by `month_id`.
- Train `RandomForestClassifier` for outbreak prediction.
- Evaluate with Precision, Recall, F1-score and confusion matrix.
- Save metrics, predictions, feature importance and model artifact.
- Add unit tests for target labeling, leakage prevention and temporal split.

### Leakage prevention
The classifier excludes target-derived columns such as:
- `pair_sars`
- `ind1_sars`, `ind2_sars`
- `ind1_sus`, `ind2_sus`
- `ind1_ixesarsvarf1`, `ind2_ixesarsvarf1`
- `contacts_infected`
- `hcir`
- `hh_ar`

The train/test split is temporal using `month_id` to avoid future information leaking into training.

## Test

```bash
python -m pytest -q
```

```bash
python src/outbreak_classification.py \
  --project-root . \
  --data-path data/processed/sashts_final_dataset.csv \
  --mapping-path data/processed/mapping_dict.json \
  --output-dir reports/issue_10_outbreak_classification \
  --model random_forest \
  --test-size 0.2 \
  --random-state 42
```

## Related Issue

Closes #10
```
