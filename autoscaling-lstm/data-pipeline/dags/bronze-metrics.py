from datetime import datetime
from airflow import DAG
from airflow.providers.cncf.kubernetes.operators.pod import KubernetesPodOperator

with DAG(
        dag_id="bronze_metrics_dag",
        description="Bronze layer: dump raw metrics from Prometheus → MinIO (S3)",
        start_date=datetime(2025, 9, 1),
        schedule=None,  # tắt tự động chạy
        catchup=False,
        tags=["bronze", "metrics"],
) as dag:

    bronze = KubernetesPodOperator(
        task_id="bronze_metrics",
        name="bronze-metrics",
        namespace="airflow",
        image="python:3.11-slim",
        image_pull_policy="IfNotPresent",
        cmds=["/bin/sh", "-lc"],
        arguments=[
            # cài dependencies và chạy script từ ConfigMap bronze-metrics-script
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
        # lấy credentials từ secret minio-cred
        secrets=[{"secret_name": "minio-cred"}],
        # mount ConfigMap đúng tên mà CronJob đã dùng
        volume_mounts=[
            {
                "name": "bronze-metrics-script",
                "mount_path": "/app",
                "read_only": True,
            }
        ],
        volumes=[
            {
                "name": "bronze-metrics-script",
                "config_map": {"name": "bronze-metrics-script"},
            }
        ],
        # giữ pod sạch sau khi chạy
        is_delete_operator_pod=True,
        get_logs=True,
        in_cluster=True,
    )
