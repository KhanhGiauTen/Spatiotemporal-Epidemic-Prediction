# Power BI Connection Guide

Power BI co hai cach dung du lieu cua pipeline:

1. Ket noi truc tiep Data Warehouse DuckDB/PostgreSQL.
2. Import CSV fallback trong `powerbi/data/`.

## 1. Chuan Bi Du Lieu

Chay full pipeline tu thu muc goc repo:

```powershell
python scripts/run_pipeline.py --dw duckdb --duckdb-path warehouse/epidemic.duckdb --refresh
```

Lenh nay tao:

- DuckDB warehouse: `warehouse/epidemic.duckdb`
- Staging tables: `stg_metadata`, `stg_contact_network`, `stg_processed_olap`
- DW tables: `Dim_Time`, `Dim_Location`, `Dim_Patient`, `Fact_Exposure`
- Cube table: `Fact_Iceberg_Cuboid`
- Power BI CSV fallback: `powerbi/data/*.csv`

## 2. DB Mode: DuckDB

Power BI Desktop khong doc file DuckDB truc tiep neu chua co driver. Cai DuckDB
ODBC driver, tao DSN tro toi:

```text
warehouse/epidemic.duckdb
```

Trong Power BI:

```text
Get Data -> ODBC -> DuckDB DSN -> Load
```

Bang/view nen load:

- `v_powerbi_overview_kpis`
- `v_powerbi_exposure_summary`
- `v_exposure_by_location_time`
- `Fact_Iceberg_Cuboid`
- `Dim_Time`
- `Dim_Location`
- `Dim_Patient`
- `Fact_Exposure`

## 3. DB Mode: PostgreSQL

Neu dung PostgreSQL:

```powershell
python scripts/run_pipeline.py --dw postgresql --database-url "postgresql+psycopg2://user:password@localhost:5432/epidemic_dw" --refresh
```

Trong Power BI:

```text
Get Data -> PostgreSQL database -> server/database -> Load
```

## 4. CSV Fallback Mode

Neu may demo khong co DB driver, import CSV:

```powershell
python scripts/prepare_powerbi_data.py --project-root . --source duckdb --duckdb-path warehouse/epidemic.duckdb --export-csv
```

Sau do trong Power BI:

```text
Get Data -> Text/CSV -> powerbi/data/*.csv
```

## 5. Dashboard Pages

Dashboard `powerbi/EpidemicDashboard.pbix` duoc thiet ke theo 5 page:

- Executive Overview
- Iceberg Cube Analytics
- Ground Zero Clustering
- Outbreak Classification
- Contact Network Analysis

Neu dung DB mode, co the thay source cua cac table CSV bang cac table/view trong
warehouse. Neu dung CSV mode, bam Refresh sau khi chay lai pipeline.
