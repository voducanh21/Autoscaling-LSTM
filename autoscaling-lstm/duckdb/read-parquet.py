import s3fs
import pyarrow.parquet as pq
import pandas as pd

# ===== Cấu hình MinIO =====
fs = s3fs.S3FileSystem(
    key="1Z3UT6tcLTuxaDrJYoyO",
    secret="6Vs1ORxhTNzcgzRyTvQsslsWVEfhH1ESxsbaVRRx",
    client_kwargs={"endpoint_url": "http://127.0.0.1:9000"},
)

# ===== Đường dẫn thư mục Silver cụ thể =====
prefix = "datalake/silver/metrics/date=2025-10-23/service=api-gateway"

# ===== Lấy danh sách file .parquet =====
files = fs.ls(prefix)
parquet_files = [f for f in files if f.endswith(".parquet")]

if not parquet_files:
    raise ValueError("Không tìm thấy file Parquet nào trong thư mục Silver.")

# ===== Lấy file mới nhất =====
latest_file = max(parquet_files, key=lambda f: fs.info(f)["LastModified"])
print(f"→ Đang đọc file mới nhất: {latest_file}")

# ===== Đọc toàn bộ dữ liệu trong file =====
with fs.open(latest_file, "rb") as f:
    table = pq.read_table(f)
    df = table.to_pandas()

# ===== Hiển thị schema và toàn bộ dữ liệu =====
print("\n=== Schema trong Parquet ===")
print(table.schema)

print("\n=== Toàn bộ dữ liệu trong DataFrame ===")
pd.set_option("display.max_rows", None)
pd.set_option("display.max_columns", None)
pd.set_option("display.width", 0)
print(df)

print(f"\nTổng số dòng: {len(df)}")
