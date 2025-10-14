import duckdb
con = duckdb.connect()
con.execute("""
  INSTALL httpfs; LOAD httpfs;
  SET s3_endpoint='127.0.0.1:9000';
  SET s3_url_style='path';
  SET s3_use_ssl=false;
  SET s3_access_key_id='RQpwLJ6SEL3dEDjxGUWw';
  SET s3_secret_access_key='CLtRwSIAU1EzKEATqP91fVsC6sCFa069mO4lmrJO';
""")
df = con.execute("SELECT file FROM glob('s3://datalake/bronze/metrics/**/*.parquet')").fetchdf()
print(df)
