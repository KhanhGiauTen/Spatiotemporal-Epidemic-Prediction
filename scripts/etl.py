"""ETL utilities for the SASHTS epidemic/contact-network dataset.

This module contains the transformation logic that used to live directly in
the EDA/ETL notebook. The notebook can import and call ``run_etl`` while keeping
the processing steps reusable from scripts or tests.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


DEFAULT_COLUMNS_TO_FILL = [
    "ixagegrp9",
    "ixsex",
    "ixminctcat1",
    "ixminctcat2",
    "sus",
    "ixesarsvarf1",
]

DEFAULT_NET_NUM_COLS = [
    "duration_sec",
    "no_ts",
    "contacts",
    "contacts_infected",
    "hcir",
    "hh_ar",
]

DEFAULT_METRIC_COLS = [
    "duration_sec",
    "no_ts",
    "contacts",
    "contacts_infected",
    "hcir",
    "hh_ar",
]

REQUIRED_META_COLUMNS = [
    "indid",
    "site",
    "agegrp9",
    "sex",
    "hhid",
    "smokecignow1",
    "bmicat",
    "index",
    "sars",
    "sus",
    "ixesarsvarf1",
]

REQUIRED_NET_COLUMNS = [
    "t",
    "date",
    "pair",
    "indid1",
    "indid2",
    "hh",
    "duration_sec",
    "no_ts",
    "contacts",
    "contacts_infected",
    "hcir",
    "hh_ar",
    "pair_sars",
]


def _jsonable(value: Any) -> Any:
    """Convert pandas/numpy/set values into JSON-serializable values."""
    if isinstance(value, set):
        return sorted(str(item) for item in value)
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_jsonable(item) for item in value]
    if hasattr(value, "item"):
        try:
            return value.item()
        except Exception:
            pass
    return value


def ensure_required_columns(
    df: pd.DataFrame,
    required_columns: list[str],
    label: str,
) -> None:
    """Raise a clear error when an ETL input is missing required fields."""
    missing = [column for column in required_columns if column not in df.columns]
    if missing:
        raise ValueError(f"{label} is missing required columns: {missing}")


def preprocess_metadata(
    df_meta: pd.DataFrame,
    columns_to_fill: list[str] | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Fill index-case missing values and fix known age-group CSV artifacts."""
    df_meta_cleaned = df_meta.copy()
    columns_to_fill = columns_to_fill or DEFAULT_COLUMNS_TO_FILL
    existing_fill_cols = [col for col in columns_to_fill if col in df_meta_cleaned.columns]

    f0_records = df_meta_cleaned[df_meta_cleaned["index"] == "Index"].copy()
    df_meta_cleaned[existing_fill_cols] = df_meta_cleaned[existing_fill_cols].fillna(
        "Self Index"
    )
    df_meta_cleaned["agegrp9"] = df_meta_cleaned["agegrp9"].replace(
        {"12-May": "5-12", "60": ">=60"}
    )

    return df_meta_cleaned, f0_records


def validate_inputs(df_meta: pd.DataFrame, df_net: pd.DataFrame) -> dict[str, Any]:
    """Run lightweight consistency and range checks used in the notebook."""
    ensure_required_columns(df_meta, REQUIRED_META_COLUMNS, "metadata")
    ensure_required_columns(df_net, REQUIRED_NET_COLUMNS, "contact network")

    meta_ids = set(df_meta["indid"].unique())
    net_ids = set(df_net["indid1"].unique()).union(set(df_net["indid2"].unique()))

    hcir_out_of_range = df_net[(df_net["hcir"] < 0) | (df_net["hcir"] > 100)]
    hh_ar_out_of_range = df_net[(df_net["hh_ar"] < 0) | (df_net["hh_ar"] > 100)]

    return {
        "metadata_id_count": len(meta_ids),
        "network_id_count": len(net_ids),
        "ids_in_net_not_in_meta": net_ids - meta_ids,
        "ids_in_meta_not_in_net": meta_ids - net_ids,
        "hcir_out_of_range_count": len(hcir_out_of_range),
        "hh_ar_out_of_range_count": len(hh_ar_out_of_range),
        "total_out_of_range_count": len(hcir_out_of_range) + len(hh_ar_out_of_range),
        "metadata_row_count": int(len(df_meta)),
        "network_row_count": int(len(df_net)),
        "metadata_duplicate_indid_count": int(df_meta["indid"].duplicated().sum()),
        "network_duplicate_pair_time_count": int(
            df_net[["pair", "t"]].duplicated().sum()
        ),
        "metadata_null_counts": {
            column: int(df_meta[column].isna().sum())
            for column in REQUIRED_META_COLUMNS
            if column in df_meta.columns
        },
        "network_null_counts": {
            column: int(df_net[column].isna().sum())
            for column in REQUIRED_NET_COLUMNS
            if column in df_net.columns
        },
    }


def cap_outliers_iqr(
    df_net: pd.DataFrame,
    numeric_cols: list[str] | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Cap numeric outliers with IQR bounds, equivalent to winsorization."""
    df_net_cleaned = df_net.copy()
    numeric_cols = numeric_cols or DEFAULT_NET_NUM_COLS
    outlier_summary = []

    for col in numeric_cols:
        q1 = df_net[col].quantile(0.25)
        q3 = df_net[col].quantile(0.75)
        iqr = q3 - q1
        lower_bound = q1 - 1.5 * iqr
        upper_bound = q3 + 1.5 * iqr

        outliers_count = ((df_net[col] < lower_bound) | (df_net[col] > upper_bound)).sum()
        outlier_summary.append(
            {
                "Column": col,
                "Lower Bound": lower_bound,
                "Upper Bound": upper_bound,
                "Outliers Count": int(outliers_count),
            }
        )

        df_net_cleaned[col] = np.clip(df_net_cleaned[col], lower_bound, upper_bound)

    return df_net_cleaned, pd.DataFrame(outlier_summary)


def build_star_schema(
    df_meta_cleaned: pd.DataFrame,
    df_net_cleaned: pd.DataFrame,
) -> dict[str, pd.DataFrame]:
    """Build dimensions and fact table from cleaned metadata/contact data."""
    dim_indid = df_meta_cleaned[
        [
            "indid",
            "site",
            "agegrp9",
            "sex",
            "hhid",
            "smokecignow1",
            "bmicat",
            "index",
            "sars",
            "sus",
            "ixesarsvarf1",
        ]
    ].drop_duplicates()
    dim_indid = dim_indid.reset_index(drop=True)

    dim_household = df_net_cleaned[
        ["hh", "hcir", "hh_ar", "contacts", "contacts_infected"]
    ].drop_duplicates()
    dim_household = dim_household.rename(columns={"hh": "hhid"}).reset_index(drop=True)

    df_net_cleaned = df_net_cleaned.copy()
    df_net_cleaned["date_parsed"] = pd.to_datetime(df_net_cleaned["date"], errors="coerce")
    dim_date = df_net_cleaned[["date", "date_parsed"]].drop_duplicates().reset_index(
        drop=True
    )
    dim_date["date_id"] = dim_date.index + 1
    dim_date["year"] = dim_date["date_parsed"].dt.year
    dim_date["month"] = dim_date["date_parsed"].dt.month
    dim_date["day"] = dim_date["date_parsed"].dt.day
    dim_date = dim_date.drop(columns=["date_parsed"])

    dim_pair = df_net_cleaned[["pair", "indid1", "indid2", "pair_sars"]].drop_duplicates()
    dim_pair = dim_pair.reset_index(drop=True)

    fact_contacts = df_net_cleaned.merge(dim_date[["date", "date_id"]], on="date", how="left")
    fact_contacts = fact_contacts[
        ["t", "date_id", "pair", "indid1", "indid2", "hh", "duration_sec", "no_ts"]
    ]
    fact_contacts = fact_contacts.rename(columns={"hh": "hhid"})

    return {
        "dim_indid": dim_indid,
        "dim_household": dim_household,
        "dim_date": dim_date,
        "dim_pair": dim_pair,
        "fact_contacts": fact_contacts,
    }


def merge_star_schema(schema: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """Merge fact and dimensions into the wide table used before encoding."""
    dim_indid = schema["dim_indid"]
    dim_household = schema["dim_household"]
    dim_date = schema["dim_date"]
    dim_pair = schema["dim_pair"]
    fact_contacts = schema["fact_contacts"]

    df_all = fact_contacts.copy()
    df_all = df_all.merge(dim_pair[["pair", "pair_sars"]], on="pair", how="left")
    df_all = df_all.merge(
        dim_household[["hhid", "hcir", "hh_ar", "contacts", "contacts_infected"]],
        on="hhid",
        how="left",
    )

    dim_ind_clean = dim_indid.drop(columns=["hhid"])
    dim_ind1 = dim_ind_clean.add_prefix("ind1_").rename(columns={"ind1_indid": "indid1"})
    df_all = df_all.merge(dim_ind1, on="indid1", how="left")

    dim_ind2 = dim_ind_clean.add_prefix("ind2_").rename(columns={"ind2_indid": "indid2"})
    df_all = df_all.merge(dim_ind2, on="indid2", how="left")

    df_all = df_all.merge(dim_date[["date_id", "year", "month", "day"]], on="date_id", how="left")

    return df_all


def transform_to_olap(
    df_all: pd.DataFrame,
    metric_cols: list[str] | None = None,
) -> tuple[pd.DataFrame, dict[str, dict[Any, int]], dict[str, int], list[str]]:
    """Encode categorical dimensions and order dimensions by cardinality."""
    df_cube = df_all.copy()
    metric_cols = metric_cols or DEFAULT_METRIC_COLS

    columns_to_drop = ["t", "date_id", "pair", "indid1", "indid2", "hhid"]
    df_cube = df_cube.drop(columns=[col for col in columns_to_drop if col in df_cube.columns])

    if "year" in df_cube.columns and "month" in df_cube.columns:
        df_cube["month_id"] = df_cube["year"] * 100 + df_cube["month"]
        df_cube = df_cube.drop(
            columns=[col for col in ["year", "month", "day"] if col in df_cube.columns]
        )

    mapping_dict: dict[str, dict[Any, int]] = {}
    categorical_cols = df_cube.select_dtypes(include=["object"]).columns

    for col in categorical_cols:
        df_cube[col] = df_cube[col].astype("category")
        mapping_dict[col] = {
            category: int(code) for code, category in enumerate(df_cube[col].cat.categories)
        }
        df_cube[col] = df_cube[col].cat.codes

    dim_cols = [col for col in df_cube.columns if col not in metric_cols]
    cardinalities = {col: int(df_cube[col].nunique()) for col in dim_cols}
    sorted_dim_cols = sorted(cardinalities, key=cardinalities.get)
    final_columns_order = sorted_dim_cols + [col for col in metric_cols if col in df_cube.columns]

    return df_cube[final_columns_order], mapping_dict, cardinalities, sorted_dim_cols


def save_outputs(
    df_result: pd.DataFrame,
    mapping_dict: dict[str, dict[Any, int]],
    output_dir: str | Path,
    validation_report: dict[str, Any] | None = None,
    reports_dir: str | Path | None = None,
) -> dict[str, Path]:
    """Save the encoded dataset and mapping dictionary."""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    json_path = output_dir / "mapping_dict.json"
    csv_path = output_dir / "sashts_final_dataset.csv"

    with json_path.open("w", encoding="utf-8") as f:
        json.dump(mapping_dict, f, ensure_ascii=False, indent=4)

    df_result.to_csv(csv_path, index=False)

    paths = {"mapping_json": json_path, "final_csv": csv_path}

    if validation_report is not None and reports_dir is not None:
        reports_dir = Path(reports_dir)
        reports_dir.mkdir(parents=True, exist_ok=True)
        validation_path = reports_dir / "etl_validation.json"
        with validation_path.open("w", encoding="utf-8") as f:
            json.dump(_jsonable(validation_report), f, ensure_ascii=False, indent=4)
        paths["validation_json"] = validation_path

    return paths


def run_etl(
    df_meta: pd.DataFrame,
    df_net: pd.DataFrame,
    output_dir: str | Path | None = None,
    reports_dir: str | Path | None = None,
    save_artifacts: bool = True,
) -> dict[str, Any]:
    """Run the full ETL pipeline and return notebook-friendly outputs."""
    ensure_required_columns(df_meta, REQUIRED_META_COLUMNS, "metadata")
    ensure_required_columns(df_net, REQUIRED_NET_COLUMNS, "contact network")

    df_meta_cleaned, f0_records = preprocess_metadata(df_meta)
    validation_report = validate_inputs(df_meta_cleaned, df_net)
    df_net_cleaned, outlier_summary = cap_outliers_iqr(df_net)
    schema = build_star_schema(df_meta_cleaned, df_net_cleaned)
    df_all = merge_star_schema(schema)
    df_result, mapping_dict, cardinalities, sorted_dim_cols = transform_to_olap(df_all)

    saved_paths: dict[str, Path] = {}
    if save_artifacts and output_dir is not None:
        saved_paths = save_outputs(
            df_result,
            mapping_dict,
            output_dir,
            validation_report=validation_report,
            reports_dir=reports_dir,
        )

    return {
        "df_meta_cleaned": df_meta_cleaned,
        "df_net_cleaned": df_net_cleaned,
        "f0_records": f0_records,
        "validation_report": validation_report,
        "outlier_summary": outlier_summary,
        "df_all": df_all,
        "df_result": df_result,
        "mapping_dict": mapping_dict,
        "cardinalities": cardinalities,
        "sorted_dim_cols": sorted_dim_cols,
        "saved_paths": saved_paths,
        **schema,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run SASHTS Pandas ETL.")
    parser.add_argument("--metadata-path", default="data/raw/sashts_metadata.csv")
    parser.add_argument("--network-path", default="data/raw/sashts_contact_network.csv")
    parser.add_argument("--output-dir", default="data/processed")
    parser.add_argument("--reports-dir", default="reports")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    metadata_path = Path(args.metadata_path)
    network_path = Path(args.network_path)

    df_meta = pd.read_csv(metadata_path)
    df_net = pd.read_csv(network_path)
    outputs = run_etl(
        df_meta,
        df_net,
        output_dir=args.output_dir,
        reports_dir=args.reports_dir,
        save_artifacts=True,
    )

    print("ETL completed")
    for name, path in outputs["saved_paths"].items():
        print(f"{name}: {path}")
    print(f"processed_rows: {len(outputs['df_result'])}")
    print(f"dimensions: {', '.join(outputs['sorted_dim_cols'])}")


if __name__ == "__main__":
    main()
