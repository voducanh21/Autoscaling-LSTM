import s3fs
import pyarrow.parquet as pq
import pandas as pd

# ======== CẤU HÌNH =========
service_name = "product-service"
date = "2025-12-01"

prefix = f"datalake/silver/metrics/date={date}/service={service_name}"

# ======== MinIO Config =========
fs = s3fs.S3FileSystem(
    key="H7TLSw9YlDtC88KDjzMN",
    secret="6thNYmyTFH1HZdl1DIw4mSx8Z6Eu8p2lIg50yizL",
    client_kwargs={"endpoint_url": "https://minio.voducanh.id.vn"},
)

print(f"→ Đang đọc từ thư mục: {prefix}")

# ======== Lấy danh sách file Parquet =========
files = fs.ls(prefix)
parquet_files = [f for f in files if f.endswith(".parquet")]

if not parquet_files:
    raise ValueError(f"Không tìm thấy file parquet trong: {prefix}")

print(f"→ Tìm thấy {len(parquet_files)} file parquet.")

# ======== Đọc và gộp =========
dfs = []
for f in parquet_files:
    with fs.open(f, "rb") as file:
        table = pq.read_table(file)
        df = table.to_pandas()
        dfs.append(df)

df_all = pd.concat(dfs, ignore_index=True)

# ======== LƯU CSV TRỰC TIẾP LÊN MINIO =========
output_path = f"{prefix}/merged_{service_name}_{date}.csv"

with fs.open(output_path, "w") as f:
    df_all.to_csv(f, index=False)

print("\n================ DONE ================")
print("✓ Đã lưu file CSV trực tiếp lên MinIO:")
print(f"  {output_path}")
print(f"✓ Tổng số dòng: {len(df_all)}")
print("======================================")
