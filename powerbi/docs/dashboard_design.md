# Dashboard Design: Spatiotemporal Epidemic Prediction

## Mục tiêu dashboard

Dashboard Power BI giúp nhóm trình bày kết quả Data Mining của dự án **Spatiotemporal Epidemic Prediction** theo một luồng phân tích rõ ràng:

- Theo dõi bức tranh tổng quan về dữ liệu exposure, số ca truyền nhiễm và hiệu năng mô hình.
- Khai thác Iceberg Cube để phân tích các tổ hợp không gian, thời gian và thuộc tính cá nhân có nguy cơ cao.
- Trực quan hóa kết quả Ground Zero Clustering để nhận diện cụm rủi ro.
- Đánh giá mô hình Outbreak Classification và các feature quan trọng.
- Phân tích Contact Network để tìm node/cụm tiếp xúc có rủi ro cao.

## Page 1: Executive Overview

### Dataset sử dụng

- `powerbi/data/overview_kpis.csv`
- `powerbi/data/exposure_summary.csv`
- `powerbi/data/contact_network_summary.csv`
- `powerbi/data/classification_metrics.csv`

### KPI cards

- Total records
- Total months
- Total contacts
- Total infected contacts
- Transmission records
- Classification accuracy
- Binary F1-score
- Network nodes
- Network edges
- Network density

### Charts

- Line chart: `month_id` theo `total_contacts`.
- Stacked column chart: `month_id` theo `record_count`, phân nhóm bằng `pair_sars`.
- Gauge hoặc card group: accuracy, precision, recall, F1.
- Donut chart: phân bổ `pair_sars` theo `record_count`.

### Filters/Slicers

- `month_id`
- `pair_sars`

### Insight cần rút ra

- Giai đoạn nào có mức độ tiếp xúc cao nhất.
- Tỷ lệ record truyền nhiễm so với non-transmission.
- Hiệu năng tổng quan của mô hình có đủ tốt để hỗ trợ phân tích rủi ro hay không.
- Mạng tiếp xúc có dày đặc hay phân tán.

## Page 2: Iceberg Cube Analytics

### Dataset sử dụng

- `powerbi/data/cube_analytics.csv`
- `powerbi/data/exposure_summary.csv`

### KPI cards

- Total cuboids
- Total contacts
- Total infected contacts
- Average duration
- Average HCIR
- Average HH_AR

### Charts

- Matrix: `month_id`, `ind1_site`, `ind2_site`, `pair_sars` với measures `cuboid_count`, `total_contacts`, `total_contacts_infected`.
- Heatmap-like matrix: site pair theo `total_contacts_infected`.
- Bar chart: top site pairs theo `total_contacts`.
- Line chart: xu hướng `cuboid_count` theo `month_id`.

### Filters/Slicers

- `month_id`
- `pair_sars`
- `ind1_site`
- `ind2_site`
- `kmeans_cluster`
- `dbscan_cluster`

### Insight cần rút ra

- Tổ hợp chiều nào vượt ngưỡng nhiều nhất.
- Site pair nào có tổng tiếp xúc hoặc tiếp xúc nhiễm cao.
- Các cuboid rủi ro cao tập trung vào tháng, site hoặc cluster nào.

## Page 3: Ground Zero Clustering

### Dataset sử dụng

- `powerbi/data/ground_zero_clusters.csv`
- `powerbi/data/cube_analytics.csv`

### KPI cards

- Number of KMeans clusters
- Number of DBSCAN clusters
- Largest cluster by record count
- Highest total exposure cluster
- Average exposure per cluster

### Charts

- Bar chart: `cluster_id` theo `record_count`, phân nhóm bằng `algorithm`.
- Bar chart: `cluster_id` theo `total_contacts` hoặc `total_exposure`.
- Scatter chart: centroid fields nếu có trong dữ liệu centroid.
- Table: cluster summary gồm `algorithm`, `cluster_id`, `record_count`, `total_contacts`, `avg_duration_sec`, `avg_hcir`, `avg_hh_ar`.

### Filters/Slicers

- `algorithm`
- `cluster_id`
- `month_id` nếu dùng thêm `cube_analytics.csv`
- `pair_sars`

### Insight cần rút ra

- Cluster nào có nguy cơ cao nhất theo exposure/contact.
- KMeans và DBSCAN có cho ra phân cụm nhất quán hay khác biệt đáng kể.
- Các cụm rủi ro cao có liên hệ với nhóm cuboid/thời gian nào.

## Page 4: Outbreak Classification

### Dataset sử dụng

- `powerbi/data/classification_metrics.csv`
- `powerbi/data/classification_feature_importance.csv`
- `powerbi/data/classification_confusion_matrix.csv`

### KPI cards

- Accuracy
- Precision macro
- Recall macro
- F1 macro
- Precision binary
- Recall binary
- F1 binary
- Train rows
- Test rows

### Charts

- Bar chart: top features theo `importance`.
- Matrix: confusion matrix với `actual_class`, `predicted_class`, `count`.
- Bar chart: metric comparison theo `metric` và `value`.
- Card hoặc table: train/test months.

### Filters/Slicers

- `feature`
- `metric`
- `actual_class`
- `predicted_class`

### Insight cần rút ra

- Mô hình phân loại outbreak có cân bằng precision/recall hay không.
- Feature nào đóng góp nhiều nhất cho dự đoán.
- Lỗi dự đoán tập trung ở false positive hay false negative.
- Temporal split đã tách train/test theo tháng nào.

## Page 5: Contact Network Analysis

### Dataset sử dụng

- `powerbi/data/contact_network_summary.csv`
- `powerbi/data/high_risk_nodes.csv`
- `powerbi/data/network_edges.csv`

### KPI cards

- Number of nodes
- Number of edges
- Network density
- Connected components
- Largest component size
- Top percent threshold

### Charts

- Bar chart: top nodes theo `risk_score`.
- Bar chart: top nodes theo `weighted_degree`.
- Scatter chart: `degree_centrality` và `betweenness_centrality`, size theo `weighted_degree`.
- Table: high-risk nodes với `node_id`, `risk_rank`, `risk_score`, `degree`, `weighted_degree`, `duration_sum`.
- Table hoặc custom visual: edge list với `node_u`, `node_v`, `weight`, `record_count`.

### Filters/Slicers

- `risk_rank`
- `node_id`
- `node_u`
- `node_v`

### Insight cần rút ra

- Node nào là điểm rủi ro cao trong mạng tiếp xúc.
- Rủi ro đến từ số lượng kết nối, vị trí trung gian trong graph hay tổng trọng số tiếp xúc.
- Mạng tiếp xúc có nhiều component nhỏ hay một component lớn chi phối.
- Các cạnh nào có trọng số tiếp xúc cao cần được ưu tiên theo dõi.

## Quy ước thiết kế đề xuất

- Dùng màu nhất quán:
  - Xanh dương cho volume/contact.
  - Đỏ hoặc cam cho outbreak/high-risk.
  - Xanh lá cho model quality hoặc trạng thái tốt.
- Đặt slicer ở cạnh trái hoặc hàng trên cùng mỗi page.
- KPI cards đặt ở hàng đầu tiên để người xem nắm nhanh trạng thái.
- Với bảng lớn, bật search/filter và giới hạn top N khi trình bày.
- Đặt tooltip giải thích các metric như `risk_score`, `weighted_degree`, `f1_binary`.

