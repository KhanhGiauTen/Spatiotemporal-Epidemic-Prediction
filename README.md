# Star-Cubing Based Spatiotemporal Epidemic Analysis System

Kho lưu trữ đồ án cuối kỳ môn **Data Mining** về phân tích dịch tễ học
không gian - thời gian dựa trên dữ liệu mạng lưới tiếp xúc SASHTS. Dự án
xây dựng một pipeline đầy đủ từ dữ liệu thô đến Data Warehouse, Iceberg Cube,
khai phá dữ liệu, Power BI dashboard và Web Application demo.

**Web demo cho nhà tuyển dụng:** [Epidemic Analytics](https://epidemic-khanh-demo.vercel.app). Bản công khai dùng snapshot tổng hợp, bản đồ minh họa và sandbox chấm điểm đơn giản; không phải dự báo dịch thực tế hay tư vấn y tế. [Phạm vi và triển khai](docs/public-demo.md).

Tên đề tài:

```text
Star-Cubing Based Spatiotemporal Epidemic Analysis System
```

## Mục Lục

- [1. Tổng Quan](#1-tổng-quan)
- [2. Kiến Trúc Pipeline](#2-kiến-trúc-pipeline)
- [3. Bộ Dữ Liệu](#3-bộ-dữ-liệu)
- [4. Thành Phần Chính](#4-thành-phần-chính)
- [5. Cấu Trúc Thư Mục](#5-cấu-trúc-thư-mục)
- [6. Cài Đặt Môi Trường](#6-cài-đặt-môi-trường)
- [7. Chạy Toàn Bộ Pipeline](#7-chạy-toàn-bộ-pipeline)
- [8. Kiểm Tra Data Warehouse](#8-kiểm-tra-data-warehouse)
- [9. Power BI Dashboard](#9-power-bi-dashboard)
- [10. Web Application và API](#10-web-application-và-api)
- [11. Chạy Các Tác Vụ Data Mining Riêng](#11-chạy-các-tác-vụ-data-mining-riêng)
- [12. Testing](#12-testing)
- [13. Demo Flow Gợi Ý](#13-demo-flow-gợi-ý)
- [14. Troubleshooting](#14-troubleshooting)

## 1. Tổng Quan

Dự án tập trung vào bài toán phân tích nguy cơ dịch bệnh từ dữ liệu tiếp xúc
không gian - thời gian. Hệ thống sử dụng:

- **Pandas ETL** để làm sạch, kiểm tra và mã hóa dữ liệu.
- **DuckDB/PostgreSQL + SQLAlchemy** để xây dựng Data Warehouse.
- **StarTree** để nén transaction bằng cây tiền tố.
- **Star-Cubing** để trích xuất Iceberg Cube/heavy-hitters.
- **K-Means, DBSCAN, Random Forest và Network Analysis** cho các tác vụ khai phá.
- **Power BI** để trực quan hóa dashboard báo cáo.
- **FastAPI + Next.js + Leaflet** để triển khai web demo.

## 2. Kiến Trúc Pipeline

```mermaid
flowchart LR
    A["Raw SASHTS CSV<br/>metadata + contact network"]
    B["Extract<br/>Pandas read_csv"]
    C["Transform<br/>Clean + Validate<br/>Outlier Capping<br/>OLAP Encoding"]
    D["Processed Artifacts<br/>sashts_final_dataset.csv<br/>mapping_dict.json<br/>etl_validation.json"]
    E["SQLAlchemy Loader<br/>scripts/run_pipeline.py"]
    F[("DuckDB Data Warehouse<br/>warehouse/epidemic.duckdb<br/>PostgreSQL optional")]
    G["StarTree + Star-Cubing<br/>min_sup heavy-hitters"]
    H["Fact_Iceberg_Cuboid"]
    I["Power BI Prep<br/>scripts/prepare_powerbi_data.py"]
    J["powerbi/data/*.csv"]
    K["Power BI Dashboard<br/>EpidemicDashboard.pbix"]
    L["Optional Analytics Scripts<br/>Clustering<br/>Classification<br/>Contact Network"]
    M["reports/* outputs"]
    N["FastAPI + Web Map Demo<br/>reads CSV outputs"]

    A --> B --> C --> D
    D --> E --> F
    D --> G --> H --> F
    F --> I --> J --> K
    D --> L --> M --> I
    J --> N
```

Lệnh chính để chạy pipeline end-to-end:

```powershell
python scripts/run_pipeline.py --dw duckdb --duckdb-path warehouse/epidemic.duckdb --refresh
```

## 3. Bộ Dữ Liệu

Dự án dùng bộ dữ liệu **SA-S-HTS** về lây truyền SARS-CoV-2 trong hộ gia đình
tại Nam Phi. Dữ liệu gồm hai file chính:

| File | Số dòng | Ý nghĩa |
|---|---:|---|
| `data/raw/sashts_metadata.csv` | 340 | Thông tin nhân khẩu học, hộ gia đình, trạng thái SARS-CoV-2 của cá nhân |
| `data/raw/sashts_contact_network.csv` | 140,542 | Sự kiện tiếp xúc giữa các cá nhân theo thời gian |

Các nhóm feature chính:

- **Spatial features**: `site`, `ind1_site`, `ind2_site`.
- **Temporal features**: `date`, `year`, `month`, `day`, `month_id`.
- **Patient features**: `agegrp9`, `sex`, `bmicat`, `smokecignow1`, `index`, `sars`.
- **Exposure measures**: `duration_sec`, `no_ts`, `contacts`, `contacts_infected`.
- **Household risk measures**: `hcir`, `hh_ar`.

## 4. Thành Phần Chính

### 4.1 ETL và Tiền Xử Lý

ETL được triển khai trong [scripts/etl.py](scripts/etl.py).

Các bước chính:

1. Kiểm tra schema đầu vào bằng danh sách cột bắt buộc.
2. Xử lý missing values cho các trường index-case bằng nhãn `Self Index`.
3. Sửa lỗi định dạng nhóm tuổi như `12-May` thành `5-12`.
4. Kiểm tra null, duplicate, out-of-range cho `hcir` và `hh_ar`.
5. Capping outlier bằng IQR cho các biến số.
6. Tạo bảng phân tích rộng từ các dimension/fact trung gian.
7. Tạo `month_id` để rời rạc hóa thời gian theo tháng.
8. Integer encoding cho categorical dimensions và lưu `mapping_dict.json`.

Output mặc định:

```text
data/processed/sashts_final_dataset.csv
data/processed/mapping_dict.json
reports/etl_validation.json
```

### 4.2 Data Warehouse

Data Warehouse được thiết kế theo mô hình **Star Schema**.

Schema SQL:

- [sql/schema.sql](sql/schema.sql): PostgreSQL-compatible schema.
- [sql/schema_sqlserver.sql](sql/schema_sqlserver.sql): SQL Server schema.

ORM/database manager:

- [src/db_manager.py](src/db_manager.py)

Bảng chính:

| Bảng | Vai trò |
|---|---|
| `stg_metadata` | Staging metadata sau ETL |
| `stg_contact_network` | Staging contact network sau ETL |
| `stg_processed_olap` | Bảng OLAP đã mã hóa |
| `Dim_Time` | Chiều thời gian |
| `Dim_Location` | Chiều địa điểm |
| `Dim_Patient` | Chiều bệnh nhân/người tiếp xúc |
| `Fact_Exposure` | Fact event-level cho từng sự kiện tiếp xúc/phơi nhiễm |
| `Fact_Iceberg_Cuboid` | Fact/mart lưu Iceberg Cube heavy-hitters |

Điểm quan trọng:

- `Fact_Exposure` lưu dữ liệu chi tiết ở mức event.
- `Fact_Iceberg_Cuboid` lưu kết quả Star-Cubing/Iceberg Cube.
- DuckDB là Data Warehouse local mặc định để demo không cần server.
- PostgreSQL có thể dùng thay thế qua SQLAlchemy URL.

### 4.3 StarTree

StarTree được triển khai trong [src/star_tree.py](src/star_tree.py).

`StarNode` dùng `__slots__` để giảm bộ nhớ:

```text
attribute_name
attribute_value
count
children
```

StarTree dùng hai bước:

1. Đếm tần suất toàn cục của từng giá trị theo từng chiều.
2. Chèn transaction vào cây sau khi áp dụng **Star Replacement**.

Star Replacement:

```text
Nếu một giá trị có support toàn cục < min_support
=> thay giá trị đó bằng "*"
```

Cơ chế này giúp giảm số nhánh nhiễu và nén dữ liệu vào RAM trước khi chạy
Star-Cubing.

### 4.4 Star-Cubing

Star-Cubing nằm trong [src/algorithm/starcubing.py](src/algorithm/starcubing.py).

Thuật toán đọc các leaf records đã nén từ StarTree, sau đó duyệt top-down theo
từng chiều. Ở mỗi chiều, thuật toán xét:

- Nhánh aggregate `*`: roll-up chiều hiện tại.
- Nhánh giá trị cụ thể: đi sâu vào từng giá trị có support đủ lớn.

Pruning:

```text
Nếu support của một nhánh cụ thể < min_sup
=> tất cả cuboid con cụ thể hơn dưới nhánh đó bị cắt bỏ theo luật Apriori
```

### 4.5 Iceberg Cube

Iceberg Cube là tập các cuboid có:

```text
support_count >= min_sup
```

Cấu hình mặc định trong [scripts/run_pipeline.py](scripts/run_pipeline.py):

```python
DEFAULT_MIN_SUP = 50
DEFAULT_CUBE_DIMENSIONS = ["month_id", "ind1_site", "ind2_site", "pair_sars"]
```

Với dữ liệu hiện tại, pipeline DuckDB đã ghi nhận xấp xỉ:

```text
Fact_Exposure rows: 140,542
Fact_Iceberg_Cuboid rows: 235
```

## 5. Cấu Trúc Thư Mục

```text
data/
  raw/                         Dữ liệu gốc SASHTS
  processed/                   Dữ liệu sau ETL và mapping dictionary
docs/                          Tài liệu thuật toán, hướng dẫn, report notes
notebook/                      Notebook EDA/ETL
powerbi/
  data/                        CSV phục vụ Power BI fallback mode
  screenshots/                 Hình dashboard dùng trong báo cáo
  EpidemicDashboard.pbix       File Power BI chính
reports/                       Kết quả mining, metrics, figures
scripts/                       ETL, pipeline, benchmark, Power BI prep
sql/                           Schema Data Warehouse
src/
  algorithm/                   Star-Cubing và cube export
  api/                         FastAPI backend
  db_manager.py                SQLAlchemy ORM/database manager
  star_tree.py                 Prefix Tree/StarTree
  outbreak_classification.py   Random Forest classification
  contact_network_analysis.py  Network analysis
web-map/                       Next.js web application
```

## 6. Cài Đặt Môi Trường

Yêu cầu:

- Python 3.11 khuyến nghị.
- Node.js 18+ cho Web App.
- Power BI Desktop nếu muốn mở dashboard `.pbix`.

Từ thư mục repo:

```powershell
cd C:\Users\Acer\source\repos\homework\DataMining\Spatiotemporal-Epidemic-Prediction
git pull --ff-only origin main
```

Tạo virtual environment:

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
```

Nếu PowerShell chặn script activation:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
```

## 7. Chạy Toàn Bộ Pipeline

### 7.1 Chạy ETL riêng

```powershell
python scripts/etl.py --metadata-path data/raw/sashts_metadata.csv --network-path data/raw/sashts_contact_network.csv --output-dir data/processed --reports-dir reports
```

### 7.2 Chạy full pipeline với DuckDB

```powershell
python scripts/run_pipeline.py --dw duckdb --duckdb-path warehouse/epidemic.duckdb --refresh
```

Pipeline sẽ tự chạy:

```text
Raw CSV
-> Pandas ETL
-> processed OLAP dataset
-> staging tables
-> Dim_Time / Dim_Location / Dim_Patient
-> Fact_Exposure
-> StarTree + Star-Cubing
-> Fact_Iceberg_Cuboid
-> powerbi/data/*.csv
```

### 7.3 Chạy với PostgreSQL tùy chọn

```powershell
python scripts/run_pipeline.py --dw postgresql --database-url "postgresql+psycopg2://user:password@localhost:5432/epidemic_dw" --refresh
```

## 8. Kiểm Tra Data Warehouse

Sau khi chạy pipeline DuckDB:

```powershell
@'
import duckdb

con = duckdb.connect("warehouse/epidemic.duckdb")

print("Fact_Exposure:", con.execute('SELECT COUNT(*) FROM "Fact_Exposure"').fetchone()[0])
print("Fact_Iceberg_Cuboid:", con.execute('SELECT COUNT(*) FROM "Fact_Iceberg_Cuboid"').fetchone()[0])

print(con.execute("""
SELECT *
FROM v_exposure_by_location_time
LIMIT 10
""").df())

con.close()
'@ | python -
```

Các query SQL hữu ích:

```sql
SELECT COUNT(*) FROM "Fact_Exposure";
SELECT COUNT(*) FROM "Fact_Iceberg_Cuboid";
SELECT * FROM v_exposure_by_location_time LIMIT 10;
SELECT * FROM v_powerbi_overview_kpis;
```

## 9. Power BI Dashboard

File dashboard:

```text
powerbi/EpidemicDashboard.pbix
```

Chuẩn bị CSV fallback từ DuckDB:

```powershell
python scripts/prepare_powerbi_data.py --project-root . --source duckdb --duckdb-path warehouse/epidemic.duckdb --export-csv
```

Các CSV nằm trong:

```text
powerbi/data/
```

### 9.1 Executive Overview

![Power BI Overview](powerbi/screenshots/overview.png)

### 9.2 Outbreak Classification

![Power BI Classification](powerbi/screenshots/classification.png)

### 9.3 Contact Network Analysis

![Power BI Network Analysis](powerbi/screenshots/network_analysis.png)

Power BI có hai chế độ kết nối:

- **DB mode**: kết nối DuckDB qua ODBC hoặc PostgreSQL connector.
- **CSV mode**: import/refresh các file `powerbi/data/*.csv`.

Chi tiết xem thêm:

- [powerbi/docs/powerbi_connection_guide.md](powerbi/docs/powerbi_connection_guide.md)
- [powerbi/docs/dashboard_design.md](powerbi/docs/dashboard_design.md)

## 10. Web Application và API

Repo có một ứng dụng web demo riêng, không phải Power BI. Backend dùng FastAPI,
frontend dùng Next.js và Leaflet.

### 10.1 Chạy FastAPI backend

```powershell
uvicorn src.api.main:app --reload --host 127.0.0.1 --port 8000
```

Mở Swagger UI:

```text
http://127.0.0.1:8000/docs
```

Một số endpoint chính:

| Endpoint | Ý nghĩa |
|---|---|
| `/health` | Kiểm tra API |
| `/api/overview` | KPI tổng quan |
| `/api/risk-polygons` | GeoJSON risk zones demo |
| `/api/classification` | Metrics classification |
| `/api/clusters` | Cluster summaries |
| `/api/network-summary` | Network metrics |
| `/api/top-risk-nodes` | Top risk nodes |
| `/api/predict` | Demo scoring endpoint |

### 10.2 Chạy Next.js frontend

Mở terminal mới:

```powershell
cd web-map
npm install
npm run dev
```

Mở:

```text
http://localhost:3000
```

Mặc định frontend đọc API tại:

```text
http://localhost:8000
```

Nếu cần đổi API URL:

```powershell
$env:NEXT_PUBLIC_API_BASE_URL="http://localhost:8000"
npm run dev
```

### 10.3 Web App Screenshots

Overview:

![Web Overview](web-map/screenshots/overview.png)

Risk Map:

![Web Risk Map](web-map/screenshots/risk%20map.png)

Prediction:

![Web Prediction](web-map/screenshots/prediction.png)

Clusters:

![Web Clusters](web-map/screenshots/clusters.png)

Network:

![Web Network](web-map/screenshots/network.png)

About:

![Web About](web-map/screenshots/about.png)

## 11. Chạy Các Tác Vụ Data Mining Riêng

### 11.1 Ground Zero Clustering

```powershell
py -3.11 scripts/run_clustering_py311.py
```

Output chính:

```text
reports/ground_zero_clustered_cuboids.csv
reports/ground_zero_kmeans_centroids.csv
reports/ground_zero_dbscan_centroids.csv
```

### 11.2 Outbreak Classification

```powershell
python .\src\outbreak_classification.py --project-root . --data-path .\data\processed\sashts_final_dataset.csv --mapping-path .\data\processed\mapping_dict.json --output-dir .\reports\issue_10_outbreak_classification --model random_forest --test-size 0.2 --random-state 42
```

Output chính:

```text
reports/issue_10_outbreak_classification/metrics.json
reports/issue_10_outbreak_classification/feature_importance.csv
reports/issue_10_outbreak_classification/confusion_matrix.csv
reports/issue_10_outbreak_classification/predictions.csv
```

### 11.3 Contact Network Analysis

```powershell
python .\src\contact_network_analysis.py --processed-data .\data\processed\sashts_final_dataset.csv --mapping-path .\data\processed\mapping_dict.json --output-dir .\reports\issue_11_contact_network --top-percent 0.05
```

Output chính:

```text
reports/issue_11_contact_network/graph_summary.json
reports/issue_11_contact_network/edge_list.csv
reports/issue_11_contact_network/top_5_percent_risk_nodes.csv
```

Sau khi chạy các script mining riêng, refresh lại Power BI CSV:

```powershell
python scripts/prepare_powerbi_data.py --project-root . --source duckdb --duckdb-path warehouse/epidemic.duckdb --export-csv
```

## 12. Testing

Chạy toàn bộ test:

```powershell
python -m pytest -q
```

Nếu Windows báo lỗi quyền truy cập thư mục temp của pytest:

```powershell
$tmp = Join-Path (Get-Location) "warehouse\pytest-tmp"
New-Item -ItemType Directory -Force -Path $tmp | Out-Null
$env:TMP=$tmp
$env:TEMP=$tmp
python -m pytest -q
```

Chạy unittest thuật toán riêng:

```powershell
python -m unittest src.star_tree_tests src.star_cubing_tests src.algorithm.starcubing_tests -v
```

## 13. Demo Flow Gợi Ý

Thứ tự demo khuyến nghị:

1. Giới thiệu bộ dữ liệu trong `data/raw/`.
2. Chạy full pipeline:

   ```powershell
   python scripts/run_pipeline.py --dw duckdb --duckdb-path warehouse/epidemic.duckdb --refresh
   ```

3. Query DuckDB để chứng minh Data Warehouse có dữ liệu:

   ```sql
   SELECT COUNT(*) FROM "Fact_Exposure";
   SELECT COUNT(*) FROM "Fact_Iceberg_Cuboid";
   SELECT * FROM v_exposure_by_location_time LIMIT 10;
   ```

4. Mở Power BI dashboard tại `powerbi/EpidemicDashboard.pbix`.
5. Chạy FastAPI:

   ```powershell
   uvicorn src.api.main:app --reload --host 127.0.0.1 --port 8000
   ```

6. Chạy Web App:

   ```powershell
   cd web-map
   npm run dev
   ```

7. Mở `http://localhost:3000` và trình bày Overview, Risk Map, Prediction,
   Clusters, Network.

## 14. Troubleshooting

### Không import được `duckdb` hoặc `duckdb_engine`

```powershell
pip install duckdb duckdb-engine
```

### Chưa có file DuckDB

Chạy lại pipeline:

```powershell
python scripts/run_pipeline.py --dw duckdb --duckdb-path warehouse/epidemic.duckdb --refresh
```

### Power BI không đọc được DuckDB trực tiếp

Dùng CSV fallback:

```powershell
python scripts/prepare_powerbi_data.py --project-root . --source duckdb --duckdb-path warehouse/epidemic.duckdb --export-csv
```

Sau đó import các file trong:

```text
powerbi/data/
```

### Web App không gọi được API

Kiểm tra backend:

```text
http://127.0.0.1:8000/health
```

Nếu frontend chạy ở port khác hoặc backend khác URL, đặt:

```powershell
$env:NEXT_PUBLIC_API_BASE_URL="http://localhost:8000"
npm run dev
```

### File `warehouse/epidemic.duckdb` không thấy trong git

Đây là hành vi đúng. File DuckDB là runtime artifact và đã được ignore để tránh
đẩy database local lên repository.

## Phạm Vi Đồ Án

Repo này phục vụ đồ án môn Data Mining, tập trung chứng minh quy trình:

```text
Dataset -> EDA -> Preprocessing -> Data Warehouse -> Iceberg Cube
-> Classification/Clustering/Network Analysis -> Dashboard/Web Demo
```

Các kết quả phân tích mang tính học thuật và demo, không phải hệ thống giám sát
y tế triển khai thực tế.

## Thành Viên và Phân Công

| Thành viên | Phần chính |
|---|---|
| Dương Quang Đông | Dataset, ETL, EDA, Preprocessing |
| Nguyễn Quốc Khánh | Data Warehouse, StarTree, Star-Cubing, Iceberg Cube |
| Ngô Chánh Phong | Clustering, Classification, Graph Network Analysis |
| Nguyễn Đình Lương | API, Web App, Power BI, Alert System, Benchmark |
