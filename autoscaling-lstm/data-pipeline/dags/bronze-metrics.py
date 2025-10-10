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
        dag_id="bronze_metrics_dag",
        description="Bronze layer: dump raw metrics from Prometheus → MinIO (S3)",
        schedule="*/5 * * * *",
        start_date=datetime(2025, 9, 1),
        catchup=False,
        default_args=default_args,
        tags=["bronze", "metrics"],
) as dag:

    # Mount scripts từ ConfigMap chứa metrics_dumper.py
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

    # ✅ Thêm security_context để container chạy bằng user có quyền ghi logs
    security_ctx = k8s.V1SecurityContext(
        run_as_user=0,              # chạy bằng root user → tránh lỗi Permission denied
        run_as_group=0,
        allow_privilege_escalation=True
    )

    bronze = KubernetesPodOperator(
        task_id="bronze_metrics",
        name="bronze-metrics",
        namespace="airflow",
        image="python:3.11-slim",
        image_pull_policy="IfNotPresent",
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
        env_from=[
            k8s.V1EnvFromSource(
                secret_ref=k8s.V1SecretEnvSource(name="minio-cred")
            )
        ],
        volumes=[volume_scripts],
        volume_mounts=[mount_scripts],
        container_resources=pod_resources,
        security_context=security_ctx,   # 👈 Thêm dòng này
        get_logs=True,
        is_delete_operator_pod=False,
        in_cluster=True,
        config_file=None,
        service_account_name="airflow-runner",
    )

    bronze
