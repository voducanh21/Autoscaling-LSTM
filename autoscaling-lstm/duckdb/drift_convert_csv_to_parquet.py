import os
import sys
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
import s3fs
import numpy as np
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

# =========================================================
# 1) CONFIG
# =========================================================
SERVICE_NAME = os.getenv("SERVICE_NAME", "api-gateway")
CSV_FILE = os.getenv("CSV_FILE", "api-gateway_filled_from_rps.csv")

# Output layout:
# s3://<BUCKET>/<CURRENT_PREFIX>/date=YYYY-MM-DD/service=<SERVICE_NAME>/*.parquet
BUCKET = os.getenv("S3_BUCKET", "datalake")
CURRENT_PREFIX = os.getenv("CURRENT_PREFIX", "drift/current/metrics1")

# CSV columns
CSV_COL_RPS = os.getenv("CSV_COL_RPS", "rps_1m")
CSV_COL_CPU_CORES = os.getenv("CSV_COL_CPU_CORES", "cpu_cores_1m")
CSV_COL_MEM_BYTES = os.getenv("CSV_COL_MEM_BYTES", "mem_bytes")
TS_COL = os.getenv("CSV_TS_COL", "ts")
CSV_COL_SERVICE = os.getenv("CSV_COL_SERVICE", "service")  # if not exists -> use SERVICE_NAME

# Normalization config (same as silver_builder)
CPU_LIMIT_MAP = {
    "api-gateway": 1.0,
    "authentication-service": 0.5,
    "order-service": 0.5,
    "payment-service": 0.5,
    "product-service": 1.0,
}
MEM_LIMIT_BYTES = float(os.getenv("MEM_LIMIT_BYTES", "1073741824"))  # 1GiB default

# Timezone for partitioning date (same idea as silver_builder)
TZ_NAME = os.getenv("TIMEZONE", "Asia/Ho_Chi_Minh")
try:
    TZ = ZoneInfo(TZ_NAME)
except Exception:
    TZ = timezone.utc

# =========================================================
# 2) MINIO / S3 CONFIG (hardcode like File 1)
# =========================================================
fs = s3fs.S3FileSystem(
    key="H7TLSw9YlDtC88KDjzMN",
    secret="6thNYmyTFH1HZdl1DIw4mSx8Z6Eu8p2lIg50yizL",
    client_kwargs={"endpoint_url": "https://minio.voducanh.id.vn"},
)

# =========================================================
# 3) READ CSV
# =========================================================
df = pd.read_csv(CSV_FILE)

if TS_COL not in df.columns:
    raise ValueError(f"CSV must contain '{TS_COL}' column")

# Ensure service column
if CSV_COL_SERVICE in df.columns:
    df["service"] = df[CSV_COL_SERVICE].astype(str)
else:
    df["service"] = str(SERVICE_NAME)

# Required raw columns to compute norm
missing = [c for c in [CSV_COL_RPS, CSV_COL_CPU_CORES, CSV_COL_MEM_BYTES] if c not in df.columns]
if missing:
    raise ValueError(
        f"CSV missing required columns: {missing}. "
        f"Need: {CSV_COL_RPS}, {CSV_COL_CPU_CORES}, {CSV_COL_MEM_BYTES} (and '{TS_COL}')"
    )

# =========================================================
# 4) PARSE TIMESTAMP -> date partition (FIX dtype mix)
#    Support:
#    - epoch seconds (numeric)
#    - ISO8601 string (with/without timezone)
#    Result: df['ts'] is timezone-aware UTC
# =========================================================
s = df[TS_COL]

if pd.api.types.is_numeric_dtype(s):
    ts = pd.to_datetime(s, unit="s", errors="coerce", utc=True)
else:
    ts = pd.to_datetime(s.astype(str), errors="coerce", utc=True)

df["ts"] = ts
df = df.dropna(subset=["ts", "service"]).copy()

# Partition by LOCAL date (align with silver idea)
df["date_part"] = df["ts"].dt.tz_convert(TZ).dt.strftime("%Y-%m-%d")

# =========================================================
# 5) ENFORCE NUMERIC + NORMALIZE (same as silver_builder)
# =========================================================
df["rps_1m"] = pd.to_numeric(df[CSV_COL_RPS], errors="coerce")
df["cpu_cores_1m"] = pd.to_numeric(df[CSV_COL_CPU_CORES], errors="coerce")
df["mem_bytes"] = pd.to_numeric(df[CSV_COL_MEM_BYTES], errors="coerce")

df = df.dropna(subset=["rps_1m", "cpu_cores_1m", "mem_bytes", "date_part", "service"]).copy()

cpu_limit = df["service"].map(CPU_LIMIT_MAP).fillna(1.0).astype(float)
df["cpu_norm"] = (df["cpu_cores_1m"].astype(float) / cpu_limit).astype(np.float32)
df["mem_norm"] = (df["mem_bytes"].astype(float) / float(MEM_LIMIT_BYTES)).astype(np.float32)

# Optional: clip negative rps
df["rps_1m"] = df["rps_1m"].astype(float).clip(lower=0.0)

print("[INFO] Rows:", len(df))
print("[INFO] Dates:", sorted(df["date_part"].unique().tolist()))
print("[INFO] Services:", sorted(df["service"].unique().tolist()))

# =========================================================
# 6) WRITE CURRENT PARQUETS (group by date + service)
# =========================================================
run_ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

for (date_value, svc), df_part in df.groupby(["date_part", "service"]):
    key_prefix = f"{CURRENT_PREFIX}/date={date_value}/service={svc}"
    filename = f"{key_prefix}/part-{run_ts}.parquet"
    s3_path = f"{BUCKET}/{filename}"

    table = pa.Table.from_pandas(
        df_part[["rps_1m", "cpu_norm", "mem_norm"]].reset_index(drop=True),
        preserve_index=False,
    )

    with fs.open(s3_path, "wb") as f:
        pq.write_table(table, f, compression="snappy")

    print(f"[DONE] Wrote {len(df_part)} rows -> s3://{BUCKET}/{filename}")

print("\n[OK] CSV -> drift/current parquet finished")
print(f"[OK] Current prefix: s3://{BUCKET}/{CURRENT_PREFIX}/date=.../service=.../")
