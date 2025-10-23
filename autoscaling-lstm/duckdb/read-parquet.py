import s3fs
import pyarrow.parquet as pq
import pandas as pd

# ===== Cấu hình MinIO =====
fs = s3fs.S3FileSystem(
    key="1Z3UT6tcLTuxaDrJYoyO",
    secret="6Vs1ORxhTNzcgzRyTvQsslsWVEfhH1ESxsbaVRRx",
    client_kwargs={"endpoint_url": "http://127.0.0.1:9000"},
)

# ===== Đường dẫn folder =====
prefix = "datalake/silver/metrics/date=2025-10-23/service=product-service"

# ===== Lấy danh sách file .parquet =====
files = fs.ls(prefix)
parquet_files = [f for f in files if f.endswith(".parquet")]

if not parquet_files:
    raise ValueError("Không tìm thấy file parquet nào trong thư mục.")

print(f"Tìm thấy {len(parquet_files)} file Parquet.")
dfs = []

for file in sorted(parquet_files):
    print(f"→ Đọc: {file}")
    with fs.open(file, "rb") as f:
        table = pq.read_table(f)
        df_part = table.to_pandas()
        dfs.append(df_part)

# ===== Ghép tất cả file lại =====
df = pd.concat(dfs, ignore_index=True)

print("\n=== Schema trong Parquet ===")
print(table.schema)

print("\n=== 5 dòng đầu ===")
print(df.head())

print(f"\nTổng số dòng: {len(df)}")
