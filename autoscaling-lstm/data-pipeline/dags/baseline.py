from datetime import datetime
from airflow import DAG
from airflow.providers.cncf.kubernetes.operators.pod import KubernetesPodOperator
from kubernetes import client as k8s

with DAG(
        dag_id="baseline_stats_dag",
        description="Build PSI baseline stats from Bronze",
        start_date=datetime(2025, 10, 27),
        schedule="0 0 */7 * *",  # mỗi 7 ngày
        catchup=False,
        max_active_runs=1,
        tags=["psi", "baseline"],
) as dag:

    volume_script = k8s.V1Volume(
        name="baseline-stats-script",
        config_map=k8s.V1ConfigMapVolumeSource(name="baseline-stats-script")
    )
    mount_script = k8s.V1VolumeMount(
        name="baseline-stats-script",
        mount_path="/app",
        read_only=True
    )

    build_baseline = KubernetesPodOperator(
        task_id="build_baseline",
        namespace="airflow",
        name="build-baseline",
        image="python:3.11-slim",
        cmds=["/bin/sh", "-lc"],
        arguments=[
            "pip install pandas pyarrow s3fs && "
            "python /app/baseline_stats.py"
        ],
        env_vars={
            "BRONZE_PREFIX": "bronze/metrics",
            "S3_BUCKET": "datalake",
            "BASELINE_PATH": "baseline/stats.parquet",
            "S3_ENDPOINT": "http://minio.minio.svc.cluster.local:9000",
        },
        env_from=[
            k8s.V1EnvFromSource(secret_ref=k8s.V1SecretEnvSource(name="minio-cred"))
        ],
        volumes=[volume_script],
        volume_mounts=[mount_script],
        node_selector={"kubernetes.io/hostname": "k3n-m03"},
        is_delete_operator_pod=True,
        get_logs=True,
    )
