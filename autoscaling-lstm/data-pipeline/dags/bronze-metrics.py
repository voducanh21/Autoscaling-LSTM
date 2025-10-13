from datetime import datetime
from airflow import DAG
from airflow.providers.cncf.kubernetes.operators.pod import KubernetesPodOperator

with DAG(
        dag_id="bronze_metrics_dag",
        start_date=datetime(2025, 9, 1),
        schedule=None,
        catchup=False,
        tags=["bronze", "metrics"],
) as dag:

    bronze = KubernetesPodOperator(
        task_id="bronze_metrics",
        name="bronze-metrics",
        namespace="airflow",
        image="python:3.11-slim",
        cmds=["/bin/sh", "-lc"],
        arguments=[
            "pip install -q pandas pyarrow requests fsspec s3fs tzdata && "
            "python /app/metrics_dumper.py"
        ],
        env_vars={
            "PROM_URL": "http://kube-prometheus-kube-prome-prometheus.monitoring.svc.cluster.local:9090",
            "S3_BUCKET": "datalake",
            "S3_PREFIX": "bronze/metrics",
            "S3_ENDPOINT": "http://minio.minio.svc.cluster.local:9000",
            "TIMEZONE": "Asia/Ho_Chi_Minh",
        },
        secrets=[{"secret_name": "minio-cred"}],  # dùng cách mới thay vì env_from
        volume_mounts=[
            {
                "name": "pipeline-scripts",
                "mount_path": "/app",
                "read_only": True,
            }
        ],
        volumes=[
            {
                "name": "pipeline-scripts",
                "config_map": {"name": "pipeline-scripts"},
            }
        ],
        is_delete_operator_pod=True,
        get_logs=True,
        in_cluster=True,
    )
