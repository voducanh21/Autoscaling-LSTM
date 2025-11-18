import s3fs
import pyarrow.parquet as pq
import pandas as pd

# ===== Hiển thị số dạng bình thường (không scientific notation) =====
pd.set_option("display.float_format", "{:.6f}".format)
pd.set_option("display.max_rows", None)
pd.set_option("display.max_columns", None)
pd.set_option("display.width", 0)

# ===== Cấu hình MinIO =====
fs = s3fs.S3FileSystem(
    key="H7TLSw9YlDtC88KDjzMN",
    secret="6thNYmyTFH1HZdl1DIw4mSx8Z6Eu8p2lIg50yizL",
    client_kwargs={"endpoint_url": "https://minio.voducanh.id.vn"},
)

# ===== Đường dẫn thư mục baseline =====
prefix = "datalake/baseline/metrics/"

# ===== Lấy danh sách file .parquet =====
files = fs.ls(prefix)
parquet_files = [f for f in files if f.endswith(".parquet")]

if not parquet_files:
    raise ValueError("Không tìm thấy file Parquet nào trong baseline.")

print(f"→ Tìm thấy {len(parquet_files)} file parquet:")
for f in parquet_files:
    print("  ", f)

# ===== Đọc & gộp dữ liệu =====
dfs = []
for f in parquet_files:
    with fs.open(f, "rb") as file:
        table = pq.read_table(file)
        df = table.to_pandas()
        dfs.append(df)

df_all = pd.concat(dfs, ignore_index=True)

# ===== In schema =====
print("\n=== Schema trong Parquet (theo file đầu tiên) ===")
with fs.open(parquet_files[0], "rb") as f:
    table = pq.read_table(f)
    print(table.schema)

# ===== Hiển thị dữ liệu =====
print("\n=== Toàn bộ dữ liệu gộp trong DataFrame ===")
print(df_all)

print(f"\nTổng số dòng sau khi gộp: {len(df_all)}")
