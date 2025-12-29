import os
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
import s3fs
from datetime import datetime

# =====================================================================
# 1. CẤU HÌNH DỄ THAY ĐỔI CHO MỖI SERVICE
# =====================================================================

SERVICE_NAME = "product-service"          # ← đổi tên service tại đây
CSV_FILE = "product-service_filled_from_rps.csv"          # ← đổi file CSV tại đây

# =====================================================================
# 2. CẤU HÌNH MINIO (KHÔNG CẦN ĐỔI)
# =====================================================================

fs = s3fs.S3FileSystem(
    key="H7TLSw9YlDtC88KDjzMN",
    secret="6thNYmyTFH1HZdl1DIw4mSx8Z6Eu8p2lIg50yizL",
    client_kwargs={"endpoint_url": "https://minio.voducanh.id.vn"},
)

BRONZE_PREFIX = "datalake/bronze/metrics"

# =====================================================================
# 3. ĐỌC CSV
# =====================================================================

df = pd.read_csv(CSV_FILE)
if "ts" not in df.columns:
    raise ValueError("CSV phải chứa cột 'ts'")

# =====================================================================
# 4. XỬ LÝ TIMESTAMP
# =====================================================================

# Nếu ts là epoch (int/float)
try:
    df["ts"] = pd.to_datetime(df["ts"], unit="s")
except:
    # Nếu ts là string ISO8601
    df["ts"] = pd.to_datetime(df["ts"])

df["date"] = df["ts"].dt.strftime("%Y-%m-%d")

print("Số dòng:", len(df))
print("Các ngày tìm thấy:", df["date"].unique())

# =====================================================================
# 5. GHI THEO NGÀY VÀ SERVICE
# =====================================================================

for date_value, df_day in df.groupby("date"):
    # Tạo prefix theo service + date (partitioning)
    prefix = f"{BRONZE_PREFIX}/date={date_value}/service={SERVICE_NAME}"

    # Tạo unique filename
    tsid = int(datetime.utcnow().timestamp())
    filename = f"{prefix}/part-{tsid}.parquet"

    # Convert DataFrame -> Arrow
    table = pa.Table.from_pandas(df_day)

    # Ghi vào MinIO
    with fs.open(filename, "wb") as f:
        pq.write_table(table, f, compression="snappy")

    print(f"Đã ghi {len(df_day)} dòng -> {filename}")

# =====================================================================
print("\nHoàn thành ETL CSV -> Parquet")
print(f"Service: {SERVICE_NAME}")
