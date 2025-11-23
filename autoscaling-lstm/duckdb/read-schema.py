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
prefix = "datalake/silver/metrics/date=2025-11-21/service=api-gateway"

# ===== Lấy danh sách file .parquet =====
files = fs.ls(prefix)
parquet_files = [f for f in files if f.endswith(".parquet")]

if not parquet_files:
    raise ValueError("Không tìm thấy file Parquet nào trong thư mục Silver.")

print(f"→ Tìm thấy {len(parquet_files)} file parquet:")
for f in parquet_files:
    print("  ", f)

# ===== Đọc và gộp dữ liệu, chỉ lấy 2 cột =====
dfs = []
for f in parquet_files:
    with fs.open(f, "rb") as file:
        table = pq.read_table(file, columns=["ts", "service"])
        df = table.to_pandas()
        dfs.append(df)

df_all = pd.concat(dfs, ignore_index=True)

# ===== Hiển thị schema và dữ liệu chỉ gồm ts, service =====
print("\n=== Schema trong Parquet (rút gọn) ===")
print(df_all.dtypes)

print("\n=== Dữ liệu (chỉ gồm ts, service) ===")
pd.set_option("display.max_rows", None)
pd.set_option("display.width", 0)
print(df_all)

print(f"\nTổng số dòng sau khi gộp: {len(df_all)}")
