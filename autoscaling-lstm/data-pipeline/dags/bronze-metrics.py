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

    bronze = KubernetesPodOperator(
        task_id="bronze_metrics",
        name="bronze-metrics",
        namespace="ops",
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
            "S3_ENDPOINT": "http://minio.infra.svc.cluster.local:9000",
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
        get_logs=True,
        # 🔧 các flag quan trọng để giữ pod và hiển thị log
        is_delete_operator_pod=False,
        in_cluster=True,
        config_file=None,
        service_account_name="airflow-runner",
    )

    bronze
