from datetime import datetime
from airflow import DAG
from airflow.providers.cncf.kubernetes.operators.pod import KubernetesPodOperator
from kubernetes import client as k8s

with DAG(
        dag_id="gold_metrics_dag",
        description="Gold layer: aggregate silver → gold",
        schedule=None,
        start_date=datetime(2025, 9, 1),
        catchup=False,
        tags=["gold", "metrics"],
) as dag:

    gold = KubernetesPodOperator(
        task_id="gold_metrics",
        name="gold-metrics",
        namespace="airflow",
        image="python:3.11-slim",
        cmds=["/bin/sh", "-lc"],
        arguments=[
            "pip install -q pandas pyarrow fsspec s3fs tzdata && "
            "python /app/gold_aggregator.py"
        ],
        env_vars={
            "S3_BUCKET": "datalake",
            "SILVER_PREFIX": "silver/metrics",
            "GOLD_PREFIX": "gold/metrics",
            "S3_ENDPOINT": "http://minio.minio.svc.cluster.local:9000",
            "TIMEZONE": "Asia/Ho_Chi_Minh",
        },
        env_from=[
            k8s.V1EnvFromSource(
                secret_ref=k8s.V1SecretEnvSource(name="minio-cred")
            )
        ],
        volumes=[
            k8s.V1Volume(
                name="pipeline-scripts",
                config_map=k8s.V1ConfigMapVolumeSource(name="pipeline-scripts"),
            )
        ],
        volume_mounts=[
            k8s.V1VolumeMount(
                name="pipeline-scripts",
                mount_path="/app",
                read_only=True,
            )
        ],
        get_logs=True,
        is_delete_operator_pod=True,
        in_cluster=True,
    )
