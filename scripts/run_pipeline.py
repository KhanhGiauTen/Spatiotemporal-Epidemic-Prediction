"""Run the end-to-end ETL -> DW -> Iceberg Cube -> Power BI pipeline.

Default demo command:
    python scripts/run_pipeline.py --dw duckdb --duckdb-path warehouse/epidemic.duckdb --refresh
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import Engine


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.etl import run_etl  # noqa: E402
from scripts.prepare_powerbi_data import prepare_powerbi_data  # noqa: E402
from src.algorithm.starcubing import starcubing  # noqa: E402
from src.star_tree import StarTree  # noqa: E402


DEFAULT_DUCKDB_PATH = "warehouse/epidemic.duckdb"
DEFAULT_METADATA_PATH = "data/raw/sashts_metadata.csv"
DEFAULT_NETWORK_PATH = "data/raw/sashts_contact_network.csv"
DEFAULT_PROCESSED_DIR = "data/processed"
DEFAULT_REPORTS_DIR = "reports"
DEFAULT_MIN_SUP = 50
DEFAULT_CUBE_DIMENSIONS = ["month_id", "ind1_site", "ind2_site", "pair_sars"]


def build_connection_string(args: argparse.Namespace, project_root: Path | None = None) -> str:
    if args.dw == "duckdb":
        duckdb_path = Path(args.duckdb_path)
        if project_root is not None and not duckdb_path.is_absolute():
            duckdb_path = project_root / duckdb_path
        duckdb_path.parent.mkdir(parents=True, exist_ok=True)
        return f"duckdb:///{duckdb_path.as_posix()}"
    if not args.database_url:
        raise ValueError("--database-url is required when --dw postgresql")
    return args.database_url


def to_sql_replace(df: pd.DataFrame, table_name: str, engine: Engine) -> None:
    df.to_sql(table_name, engine, if_exists="replace", index=False, chunksize=10_000)


def execute_statements(engine: Engine, statements: list[str]) -> None:
    with engine.begin() as conn:
        for statement in statements:
            conn.execute(text(statement))


def drop_pipeline_objects(engine: Engine) -> None:
    statements = [
        'DROP VIEW IF EXISTS v_exposure_by_location_time',
        'DROP VIEW IF EXISTS v_powerbi_overview_kpis',
        'DROP VIEW IF EXISTS v_powerbi_exposure_summary',
        'DROP TABLE IF EXISTS "Fact_Iceberg_Cuboid"',
        'DROP TABLE IF EXISTS "Fact_Exposure"',
        'DROP TABLE IF EXISTS "Dim_Patient"',
        'DROP TABLE IF EXISTS "Dim_Location"',
        'DROP TABLE IF EXISTS "Dim_Time"',
        'DROP TABLE IF EXISTS stg_processed_olap',
        'DROP TABLE IF EXISTS stg_contact_network',
        'DROP TABLE IF EXISTS stg_metadata',
    ]
    execute_statements(engine, statements)


def create_warehouse_tables(engine: Engine) -> None:
    statements = [
        """
        CREATE TABLE IF NOT EXISTS "Dim_Time" (
            time_id INTEGER PRIMARY KEY,
            date_full DATE NOT NULL,
            year INTEGER NOT NULL,
            month INTEGER NOT NULL,
            day INTEGER NOT NULL,
            week_of_year INTEGER NOT NULL,
            quarter INTEGER NOT NULL,
            day_of_week VARCHAR NOT NULL,
            is_weekend BOOLEAN NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS "Dim_Location" (
            location_id INTEGER PRIMARY KEY,
            site_code VARCHAR NOT NULL,
            site_name VARCHAR NOT NULL,
            region VARCHAR,
            country VARCHAR DEFAULT 'South Africa',
            latitude DECIMAL(10, 8),
            longitude DECIMAL(11, 8),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS "Dim_Patient" (
            patient_id INTEGER PRIMARY KEY,
            patient_code VARCHAR NOT NULL,
            age_group VARCHAR NOT NULL,
            sex VARCHAR NOT NULL,
            bmi_category VARCHAR,
            smoking_status VARCHAR,
            household_id VARCHAR,
            role_in_network VARCHAR DEFAULT 'Contact',
            sars_status VARCHAR DEFAULT 'Unknown',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS "Fact_Exposure" (
            exposure_id BIGINT PRIMARY KEY,
            time_id INTEGER NOT NULL,
            location_id INTEGER NOT NULL,
            patient_id INTEGER NOT NULL,
            contact_patient_id INTEGER,
            count_exposure INTEGER NOT NULL DEFAULT 1,
            exposure_strength DECIMAL(10, 4),
            sars_status_patient VARCHAR,
            susceptibility_status VARCHAR,
            variant_type VARCHAR,
            contact_duration_category VARCHAR,
            is_threshold_exceeded BOOLEAN DEFAULT TRUE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS "Fact_Iceberg_Cuboid" (
            cuboid_id BIGINT PRIMARY KEY,
            run_id VARCHAR NOT NULL,
            dimension_values_json VARCHAR NOT NULL,
            support_count INTEGER NOT NULL,
            min_sup INTEGER NOT NULL,
            month_id INTEGER,
            ind1_site VARCHAR,
            ind2_site VARCHAR,
            pair_sars VARCHAR,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """,
    ]
    execute_statements(engine, statements)


def create_views(engine: Engine) -> None:
    statements = [
        """
        CREATE OR REPLACE VIEW v_exposure_by_location_time AS
        SELECT
            dt.year,
            dt.month,
            dt.date_full,
            dl.site_name,
            dl.region,
            COUNT(fe.exposure_id) AS total_exposures,
            SUM(fe.count_exposure) AS total_exposure_count,
            COUNT(DISTINCT fe.patient_id) AS unique_patients,
            COUNT(DISTINCT fe.contact_patient_id) AS unique_contacts,
            AVG(fe.exposure_strength) AS avg_exposure_strength
        FROM "Fact_Exposure" fe
        JOIN "Dim_Time" dt ON fe.time_id = dt.time_id
        JOIN "Dim_Location" dl ON fe.location_id = dl.location_id
        WHERE fe.is_threshold_exceeded = TRUE
        GROUP BY dt.year, dt.month, dt.date_full, dl.site_name, dl.region
        """,
        """
        CREATE OR REPLACE VIEW v_powerbi_overview_kpis AS
        SELECT
            COUNT(*) AS total_exposure_events,
            SUM(count_exposure) AS total_exposure_count,
            COUNT(DISTINCT patient_id) AS unique_patients,
            COUNT(DISTINCT contact_patient_id) AS unique_contacts,
            AVG(exposure_strength) AS avg_exposure_strength
        FROM "Fact_Exposure"
        """,
        """
        CREATE OR REPLACE VIEW v_powerbi_exposure_summary AS
        SELECT
            dt.year,
            dt.month,
            dl.site_name,
            COUNT(fe.exposure_id) AS record_count,
            SUM(fe.count_exposure) AS total_contacts,
            AVG(fe.exposure_strength) AS avg_duration_sec
        FROM "Fact_Exposure" fe
        JOIN "Dim_Time" dt ON fe.time_id = dt.time_id
        JOIN "Dim_Location" dl ON fe.location_id = dl.location_id
        GROUP BY dt.year, dt.month, dl.site_name
        """,
    ]
    execute_statements(engine, statements)


def parse_date_series(series: pd.Series) -> pd.Series:
    parsed = pd.to_datetime(series, errors="coerce")
    if parsed.isna().any():
        missing = int(parsed.isna().sum())
        raise ValueError(f"Unable to parse {missing} contact-network date values")
    return parsed.dt.date


def build_time_dimension(df_net: pd.DataFrame) -> pd.DataFrame:
    dates = parse_date_series(df_net["date"])
    unique_dates = pd.Series(sorted(dates.unique()), name="date_full")
    dim = pd.DataFrame({"date_full": unique_dates})
    date_ts = pd.to_datetime(dim["date_full"])
    dim["time_id"] = date_ts.dt.strftime("%Y%m%d").astype(int)
    dim["year"] = date_ts.dt.year
    dim["month"] = date_ts.dt.month
    dim["day"] = date_ts.dt.day
    dim["week_of_year"] = date_ts.dt.isocalendar().week.astype(int)
    dim["quarter"] = date_ts.dt.quarter
    dim["day_of_week"] = date_ts.dt.day_name()
    dim["is_weekend"] = date_ts.dt.weekday >= 5
    return dim[
        [
            "time_id",
            "date_full",
            "year",
            "month",
            "day",
            "week_of_year",
            "quarter",
            "day_of_week",
            "is_weekend",
        ]
    ]


def build_location_dimension(df_meta: pd.DataFrame) -> pd.DataFrame:
    sites = sorted(str(site) for site in df_meta["site"].dropna().unique())
    records = []
    for idx, site in enumerate(sites, start=1):
        records.append(
            {
                "location_id": idx,
                "site_code": site.upper().replace(" ", "_"),
                "site_name": site,
                "region": site,
                "country": "South Africa",
            }
        )
    return pd.DataFrame(records)


def build_patient_dimension(df_meta: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for idx, (_, payload) in enumerate(df_meta.sort_values("indid").iterrows(), start=1):
        rows.append(
            {
                "patient_id": idx,
                "patient_code": payload.get("indid"),
                "age_group": payload.get("agegrp9", "Unknown"),
                "sex": payload.get("sex", "Unknown"),
                "bmi_category": payload.get("bmicat"),
                "smoking_status": payload.get("smokecignow1"),
                "household_id": payload.get("hhid"),
                "role_in_network": payload.get("index", "Contact"),
                "sars_status": payload.get("sars", "Unknown"),
            }
        )
    return pd.DataFrame(rows)


def duration_category(duration: Any) -> str:
    try:
        seconds = float(duration)
    except (TypeError, ValueError):
        return "Unknown"
    if seconds < 60:
        return "Short"
    if seconds < 300:
        return "Medium"
    return "Long"


def build_exposure_facts(
    df_net: pd.DataFrame,
    df_meta: pd.DataFrame,
    dim_time: pd.DataFrame,
    dim_location: pd.DataFrame,
    dim_patient: pd.DataFrame,
    threshold: int,
) -> pd.DataFrame:
    meta_by_id = df_meta.set_index("indid").to_dict("index")
    patient_id_by_code = dict(zip(dim_patient["patient_code"], dim_patient["patient_id"]))
    location_id_by_site = dict(zip(dim_location["site_name"], dim_location["location_id"]))
    time_id_by_date = dict(zip(dim_time["date_full"].astype(str), dim_time["time_id"]))
    parsed_dates = parse_date_series(df_net["date"]).astype(str)

    records = []
    for exposure_id, (row_index, row) in enumerate(df_net.iterrows(), start=1):
        patient_code = row.get("indid1")
        contact_code = row.get("indid2")
        patient_meta = meta_by_id.get(patient_code, {})
        site = patient_meta.get("site")
        patient_id = patient_id_by_code.get(patient_code)
        if patient_id is None or site not in location_id_by_site:
            continue

        count_exposure = int(row.get("no_ts", 1) or 1)
        records.append(
            {
                "exposure_id": exposure_id,
                "time_id": int(time_id_by_date[parsed_dates.loc[row_index]]),
                "location_id": int(location_id_by_site[site]),
                "patient_id": int(patient_id),
                "contact_patient_id": (
                    int(patient_id_by_code[contact_code])
                    if contact_code in patient_id_by_code
                    else None
                ),
                "count_exposure": count_exposure,
                "exposure_strength": float(row.get("duration_sec", 0) or 0),
                "sars_status_patient": patient_meta.get("sars"),
                "susceptibility_status": patient_meta.get("sus"),
                "variant_type": patient_meta.get("ixesarsvarf1"),
                "contact_duration_category": duration_category(row.get("duration_sec")),
                "is_threshold_exceeded": count_exposure >= threshold,
            }
        )
    return pd.DataFrame(records)


def insert_dataframe(engine: Engine, table_name: str, df: pd.DataFrame) -> None:
    if df.empty:
        return
    df.to_sql(table_name, engine, if_exists="append", index=False, chunksize=10_000)


def load_warehouse(
    engine: Engine,
    etl_outputs: dict[str, Any],
    threshold: int,
) -> dict[str, int]:
    df_meta = etl_outputs["df_meta_cleaned"]
    df_net = etl_outputs["df_net_cleaned"]
    dim_time = build_time_dimension(df_net)
    dim_location = build_location_dimension(df_meta)
    dim_patient = build_patient_dimension(df_meta)
    fact_exposure = build_exposure_facts(
        df_net,
        df_meta,
        dim_time,
        dim_location,
        dim_patient,
        threshold=threshold,
    )

    to_sql_replace(df_meta, "stg_metadata", engine)
    to_sql_replace(df_net, "stg_contact_network", engine)
    to_sql_replace(etl_outputs["df_result"], "stg_processed_olap", engine)

    insert_dataframe(engine, "Dim_Time", dim_time)
    insert_dataframe(engine, "Dim_Location", dim_location)
    insert_dataframe(engine, "Dim_Patient", dim_patient)
    insert_dataframe(engine, "Fact_Exposure", fact_exposure)

    return {
        "time_records": len(dim_time),
        "location_records": len(dim_location),
        "patient_records": len(dim_patient),
        "exposure_records": len(fact_exposure),
    }


def decode_value(column: str, value: Any, mapping_dict: dict[str, dict[Any, int]]) -> Any:
    if str(value) == "*":
        return "*"
    if column not in mapping_dict:
        return value
    inverse = {int(code): label for label, code in mapping_dict[column].items()}
    try:
        return inverse.get(int(value), value)
    except (TypeError, ValueError):
        return value


def build_iceberg_records(
    df_result: pd.DataFrame,
    mapping_dict: dict[str, dict[Any, int]],
    dimensions: list[str],
    min_sup: int,
    run_id: str,
) -> list[dict[str, Any]]:
    transactions = [
        tuple(row)
        for row in df_result[dimensions].astype(str).itertuples(index=False, name=None)
    ]
    tree = StarTree(dimensions, min_support=min_sup)
    tree.build_from_transactions(transactions)
    cuboids = starcubing(tree, min_sup=min_sup)

    records = []
    for cuboid_id, (cuboid, support) in enumerate(cuboids, start=1):
        decoded = {
            column: decode_value(column, value, mapping_dict)
            for column, value in zip(dimensions, cuboid)
        }
        records.append(
            {
                "cuboid_id": cuboid_id,
                "run_id": run_id,
                "dimension_values_json": json.dumps(decoded, ensure_ascii=False),
                "support_count": int(support),
                "min_sup": int(min_sup),
                "month_id": (
                    int(decoded["month_id"])
                    if "month_id" in decoded and str(decoded["month_id"]) != "*"
                    else None
                ),
                "ind1_site": decoded.get("ind1_site"),
                "ind2_site": decoded.get("ind2_site"),
                "pair_sars": decoded.get("pair_sars"),
            }
        )
    return records


def load_iceberg_cuboids(
    engine: Engine,
    etl_outputs: dict[str, Any],
    dimensions: list[str],
    min_sup: int,
    run_id: str,
) -> int:
    df_result = etl_outputs["df_result"]
    available_dimensions = [dimension for dimension in dimensions if dimension in df_result.columns]
    if len(available_dimensions) < 2:
        raise ValueError(f"Not enough cube dimensions are available: {available_dimensions}")
    records = build_iceberg_records(
        df_result,
        etl_outputs["mapping_dict"],
        available_dimensions,
        min_sup=min_sup,
        run_id=run_id,
    )
    insert_dataframe(engine, "Fact_Iceberg_Cuboid", pd.DataFrame(records))
    return len(records)


def run_pipeline(args: argparse.Namespace) -> dict[str, Any]:
    project_root = Path(args.project_root).resolve()
    metadata_path = project_root / args.metadata_path
    network_path = project_root / args.network_path
    processed_dir = project_root / args.processed_dir
    reports_dir = project_root / args.reports_dir

    df_meta = pd.read_csv(metadata_path)
    df_net = pd.read_csv(network_path)
    etl_outputs = run_etl(
        df_meta,
        df_net,
        output_dir=processed_dir,
        reports_dir=reports_dir,
        save_artifacts=True,
    )

    connection_string = build_connection_string(args, project_root=project_root)
    engine = create_engine(connection_string)
    if args.refresh:
        drop_pipeline_objects(engine)
    create_warehouse_tables(engine)
    load_summary = load_warehouse(engine, etl_outputs, threshold=args.threshold)
    run_id = args.run_id or datetime.now().strftime("%Y%m%d%H%M%S")
    cuboid_count = load_iceberg_cuboids(
        engine,
        etl_outputs,
        dimensions=args.cube_dimensions,
        min_sup=args.min_sup,
        run_id=run_id,
    )
    create_views(engine)

    prepare_powerbi_data(
        project_root=project_root,
        source=args.dw,
        duckdb_path=Path(args.duckdb_path),
        database_url=args.database_url,
        export_csv=True,
    )

    tables = inspect(engine).get_table_names()
    engine.dispose()
    summary = {
        "connection_string": connection_string,
        "run_id": run_id,
        "warehouse_tables": sorted(tables),
        "load_summary": load_summary,
        "iceberg_cuboids": cuboid_count,
        "processed_rows": len(etl_outputs["df_result"]),
    }
    print(json.dumps(summary, indent=2, ensure_ascii=False, default=str))
    return summary


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the complete epidemic ETL/DW pipeline.")
    parser.add_argument("--project-root", default=".")
    parser.add_argument("--metadata-path", default=DEFAULT_METADATA_PATH)
    parser.add_argument("--network-path", default=DEFAULT_NETWORK_PATH)
    parser.add_argument("--processed-dir", default=DEFAULT_PROCESSED_DIR)
    parser.add_argument("--reports-dir", default=DEFAULT_REPORTS_DIR)
    parser.add_argument("--dw", choices=["duckdb", "postgresql"], default="duckdb")
    parser.add_argument("--duckdb-path", default=DEFAULT_DUCKDB_PATH)
    parser.add_argument("--database-url", default=None)
    parser.add_argument("--refresh", action="store_true")
    parser.add_argument("--threshold", type=int, default=1)
    parser.add_argument("--min-sup", type=int, default=DEFAULT_MIN_SUP)
    parser.add_argument("--run-id", default=None)
    parser.add_argument("--cube-dimensions", nargs="+", default=DEFAULT_CUBE_DIMENSIONS)
    return parser.parse_args()


def main() -> None:
    run_pipeline(parse_args())


if __name__ == "__main__":
    main()
