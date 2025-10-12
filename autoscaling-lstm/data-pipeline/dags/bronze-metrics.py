from datetime import datetime, timedelta
from airflow import DAG
from airflow.providers.cncf.kubernetes.operators.pod import KubernetesPodOperator


default_args = {
    "owner": "autoscaling",
    "retries": 1,
    "retry_delay": timedelta(minutes=5),
}

with DAG(
        dag_id="bronze_metrics_dag",
        description="Bronze layer: dump raw metrics from Prometheus → MinIO (S3)",
        start_date=datetime(2025, 9, 1),
        catchup=False,
        default_args=default_args,
        tags=["bronze", "metrics"],
) as dag:
    from kubernetes import client as k8s

    # Mount ConfigMap chứa metrics_dumper.py
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

    security_ctx = k8s.V1SecurityContext(
        run_as_user=0,
        run_as_group=0,
        allow_privilege_escalation=True,
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
            # Prometheus endpoint
            "PROM_URL": "http://kube-prometheus-kube-prome-prometheus.monitoring.svc.cluster.local:9090",
            # MinIO (S3)
            "S3_BUCKET": "datalake",
            "S3_PREFIX": "bronze/metrics",
            "S3_ENDPOINT": "http://minio.minio.svc.cluster.local:9000",
            "TIMEZONE": "Asia/Ho_Chi_Minh",
            # enable boto3 / s3fs debug logging (optional)
            "AWS_REGION": "us-east-1",
            "AWS_DEFAULT_REGION": "us-east-1",
        },
        env_from=[
            k8s.V1EnvFromSource(secret_ref=k8s.V1SecretEnvSource(name="minio-cred"))
        ],
        volumes=[volume_scripts],
        volume_mounts=[mount_scripts],
        container_resources=pod_resources,
        security_context=security_ctx,
        # Lấy log trực tiếp về Airflow rồi đẩy sang MinIO (theo config Airflow)
        get_logs=True,
        is_delete_operator_pod=True,
        in_cluster=True,
        config_file=None,
    )

    bronze
