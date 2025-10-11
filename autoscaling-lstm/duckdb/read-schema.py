import duckdb
con = duckdb.connect()
con.execute("""
  INSTALL httpfs; LOAD httpfs;
  SET s3_endpoint='127.0.0.1:9000';
  SET s3_url_style='path';
  SET s3_use_ssl=false;
  SET s3_access_key_id='v8mkulsmdVrQ6a5DIEut';
  SET s3_secret_access_key='ZXN06NuuBIqKWuE8E7KaO9a2iB84yNNXxhUlLRBd';
""")
df = con.execute("SELECT file FROM glob('s3://datalake/bronze/metrics/**/*.parquet')").fetchdf()
print(df)
