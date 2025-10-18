import pyarrow.parquet as pq
import s3fs
import pandas as pd

# --- Kết nối MinIO qua S3 API ---
fs = s3fs.S3FileSystem(
    key="1Z3UT6tcLTuxaDrJYoyO",
    secret="6Vs1ORxhTNzcgzRyTvQsslsWVEfhH1ESxsbaVRRx",
    client_kwargs={"endpoint_url": "http://127.0.0.1:9000"},
)

# --- Đường dẫn file silver ---
path = "datalake/silver/metrics/date=2025-10-18/service=authentication-service/part-1760724386.parquet"

# --- Đọc thủ công bằng PyArrow ---
with fs.open(path, "rb") as f:
    table = pq.read_table(f, read_dictionary=[])  # tắt dictionary decoding
    df = table.to_pandas()

print("=== Schema trong Parquet ===")
print(table.schema)

print("\n=== 10 dòng đầu ===")
print(df.head(10).to_string(index=False))

print("\nTổng số dòng:", len(df))
