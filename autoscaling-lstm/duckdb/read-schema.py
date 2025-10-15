import duckdb

# === Cấu hình S3 ===
S3_PATH = "s3://datalake/bronze/metrics/date=2025-10-15/service=product-service"

# === Kết nối và cấu hình DuckDB + HTTPFS ===
con = duckdb.connect()
con.execute("""
  INSTALL httpfs;
  LOAD httpfs;

  SET s3_url_style='path';
  SET s3_endpoint='127.0.0.1:9000';
  SET s3_use_ssl=false;
  SET s3_access_key_id='RQpwLJ6SEL3dEDjxGUWw';
  SET s3_secret_access_key='CLtRwSIAU1EzKEATqP91fVsC6sCFa069mO4lmrJO';
""")

# === Đọc trước vài dòng để xem dữ liệu (tắt hive_partitioning) ===
df = con.execute(f"""
  SELECT *
  FROM read_parquet('{S3_PATH}/*.parquet', hive_partitioning=false)
  ORDER BY ts
  LIMIT 100
""").fetchdf()

print("=== Preview (100 rows) ===")
print(df.to_string(index=False))

# === Kiểm tra kiểu dữ liệu (schema thực tế trong file) ===
schema = con.execute(f"""
  DESCRIBE SELECT * FROM read_parquet('{S3_PATH}/*.parquet', hive_partitioning=false)
""").fetchdf()

print("\n=== Schema ===")
print(schema)

# === Đếm tổng số dòng ===
n_rows = con.execute(f"""
  SELECT count(*) 
  FROM read_parquet('{S3_PATH}/*.parquet', hive_partitioning=false)
""").fetchone()[0]

print("\nTổng số dòng:", n_rows)
