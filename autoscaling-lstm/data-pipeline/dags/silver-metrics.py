from datetime import datetime
from airflow import DAG
from airflow.providers.cncf.kubernetes.operators.pod import KubernetesPodOperator
from kubernetes import client as k8s

SILVER_SCRIPT = r"""
import os, sys
import pandas as pd
import s3fs, pyarrow.parquet as pq, pyarrow as pa

BUCKET      = os.getenv('S3_BUCKET', 'datalake')
BRONZE_PATH = os.getenv('BRONZE_PREFIX', 'bronze/metrics')
SILVER_PATH = os.getenv('SILVER_PREFIX', 'silver/metrics')
S3_ENDPOINT = os.getenv('S3_ENDPOINT')

fs = s3fs.S3FileSystem(client_kwargs={'endpoint_url': S3_ENDPOINT})

def main():
    try:
        files = fs.glob(f'{BUCKET}/{BRONZE_PATH}/**/*.parquet')
        if not files:
            print('[WARN] no bronze data found')
            return

        dfs = []
        for f in files:
            try:
                table = pq.read_table(f's3://{f}', filesystem=fs)
                schema = table.schema
                for name in schema.names:
                    field = schema.field(name)
                    if pa.types.is_dictionary(field.type):
                        arr = table[name].combine_chunks().dictionary_decode()
                        table = table.set_column(schema.get_field_index(name), name, arr)
                d = table.to_pandas()

                if 'service' in d.columns:
                    d['service'] = d['service'].astype(str)
                if 'ts' in d.columns:
                    d['ts'] = pd.to_datetime(d['ts'], errors='coerce').astype(str)
                for col in ['rps_1m','latency_p95_ms','cpu_cores_1m','mem_bytes']:
                    if col in d.columns:
                        d[col] = pd.to_numeric(d[col], errors='coerce')

                dfs.append(d)
            except Exception as e:
                print(f'[WARN] skip {f} ({e})', file=sys.stderr)

        if not dfs:
            print('[WARN] no valid parquet files')
            return

        df = pd.concat(dfs, ignore_index=True)
        df = df.dropna(subset=['service', 'ts']).sort_values('ts')

        out_path = f's3://{BUCKET}/{SILVER_PATH}/silver-{pd.Timestamp.now().strftime("%Y%m%d%H%M%S")}.parquet'
        df.to_parquet(
            out_path,
            index=False,
            engine='pyarrow',
            storage_options={'client_kwargs': {'endpoint_url': S3_ENDPOINT}},
        )
        print(f'[OK] wrote {out_path}')
    except Exception as e:
        print(f'[ERROR] {e}', file=sys.stderr)
        sys.exit(1)

if __name__ == '__main__':
    main()
"""

with DAG(
        dag_id="silver_metrics_dag",
        description="Silver layer: transform bronze metrics → silver",
        schedule=None,
        start_date=datetime(2025, 9, 1),
        catchup=False,
        tags=["silver", "metrics"],
) as dag:

    silver = KubernetesPodOperator(
        task_id="silver_metrics",
        name="silver-metrics",
        namespace="airflow",
        image="python:3.11-slim",
        cmds=["/bin/sh", "-lc"],
        arguments=[
            "pip install -q pandas pyarrow fsspec s3fs tzdata && "
            f"python - <<'PYCODE'\n{SILVER_SCRIPT}\nPYCODE"
        ],
        env_vars={
            "S3_BUCKET": "datalake",
            "BRONZE_PREFIX": "bronze/metrics",
            "SILVER_PREFIX": "silver/metrics",
            "S3_ENDPOINT": "http://minio.minio.svc.cluster.local:9000",
            "TIMEZONE": "Asia/Ho_Chi_Minh",
        },
        env_from=[
            k8s.V1EnvFromSource(secret_ref=k8s.V1SecretEnvSource(name="minio-cred"))
        ],
        get_logs=True,
        is_delete_operator_pod=True,
        in_cluster=True,
    )
