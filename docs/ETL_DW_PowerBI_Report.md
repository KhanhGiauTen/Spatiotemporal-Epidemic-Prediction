# ETL, Data Warehouse, and Power BI Pipeline Report

## 1. Architecture

Pipeline cua du an duoc chuan hoa thanh luong:

```text
Raw SASHTS CSV
-> Pandas ETL
-> Processed OLAP CSV + mapping dictionary
-> DuckDB/PostgreSQL Data Warehouse
-> StarTree + Star-Cubing
-> Fact_Iceberg_Cuboid
-> Power BI / FastAPI / Reports
```

DuckDB la Data Warehouse local mac dinh de demo nhanh khong can server.
PostgreSQL duoc ho tro thong qua cung interface SQLAlchemy.

## 2. ETL Flow

Input:

- `data/raw/sashts_metadata.csv`
- `data/raw/sashts_contact_network.csv`

Command:

```powershell
python scripts/etl.py --metadata-path data/raw/sashts_metadata.csv --network-path data/raw/sashts_contact_network.csv --output-dir data/processed --reports-dir reports
```

Output:

- `data/processed/sashts_final_dataset.csv`
- `data/processed/mapping_dict.json`
- `reports/etl_validation.json`

Transform chinh:

- Fill missing values cho index-case fields bang `Self Index`.
- Sua artifact nhom tuoi `12-May` thanh `5-12`.
- Validate required columns, row counts, duplicate IDs, null counts.
- Cap numeric outliers bang IQR.
- Build star-schema-like intermediate tables trong memory.
- Merge thanh wide OLAP table.
- Encode categorical dimensions thanh integer va luu mapping dictionary.

## 3. Data Warehouse

Command demo DuckDB:

```powershell
python scripts/run_pipeline.py --dw duckdb --duckdb-path warehouse/epidemic.duckdb --refresh
```

Command PostgreSQL tuy chon:

```powershell
python scripts/run_pipeline.py --dw postgresql --database-url "postgresql+psycopg2://user:password@localhost:5432/epidemic_dw" --refresh
```

Tables:

- `stg_metadata`
- `stg_contact_network`
- `stg_processed_olap`
- `Dim_Time`
- `Dim_Location`
- `Dim_Patient`
- `Fact_Exposure`
- `Fact_Iceberg_Cuboid`

`Fact_Exposure` la event-level fact. Moi dong dai dien cho mot exposure/contact
event giua `indid1` va `indid2` tai mot thoi diem va dia diem.

`Fact_Iceberg_Cuboid` luu Iceberg Cube heavy-hitters rieng, gom `run_id`,
`dimension_values_json`, `support_count`, `min_sup`, `month_id`, `ind1_site`,
`ind2_site`, va `pair_sars`.

## 4. Demo Queries

Mo DuckDB va chay:

```sql
SELECT COUNT(*) FROM "Fact_Exposure";
SELECT COUNT(*) FROM "Fact_Iceberg_Cuboid";
SELECT * FROM v_exposure_by_location_time LIMIT 10;
SELECT * FROM v_powerbi_overview_kpis;
```

Ket qua ky vong voi du lieu hien tai:

- `Fact_Exposure`: co hon 140k dong event.
- `Fact_Iceberg_Cuboid`: co cuboid heavy-hitter khi `min_sup` hop le.
- View tong hop tra du lieu theo thoi gian va dia diem.

## 5. Power BI

Power BI co hai che do:

- DB mode: ket noi DuckDB bang ODBC hoac PostgreSQL connector.
- CSV mode: import `powerbi/data/*.csv`.

Chuan bi CSV fallback tu DB:

```powershell
python scripts/prepare_powerbi_data.py --project-root . --source duckdb --duckdb-path warehouse/epidemic.duckdb --export-csv
```

Mo `powerbi/EpidemicDashboard.pbix`, bam Refresh, sau do trinh bay 5 page:

- Executive Overview
- Iceberg Cube Analytics
- Ground Zero Clustering
- Outbreak Classification
- Contact Network Analysis

## 6. Test and Acceptance

Chay:

```powershell
python -m pytest -q
```

Acceptance criteria:

- ETL script chay duoc khong can notebook.
- DuckDB warehouse duoc tao tai `warehouse/epidemic.duckdb`.
- Staging, dimension, fact, cube tables ton tai.
- `Fact_Exposure` va `Fact_Iceberg_Cuboid` co du lieu.
- `powerbi/data/*.csv` duoc tao/refreshed.
- Power BI co the refresh bang DB mode hoac CSV mode.
