# Spatiotemporal Epidemic Prediction

Kho lưu trữ đồ án môn Data Mining về phân tích và dự đoán nguy cơ lây nhiễm
dựa trên dữ liệu dịch tễ có yếu tố không gian, thời gian và mạng tiếp xúc.

Đề tài tập trung vào việc biến dữ liệu tiếp xúc thô thành các mẫu dịch tễ có
ý nghĩa bằng ETL, Data Warehouse, Prefix Tree, Star-Cubing và Iceberg Cube.

## Mục Tiêu Đề Tài

- Tiền xử lý dữ liệu dịch tễ và mạng tiếp xúc từ bộ SASHTS.
- Thiết kế Data Warehouse dạng Star Schema để lưu kết quả phân tích.
- Cài đặt Prefix Tree/Star Tree để nén quỹ đạo hoặc transaction vào RAM.
- Trích xuất Iceberg Cube bằng Star-Cubing với ngưỡng hỗ trợ tối thiểu.
- Xuất các cuboid vượt ngưỡng vào bảng fact để phục vụ truy vấn và khai phá.

## Pipeline Tổng Quan

```text
Raw Data -> ETL -> Star Tree -> Star-Cubing / Iceberg Cube -> Data Warehouse -> Mining / Reports
```

## Thành Phần Chính

### Data Warehouse

Schema được định nghĩa trong:

- `sql/schema.sql`: PostgreSQL schema.
- `sql/schema_sqlserver.sql`: SQL Server schema.

Mô hình gồm các bảng dimension và fact:

- `Dim_Time`: chiều thời gian.
- `Dim_Location`: chiều địa điểm.
- `Dim_Patient`: chiều cá nhân/bệnh nhân.
- `Fact_Exposure`: lưu các tổ hợp vượt ngưỡng với measure `count_exposure`.

Kết nối database và ORM được cài đặt bằng SQLAlchemy trong `src/db_manager.py`.

### Star Tree

`src/star_tree.py` cài đặt:

- `StarNode` dùng `__slots__` để giảm RAM.
- `StarTree` để lưu transaction theo cấu trúc cây tiền tố.
- Star Replacement dựa trên global support trước khi insert vào cây.

API chính:

```python
from src.star_tree import StarTree

tree = StarTree(["site", "age_group", "sex"], min_support=2)
tree.build_from_transactions(transactions)
```

### Star-Cubing và Iceberg Cube

`src/algorithm/starcubing.py` cài đặt:

- `starcubing(tree, min_sup)`: trích xuất các Iceberg Cuboids thỏa `min_sup`.
- Top-down traversal theo từng chiều.
- Bottom-up pruning theo luật Apriori cho các nhánh không đủ support.
- `export_cube_to_sql(...)`: batch insert kết quả cube vào `Fact_Exposure`.

`src/star_cubing.py` là wrapper tương thích để import cũ vẫn chạy.

## Cấu Trúc Thư Mục

```text
data/
  raw/                  Dữ liệu thô
  processed/            Dữ liệu sau ETL và mapping dictionary
docs/                   Tài liệu thuật toán
notebook/               Notebook EDA/ETL
reports/                Kết quả và hình ảnh báo cáo
sql/                    Schema Data Warehouse
src/                    Source code chính
  algorithm/            Star-Cubing và export cube
  db_manager.py         SQLAlchemy ORM/database manager
  data_loader.py        Loader dữ liệu vào warehouse
  star_tree.py          Prefix Tree/Star Tree
```

## Cài Đặt

```bash
pip install -r requirements.txt
```

Tạo file `.env` từ `.env.example` nếu cần cấu hình database thật. Mặc định có
thể dùng SQLite cho kiểm thử local; PostgreSQL và SQL Server được hỗ trợ qua
connection string SQLAlchemy.

## Chạy Test

```bash
python -m pytest -q
```

Hoặc chạy unittest trực tiếp:

```bash
python -m unittest src.star_tree_tests src.star_cubing_tests src.algorithm.starcubing_tests -v
```

## Trạng Thái Hoàn Thiện

- Data Warehouse Star Schema: hoàn thiện cho PostgreSQL và SQL Server.
- SQLAlchemy integration: hoàn thiện trong `src/db_manager.py`.
- Star Tree với `__slots__` và global Star Replacement: hoàn thiện.
- Star-Cubing với top-down traversal và Apriori pruning: hoàn thiện.
- Export Iceberg Cube sang `Fact_Exposure` bằng batch insert: hoàn thiện.
- Test tự động: `pytest` nhận diện và chạy toàn bộ test hiện có.

## Phạm Vi Môn Học

Repo này thuộc nhóm bài toán Data Mining ứng dụng trong dịch tễ học, kết hợp:

- Data preprocessing.
- Data warehousing.
- Frequent pattern mining.
- Multidimensional cube mining.
- Network/contact analysis.

Mục tiêu cuối cùng là tạo nền tảng dữ liệu có thể mở rộng cho phân tích mẫu
lây nhiễm theo không gian, thời gian và đặc trưng cá nhân.
