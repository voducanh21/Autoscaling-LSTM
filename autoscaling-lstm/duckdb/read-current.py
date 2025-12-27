import os
import pandas as pd
import pyarrow.parquet as pq
import s3fs

# =========================
# CONFIG
# =========================
BUCKET = os.getenv("S3_BUCKET", "datalake")
CURRENT_PREFIX = os.getenv("CURRENT_PREFIX", "drift/current/metrics1")
SERVICE_NAME = os.getenv("SERVICE_NAME", "product-service")
DAY = os.getenv("DAY", "2025-02-01")  # YYYY-MM-DD

# MinIO credentials (same as your scripts)
S3_ENDPOINT = os.getenv("S3_ENDPOINT", "https://minio.voducanh.id.vn")

fs = s3fs.S3FileSystem(
    key="H7TLSw9YlDtC88KDjzMN",
    secret="6thNYmyTFH1HZdl1DIw4mSx8Z6Eu8p2lIg50yizL",
    client_kwargs={"endpoint_url": S3_ENDPOINT},
)

# =========================
# READ ALL PARQUETS IN 1 DAY
# =========================
prefix = f"{BUCKET}/{CURRENT_PREFIX}/date={DAY}/service={SERVICE_NAME}/"
files = sorted(fs.glob(prefix + "*.parquet"))

if not files:
    raise SystemExit(f"No parquet files found at s3://{prefix}")

dfs = []
for fpath in files:
    with fs.open(fpath, "rb") as f:
        df = pq.read_table(f).to_pandas()
        dfs.append(df)

out = pd.concat(dfs, ignore_index=True)

print("[INFO] files:", len(files))
print("[INFO] rows:", len(out))
print(out.head(10))

# Optional: save local
# out.to_csv(f"current_{SERVICE_NAME}_{DAY}.csv", index=False)
