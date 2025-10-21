import pyarrow.parquet as pq
import s3fs
import pandas as pd

fs = s3fs.S3FileSystem(
    key="1Z3UT6tcLTuxaDrJYoyO",
    secret="6Vs1ORxhTNzcgzRyTvQsslsWVEfhH1ESxsbaVRRx",
    client_kwargs={"endpoint_url": "http://127.0.0.1:9000"},
)

path = "datalake/bronze/metrics/date=2025-10-20/service=api-gateway/part-1760896643.parquet"
print(f"Đang đọc file: {path}")

with fs.open(path, "rb") as f:
    table = pq.read_table(f)
    df = table.to_pandas()

print("=== Schema trong Parquet ===")
print(table.schema)
print("\n=== 5 dòng đầu ===")
print(df.head())

print("\nTổng số dòng:", len(df))
