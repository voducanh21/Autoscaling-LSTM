# dags/drift_psi_dag.py
from datetime import datetime
import pendulum
from airflow import DAG
from airflow.providers.cncf.kubernetes.operators.pod import KubernetesPodOperator
from kubernetes import client as k8s

VN_TZ = pendulum.timezone("Asia/Ho_Chi_Minh")

with DAG(
        dag_id="drift_psi",
        start_date=pendulum.datetime(2025, 10, 20, tz=VN_TZ),
        schedule="0 2 * * 1",   # weekly: 02:00 mỗi Thứ 2
        catchup=False,
        max_active_runs=1,
        tags=["drift", "psi"],
) as dag:
    psi = KubernetesPodOperator(
        task_id="compute_psi",
        name="drift-psi",
        namespace="airflow",
        image="python:3.11-slim",
        cmds=["/bin/sh", "-lc"],
        arguments=[
            "pip install -q numpy pandas pyarrow fsspec s3fs tzdata && "
            "python /app/compute_psi.py"
        ],
        env_vars={
            "S3_BUCKET": "datalake",
            "S3_ENDPOINT": "https://minio.voducanh.id.vn",
            "TIMEZONE": "Asia/Ho_Chi_Minh",
            "AWS_S3_ADDRESSING_STYLE": "path",
            "MODEL_NAME": "cnn_lstm_forecast",
            "REF_PREFIX": "drift/reference",
            "REF_TAG": "",
            "CURRENT_PREFIX": "drift/current/metrics",
            "PSI_PREFIX": "drift/psi",
            "PSI_BINS": "10",
            "PSI_EPS": "1e-6",
            "MAX_SAMPLES_PER_SERVICE": "200000",
            "CURRENT_DAYS": "7",
            "CURRENT_DATE_FRACTION": "0.0",
            "CURRENT_PICK_MODE": "last",
            "CURRENT_SEED": "42",
            "SAVE_LATEST_POINTER": "true",
            # "PSI_THRESHOLD": "0.2",
        },
        env_from=[
            k8s.V1EnvFromSource(secret_ref=k8s.V1SecretEnvSource(name="minio-cred"))
        ],
        volumes=[
            k8s.V1Volume(
                name="drift-psi-script",
                config_map=k8s.V1ConfigMapVolumeSource(name="drift-psi-script"),
            )
        ],
        volume_mounts=[
            k8s.V1VolumeMount(name="drift-psi-script", mount_path="/app", read_only=True)
        ],
        labels={"airflow-task": "drift-psi"},
        is_delete_operator_pod=True,
        get_logs=True,
        in_cluster=True,
    )
