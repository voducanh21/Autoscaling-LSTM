import duckdb

S3_PATH = "s3://datalake/bronze/metrics/date=2025-09-16/service=payment-service"

con = duckdb.connect()
con.execute("""
  INSTALL httpfs;
  LOAD httpfs;
  SET s3_url_style='path';
  SET s3_endpoint='127.0.0.1:9000';
  SET s3_use_ssl=false;
  SET s3_access_key_id='6VLd8iEOyp97NrDqLyyB';
  SET s3_secret_access_key='bufBJSbuCcMYHZV81vvGRXcaOUJbi2YrxtEFNaOj';
""")

# Đọc toàn bộ các file .parquet trong folder
df = con.execute(f"""
  SELECT *
  FROM read_parquet('{S3_PATH}/*.parquet')
  ORDER BY ts
  LIMIT 100
""").fetchdf()

print("=== Preview (100 rows) ===")
print(df.to_string(index=False))

# Đếm tổng số dòng
n_rows = con.execute(f"SELECT count(*) FROM read_parquet('{S3_PATH}/*.parquet')").fetchone()[0]
print("\nTổng số dòng:", n_rows)
