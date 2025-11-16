from datetime import datetime
from airflow import DAG
from airflow.providers.cncf.kubernetes.operators.pod import KubernetesPodOperator
from kubernetes import client as k8s

with DAG(
        dag_id="drift_checker_dag",
        description="Detect drift via PSI and trigger retraining",
        start_date=datetime(2025, 10, 27),
        schedule="0 * * * *",  # mỗi 60 phút
        catchup=False,
        max_active_runs=1,
        tags=["drift", "psi"],
) as dag:

    volume_script = k8s.V1Volume(
        name="drift-checker-script",
        config_map=k8s.V1ConfigMapVolumeSource(name="drift-checker-script")
    )
    mount_script = k8s.V1VolumeMount(
        name="drift-checker-script",
        mount_path="/app",
        read_only=True
    )

    drift = KubernetesPodOperator(
        task_id="drift_checker",
        namespace="airflow",
        name="drift-checker",
        image="python:3.11-slim",
        cmds=["/bin/sh", "-lc"],
        arguments=[
            "pip install pandas pyarrow numpy requests s3fs && "
            "python /app/drift_checker.py"
        ],
        env_vars={
            "BRONZE_PREFIX": "bronze/metrics",
            "BASELINE_PATH": "baseline/stats.parquet",
            "S3_BUCKET": "datalake",
            "S3_ENDPOINT": "http://minio.minio.svc.cluster.local:9000",
            "LOOKBACK_HOURS": "3",
            "PSI_THRESHOLD": "0.25",
            "AIRFLOW_URL": "http://airflow-api-server.airflow.svc.cluster.local:8080",
            "AIRFLOW_USERNAME": "admin",
            "AIRFLOW_PASSWORD": "admin",
            "TRAIN_DAG_ID": "train_lstm_dag",
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
