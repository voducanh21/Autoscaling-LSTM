from datetime import datetime, timedelta
from airflow import DAG
from airflow.providers.cncf.kubernetes.operators.pod import KubernetesPodOperator
from kubernetes import client as k8s

default_args = {
    "owner": "autoscaling",
    "retries": 1,
    "retry_delay": timedelta(minutes=5),
}

with DAG(
        dag_id="silver_metrics_dag",
        description="Silver layer: transform bronze metrics → silver (cleaned, structured)",
        schedule="*/10 * * * *",
        start_date=datetime(2025, 9, 1),
        catchup=False,
        default_args=default_args,
        tags=["silver", "metrics"],
) as dag:

    # Mount scripts từ ConfigMap
    volume_scripts = k8s.V1Volume(
        name="pipeline-scripts",
        config_map=k8s.V1ConfigMapVolumeSource(name="pipeline-scripts"),
    )
    mount_scripts = k8s.V1VolumeMount(
        name="pipeline-scripts", mount_path="/app", read_only=True
    )

    pod_resources = k8s.V1ResourceRequirements(
        requests={"cpu": "100m", "memory": "128Mi"},
        limits={"cpu": "500m", "memory": "512Mi"},
    )

    # ✅ Giống bronze: chạy với quyền root để tránh lỗi ghi logs
    security_ctx = k8s.V1SecurityContext(
        run_as_user=0,
        run_as_group=0
    )

    silver = KubernetesPodOperator(
        task_id="silver_metrics",
        name="silver-metrics",
        namespace="airflow",   # ✅ chạy trong namespace airflow
        image="python:3.11-slim",
        image_pull_policy="IfNotPresent",
        cmds=["/bin/sh", "-lc"],
        arguments=[
            "pip install -q pandas pyarrow fsspec s3fs tzdata && "
            "python /app/silver_builder.py"
        ],
        env_vars={
            "S3_BUCKET": "datalake",
            "BRONZE_PREFIX": "bronze/metrics",
            "SILVER_PREFIX": "silver/metrics",
            "S3_ENDPOINT": "http://minio.minio.svc.cluster.local:9000",
            "TIMEZONE": "Asia/Ho_Chi_Minh",
        },
        env_from=[
            k8s.V1EnvFromSource(
                secret_ref=k8s.V1SecretEnvSource(name="minio-cred")
            )
        ],
        volumes=[volume_scripts],
        volume_mounts=[mount_scripts],
        container_resources=pod_resources,
        security_context=security_ctx,    # ✅ thêm dòng này
        get_logs=True,
        is_delete_operator_pod=False,
        in_cluster=True,
        config_file=None,
        # ❌ bỏ service_account_name để dùng SA mặc định của airflow-scheduler
    )

    silver
