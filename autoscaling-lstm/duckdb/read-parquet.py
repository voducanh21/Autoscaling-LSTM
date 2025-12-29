import os
import s3fs
import pyarrow.parquet as pq
import pandas as pd

# =========================
# 1) Cấu hình MinIO (khuyên dùng ENV thay vì hardcode)
# =========================
MINIO_ENDPOINT = os.getenv("MINIO_ENDPOINT", "https://minio.voducanh.id.vn")
MINIO_KEY = os.getenv("MINIO_KEY", "H7TLSw9YlDtC88KDjzMN")
MINIO_SECRET = os.getenv("MINIO_SECRET", "6thNYmyTFH1HZdl1DIw4mSx8Z6Eu8p2lIg50yizL")

# Nếu MinIO dùng cert tự ký và bị lỗi SSL, thử bật dòng dưới (không khuyến nghị cho production)
# VERIFY_TLS = os.getenv("VERIFY_TLS", "true").lower() == "true"
VERIFY_TLS = True  # đổi False nếu cần

fs = s3fs.S3FileSystem(
    key=MINIO_KEY,
    secret=MINIO_SECRET,
    client_kwargs={"endpoint_url": MINIO_ENDPOINT, "verify": VERIFY_TLS},
)

# =========================
# 2) Chọn đúng đường dẫn theo ảnh: bucket=datalake
# =========================
BUCKET = "datalake"
PREFIX = "silver/metrics/date=2025-12-28/service=api-gateway/"  # nhớ có dấu / cuối

# Lấy danh sách parquet trong "thư mục"
parquet_files = sorted(fs.glob(f"{BUCKET}/{PREFIX}*.parquet"))
if not parquet_files:
    raise ValueError(f"Không tìm thấy file .parquet trong {BUCKET}/{PREFIX}")

print(f"→ Tìm thấy {len(parquet_files)} file parquet:")
for f in parquet_files:
    print("  ", f)

# =========================
# 3) Đọc schema (file đầu tiên)
# =========================
with fs.open(parquet_files[0], "rb") as f0:
    table0 = pq.read_table(f0)
    print("\n=== Schema (file đầu tiên) ===")
    print(table0.schema)

# =========================
# 4) Đọc & gộp dữ liệu
# =========================
dfs = []
for f in parquet_files:
    with fs.open(f, "rb") as fo:
        t = pq.read_table(fo)
        dfs.append(t.to_pandas())

df_all = pd.concat(dfs, ignore_index=True)

# =========================
# 5) In thử dữ liệu
# =========================
pd.set_option("display.max_columns", None)
pd.set_option("display.width", 0)

print("\n=== Head(20) ===")
print(df_all.head(20))

print("\n=== Tail(20) ===")
print(df_all.tail(20))

print(f"\nTổng số dòng: {len(df_all)}")
print(f"Tổng số cột: {df_all.shape[1]}")

# =========================
# 6) Thống kê nhanh (hữu ích để kiểm tra rps_future có bị 'kẹt' quanh 100 không)
# =========================
def show_quantiles(df, col):
    if col not in df.columns:
        print(f"[SKIP] Không có cột {col}")
        return
    s = pd.to_numeric(df[col], errors="coerce").dropna()
    if s.empty:
        print(f"[SKIP] Cột {col} toàn NaN/không convert được")
        return
    qs = s.quantile([0.5, 0.9, 0.95, 0.99]).to_dict()
    print(f"\n[{col}] describe:\n{s.describe()}")
    print(f"[{col}] quantiles (p50/p90/p95/p99): {qs}")

for c in ["rps_1m", "rps_future", "cpu_norm", "cpu_future", "mem_norm", "mem_future", "latency_p95_ms"]:
    show_quantiles(df_all, c)

# Nếu muốn xem toàn bộ (cẩn thận rất dài):
# pd.set_option("display.max_rows", None)
# print(df_all)
