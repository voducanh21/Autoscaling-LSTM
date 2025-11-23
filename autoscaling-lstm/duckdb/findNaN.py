import s3fs, pyarrow.parquet as pq

fs = s3fs.S3FileSystem(
    key="H7TLSw9YlDtC88KDjzMN",
    secret="6thNYmyTFH1HZdl1DIw4mSx8Z6Eu8p2lIg50yizL",
    client_kwargs={"endpoint_url": "https://minio.voducanh.id.vn"},
)

path = "datalake/silver/metrics/date=2025-11-23/service=authentication-service/part-1763913049.parquet"

with fs.open(path, "rb") as f:
    df = pq.read_table(f).to_pandas()

print(df[["cpu_cores_1m", "cpu_norm"]])
