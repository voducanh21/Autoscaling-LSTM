import s3fs
import pyarrow.parquet as pq
import pandas as pd

# ===== Cấu hình MinIO =====
fs = s3fs.S3FileSystem(
    key="H7TLSw9YlDtC88KDjzMN",
    secret="6thNYmyTFH1HZdl1DIw4mSx8Z6Eu8p2lIg50yizL",
    client_kwargs={"endpoint_url": "https://minio.voducanh.id.vn"},
)

# ===== Đường dẫn thư mục Silver cụ thể =====
prefix = "datalake/bronze/metrics/date=2025-11-14/service=api-gateway"

# ===== Lấy danh sách file .parquet =====
files = fs.ls(prefix)
parquet_files = [f for f in files if f.endswith(".parquet")]

if not parquet_files:
    raise ValueError("Không tìm thấy file Parquet nào trong thư mục Silver.")

print(f"→ Tìm thấy {len(parquet_files)} file parquet:")
for f in parquet_files:
    print("  ", f)

# ===== Đọc và gộp tất cả dữ liệu =====
dfs = []
for f in parquet_files:
    with fs.open(f, "rb") as file:
        table = pq.read_table(file)
        df = table.to_pandas()
        dfs.append(df)

df_all = pd.concat(dfs, ignore_index=True)

# ===== Hiển thị schema và toàn bộ dữ liệu =====
print("\n=== Schema trong Parquet (theo file đầu tiên) ===")
print(pq.read_table(fs.open(parquet_files[0], "rb")).schema)

print("\n=== Toàn bộ dữ liệu gộp trong DataFrame ===")
pd.set_option("display.max_rows", None)
pd.set_option("display.max_columns", None)
pd.set_option("display.width", 0)
print(df_all)

print(f"\nTổng số dòng sau khi gộp: {len(df_all)}")
