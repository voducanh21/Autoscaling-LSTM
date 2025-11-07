from datetime import datetime
from airflow import DAG
from airflow.providers.cncf.kubernetes.operators.pod import KubernetesPodOperator
from kubernetes import client as k8s

with DAG(
        dag_id="bronze_metrics_dag",
        description="Bronze layer: dump raw metrics from Prometheus → MinIO (S3)",
        start_date=datetime(2025, 10, 20),
        schedule="*/5 * * * *",
        catchup=False,
        max_active_runs=1,
        tags=["bronze", "metrics"],
) as dag:

    volume_script = k8s.V1Volume(
        name="bronze-metrics-script",
        config_map=k8s.V1ConfigMapVolumeSource(name="bronze-metrics-script")
    )
    mount_script = k8s.V1VolumeMount(
        name="bronze-metrics-script",
        mount_path="/app",
        read_only=True
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
            "S3_ENDPOINT": "https://minio.voducanh.id.vn",
            "TIMEZONE": "Asia/Ho_Chi_Minh",
            "AWS_S3_ADDRESSING_STYLE": "path",
        },
        env_from=[
            k8s.V1EnvFromSource(secret_ref=k8s.V1SecretEnvSource(name="minio-cred"))
        ],
        volumes=[volume_script],
        volume_mounts=[mount_script],
        affinity={
            "podAntiAffinity": {
                "preferredDuringSchedulingIgnoredDuringExecution": [
                    {
                        "weight": 100,
                        "podAffinityTerm": {
                            "labelSelector": {
                                "matchExpressions": [
                                    {"key": "app", "operator": "In", "values": ["airflow"]}
                                ]
                            },
                            "topologyKey": "kubernetes.io/hostname"
                        }
                    }
                ]
            }
        },
        is_delete_operator_pod=True,
        get_logs=True,
        in_cluster=True,
    )
