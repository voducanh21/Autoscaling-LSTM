import pyarrow.parquet as pq
import s3fs
import pandas as pd

# --- Kết nối MinIO qua S3 API ---
fs = s3fs.S3FileSystem(
    key="1Z3UT6tcLTuxaDrJYoyO",
    secret="6Vs1ORxhTNzcgzRyTvQsslsWVEfhH1ESxsbaVRRx",
    client_kwargs={"endpoint_url": "http://127.0.0.1:9000"},
)

# --- Tự động tìm file gold mới nhất ---
files = sorted(fs.glob("datalake/gold/metrics/gold-*.parquet"))
if not files:
    raise FileNotFoundError("Không tìm thấy file nào trong datalake/gold/metrics/")
latest = files[-1]
print(f"Đang đọc file gold mới nhất: {latest}")

# --- Đọc file parquet ---
with fs.open(latest, "rb") as f:
    table = pq.read_table(f, read_dictionary=[])
    df = table.to_pandas()

print("=== Schema trong Parquet ===")
print(table.schema)

print("\n=== 10 dòng đầu ===")
print(df.head(10).to_string(index=False))

print("\nTổng số dòng:", len(df))
