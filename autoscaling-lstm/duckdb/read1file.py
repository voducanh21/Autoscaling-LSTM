import s3fs
import pyarrow.parquet as pq
import pandas as pd

fs = s3fs.S3FileSystem(
    key="H7TLSw9YlDtC88KDjzMN",
    secret="6thNYmyTFH1HZdl1DIw4mSx8Z6Eu8p2lIg50yizL",
    client_kwargs={"endpoint_url": "https://minio.voducanh.id.vn"},
)

file_path = "datalake/silver/metrics/date=2025-11-23/service=api-gateway/part-1763913049.parquet"

print("Exists?", fs.exists(file_path))

with fs.open(file_path, "rb") as f:
    table = pq.read_table(f)
    df = table.to_pandas()

# ===== Bật full hiển thị =====
pd.set_option("display.max_columns", None)
pd.set_option("display.max_rows", None)
pd.set_option("display.max_colwidth", None)
pd.set_option("display.width", 0)

print(table.schema)
print(df)
