from datetime import datetime
from airflow import DAG
from airflow.providers.cncf.kubernetes.operators.pod import KubernetesPodOperator
from kubernetes import client as k8s

with DAG(
        dag_id="silver_metrics_dag",
        start_date=datetime(2025, 10, 18),
        schedule="*/10 * * * *",
        catchup=False,
        max_active_runs=1,
        tags=["silver","metrics"],
) as dag:
    silver = KubernetesPodOperator(
        task_id="silver_metrics",
        name="silver-metrics",
        namespace="airflow",
        image="python:3.11-slim",
        cmds=["/bin/sh","-lc"],
        arguments=[
            "pip install -q pandas pyarrow fsspec s3fs tzdata && "
            "python /app/silver_builder.py"
        ],
        env_vars={
            "S3_BUCKET":"datalake",
            "BRONZE_PREFIX":"bronze/metrics",
            "SILVER_PREFIX":"silver/metrics",
            "S3_ENDPOINT":"http://minio.minio.svc.cluster.local:9000",
            "TIMEZONE":"Asia/Ho_Chi_Minh",
            "PAST_HOURS":"48",
            "ROLL_WINDOWS":"[5,15]",
            "LAG_MINUTES":"[1,5,10]",
        },
        env_from=[k8s.V1EnvFromSource(secret_ref=k8s.V1SecretEnvSource(name="minio-cred"))],
        volumes=[k8s.V1Volume(
            name="silver-scripts",
            config_map=k8s.V1ConfigMapVolumeSource(name="silver-metrics-script"),
        )],
        volume_mounts=[k8s.V1VolumeMount(
            name="silver-scripts", mount_path="/app", read_only=True
        )],
        get_logs=True,
        is_delete_operator_pod=True,
        in_cluster=True,
    )
