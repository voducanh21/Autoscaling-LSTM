from datetime import datetime
from airflow import DAG
from airflow.providers.cncf.kubernetes.operators.pod import KubernetesPodOperator
from kubernetes import client as k8s

with DAG(
        dag_id="drift_checker_dag",
        description="Detect drift via PSI and trigger retraining",
        start_date=datetime(2025, 10, 27),
        schedule="0 * * * *",   # chạy mỗi 60 phút
        catchup=False,
        max_active_runs=1,
        tags=["drift", "psi"],
) as dag:

    # ---------- Mount ConfigMap ----------
    volume_script = k8s.V1Volume(
        name="drift-checker-script",
        config_map=k8s.V1ConfigMapVolumeSource(name="drift-checker-script")
    )
    mount_script = k8s.V1VolumeMount(
        name="drift-checker-script",
        mount_path="/app",
        read_only=True
    )

    # ---------- Drift checker Pod ----------
    drift = KubernetesPodOperator(
        task_id="drift_checker",
        name="drift-checker",
        namespace="airflow",
        image="python:3.11-slim",
        image_pull_policy="IfNotPresent",
        cmds=["/bin/sh", "-lc"],
        arguments=[
            "pip install -q pandas pyarrow numpy requests s3fs && "
            "python /app/drift_checker.py"
        ],
        env_vars={
            # ==== S3 Config ====
            "S3_BUCKET": "datalake",
            "S3_ENDPOINT": "https://minio.voducanh.id.vn",   # dùng HTTPS (Cloudflare tunnel)
            "BRONZE_PREFIX": "bronze/metrics",

            # ==== Correct baseline path ====
            "BASELINE_PATH": "baseline/metrics/baseline_latest.parquet",

            # ==== PSI Config ====
            "LOOKBACK_HOURS": "1",       # mỗi 1 giờ đọc lại dữ liệu 1 giờ gần nhất
            "PSI_THRESHOLD": "0.25",

            # ==== Airflow API ====
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
        in_cluster=True,
    )
