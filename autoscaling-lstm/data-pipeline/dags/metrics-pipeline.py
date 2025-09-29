from datetime import datetime, timedelta
from airflow import DAG
from airflow.providers.cncf.kubernetes.operators.pod import KubernetesPodOperator
from kubernetes.client import models as k8s

default_args = {
    "owner": "autoscaling",
    "retries": 1,
    "retry_delay": timedelta(minutes=5),
}

with DAG(
        dag_id="metrics_pipeline",
        description="Bronze → Silver metrics pipeline",
        schedule="*/5 * * * *",     # chạy mỗi 5 phút
        start_date=datetime(2025, 9, 1),
        catchup=False,
        default_args=default_args,
        tags=["bronze","silver"],
) as dag:

    # Mount scripts từ ConfigMap 'pipeline-scripts' vào /app
    volume_scripts = k8s.V1Volume(
        name="pipeline-scripts",
        config_map=k8s.V1ConfigMapVolumeSource(name="pipeline-scripts")
    )
    mount_scripts = k8s.V1VolumeMount(
        name="pipeline-scripts", mount_path="/app", read_only=True
    )

    bronze = KubernetesPodOperator(
        task_id="bronze_metrics",
        name="bronze-metrics",
        namespace="ops",
        image="python:3.11-slim",
        image_pull_policy="IfNotPresent",
        cmds=["/bin/sh","-lc"],
        arguments=[
            # cài tối thiểu các package cần thiết
            "pip install -q pandas pyarrow requests fsspec s3fs tzdata && "
            "python /app/metrics_dumper.py"
        ],
        env_vars={
            # THAM SỐ HÓA – chỉnh theo cụm của bạn
            "PROM_URL": "http://kube-prometheus-kube-prome-prometheus.monitoring.svc.cluster.local:9090",
            "METRICS_NS": "ops",
            "S3_BUCKET": "datalake",
            "S3_PREFIX": "bronze/metrics",
            "S3_ENDPOINT": "http://minio.ops.svc.cluster.local:9000",
            "TIMEZONE": "Asia/Ho_Chi_Minh",
        },
        # Lấy key/secret MinIO từ Secret (tạo ở ns ops: 'minio-cred')
        env_from=[k8s.V1EnvFromSource(secret_ref=k8s.V1SecretEnvSource(name="minio-cred"))],
        volumes=[volume_scripts],
        volume_mounts=[mount_scripts],
        resources={
            "request_memory": "128Mi",
            "request_cpu": "100m",
            "limit_memory": "512Mi",
            "limit_cpu": "500m",
        },
        get_logs=True,
        is_delete_operator_pod=True,
        service_account_name="airflow-runner",
    )

    silver = KubernetesPodOperator(
        task_id="silver_metrics",
        name="silver-metrics",
        namespace="ops",
        image="python:3.11-slim",
        image_pull_policy="IfNotPresent",
        cmds=["/bin/sh","-lc"],
        arguments=[
            "pip install -q pandas pyarrow numpy fsspec s3fs tzdata && "
            "python /app/silver_builder.py"
        ],
        env_vars={
            "S3_BUCKET": "datalake",
            "BRONZE_PREFIX": "bronze/metrics",
            "SILVER_PREFIX": "silver/metrics",
            "S3_ENDPOINT": "http://minio.ops.svc.cluster.local:9000",
            "TIMEZONE": "Asia/Ho_Chi_Minh",
        },
        env_from=[k8s.V1EnvFromSource(secret_ref=k8s.V1SecretEnvSource(name="minio-cred"))],
        volumes=[volume_scripts],
        volume_mounts=[mount_scripts],
        resources=k8s.V1ResourceRequirements(
            requests={"cpu":"100m","memory":"128Mi"},
            limits={"cpu":"500m","memory":"512Mi"},
        ),
        get_logs=True,
        is_delete_operator_pod=True,
        service_account_name="airflow-runner",
    )

    bronze >> silver