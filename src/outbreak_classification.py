"""
Issue 10: Outbreak classification script (no notebook, no leakage)

Usage example:
    python src/outbreak_classification.py \
      --project-root . \
      --data-path data/processed/sashts_final_dataset.csv \
      --mapping-path data/processed/mapping_dict.json \
      --output-dir reports/issue_10_outbreak_classification \
      --model random_forest \
      --test-size 0.2 \
      --random-state 42

This script enforces leakage prevention and temporal split by `month_id`.
"""
from __future__ import annotations

import argparse
import json
import subprocess
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
            "Previous phase files are missing. Please complete/check ETL, Star Tree, Star-Cubing and Data Warehouse phases first: "
            f"{missing}"
        )


def run_pytests() -> None:
    """Run pytest and raise if tests fail."""
    try:
        res = subprocess.run(["pytest", "-q"], check=False)
    except FileNotFoundError:
        # pytest not installed in environment; user can still proceed
        return

    if res.returncode != 0:
        raise RuntimeError("Pre-existing tests failed (pytest exit code != 0). Fix tests before running classification.")


def load_dataset(data_path: Path) -> pd.DataFrame:
    if not data_path.exists():
        raise FileNotFoundError(f"Dataset not found: {data_path}. Run ETL phase first.")

    df = pd.read_csv(data_path)

    if df.empty:
        raise ValueError("Dataset is empty.")

    return df


def load_mapping(mapping_path: Path) -> Dict:
    if not mapping_path.exists():
        raise FileNotFoundError(f"Mapping dictionary not found: {mapping_path}. Run ETL phase first.")

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
            f"Got: {pair_mapping.get('Transmission')}"
        )


def create_outbreak_label(df: pd.DataFrame, target_col: str = "pair_sars", output_col: str = "outbreak_label") -> pd.DataFrame:
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


def temporal_train_test_split(df: pd.DataFrame, time_col: str = "month_id", test_size: float = 0.2) -> Tuple[pd.DataFrame, pd.DataFrame, List[int], List[int]]:
    if time_col not in df.columns:
        raise ValueError(f"Missing time column for temporal split: {time_col}")

    unique_times = sorted(df[time_col].unique())

    if len(unique_times) < 2:
        raise ValueError("Temporal split requires at least two unique time periods.")

    n_test_times = max(1, int(len(unique_times) * test_size))
    n_test_times = min(n_test_times, len(unique_times) - 1)

    train_times = unique_times[:-n_test_times]
    test_times = unique_times[-n_test_times:]

    train_df = df[df[time_col].isin(train_times)].copy()
    test_df = df[df[time_col].isin(test_times)].copy()

    return train_df, test_df, train_times, test_times


def validate_temporal_split(train_df: pd.DataFrame, test_df: pd.DataFrame, time_col: str = "month_id") -> None:
    max_train_time = train_df[time_col].max()
    min_test_time = test_df[time_col].min()

    if max_train_time >= min_test_time:
        raise ValueError(
            "Temporal leakage detected. "
            f"max_train_time={max_train_time}, min_test_time={min_test_time}"
        )


def validate_no_duplicate_feature_rows(X_train: pd.DataFrame, X_test: pd.DataFrame) -> int:
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


def evaluate_model(model, X_test, y_test) -> Tuple[Dict, str, np.ndarray, np.ndarray]:
    y_pred = model.predict(X_test)

    metrics = {
        "accuracy": float(accuracy_score(y_test, y_pred)),
        "precision_macro": float(precision_score(y_test, y_pred, average="macro", zero_division=0)),
        "recall_macro": float(recall_score(y_test, y_pred, average="macro", zero_division=0)),
        "f1_macro": float(f1_score(y_test, y_pred, average="macro", zero_division=0)),
        "precision_binary": float(precision_score(y_test, y_pred, zero_division=0)),
        "recall_binary": float(recall_score(y_test, y_pred, zero_division=0)),
        "f1_binary": float(f1_score(y_test, y_pred, zero_division=0)),
    }

    report = classification_report(
        y_test,
        y_pred,
        target_names=["Safe", "Outbreak"],
        zero_division=0,
    )

    cm = confusion_matrix(y_test, y_pred)

    return metrics, report, cm, y_pred


def save_outputs(output_dir: Path, model, metrics: Dict, report: str, cm: np.ndarray, y_pred: np.ndarray, test_df: pd.DataFrame, feature_cols: List[str]) -> None:
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

    # check previous phase files exist
    check_previous_phase_files(project_root)

    # run pytest for existing tests to ensure earlier phases ok
    run_pytests()

    df = load_dataset(Path(args.data_path))
    mapping = load_mapping(Path(args.mapping_path))

    validate_dataset_schema(df)
    validate_mapping(mapping)

    # create binary label and drop rows without label if any
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
