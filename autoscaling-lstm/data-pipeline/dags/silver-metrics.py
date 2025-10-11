from datetime import datetime, timedelta
from airflow import DAG
from airflow.providers.cncf.kubernetes.operators.pod import KubernetesPodOperator

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
    # 👉 import kubernetes client *bên trong* để tránh delay khi parse
    from kubernetes import client as k8s

    # Mount scripts từ ConfigMap chứa silver_builder.py
    volume_scripts = k8s.V1Volume(
        name="pipeline-scripts",
        config_map=k8s.V1ConfigMapVolumeSource(name="pipeline-scripts"),
    )
    mount_scripts = k8s.V1VolumeMount(
        name="pipeline-scripts", mount_path="/app", read_only=True
    )

    # Mount PVC logs để đồng bộ quyền ghi log
    volume_logs = k8s.V1Volume(
        name="logs",
        persistent_volume_claim=k8s.V1PersistentVolumeClaimVolumeSource(
            claim_name="airflow-logs"
        ),
    )
    mount_logs = k8s.V1VolumeMount(name="logs", mount_path="/opt/airflow/logs")

    # Resource requests/limits
    pod_resources = k8s.V1ResourceRequirements(
        requests={"cpu": "100m", "memory": "128Mi"},
        limits={"cpu": "500m", "memory": "512Mi"},
    )

    # Chạy bằng root để đảm bảo quyền ghi log
    security_ctx = k8s.V1SecurityContext(
        run_as_user=50000,
        run_as_group=50000,
        allow_privilege_escalation=False,
    )

    # KubernetesPodOperator chạy script Silver
    silver = KubernetesPodOperator(
        task_id="silver_metrics",
        name="silver-metrics",
        namespace="airflow",
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
            k8s.V1EnvFromSource(secret_ref=k8s.V1SecretEnvSource(name="minio-cred"))
        ],
        volumes=[volume_scripts, volume_logs],
        volume_mounts=[mount_scripts, mount_logs],
        container_resources=pod_resources,
        security_context=security_ctx,
        get_logs=True,
        is_delete_operator_pod=False,
        in_cluster=True,
        config_file=None,
    )

    silver
