# dags/drift_psi_dag.py
from datetime import datetime
from airflow import DAG
from airflow.providers.cncf.kubernetes.operators.pod import KubernetesPodOperator
from kubernetes import client as k8s

with DAG(
        dag_id="drift_psi",
        start_date=datetime(2025, 10, 20),
        schedule=None,          # webhook trigger
        catchup=False,
        max_active_runs=1,
        tags=["drift", "psi"],
) as dag:
    psi = KubernetesPodOperator(
        task_id="compute_psi",
        name="drift-psi",
        namespace="airflow",

        # nên dùng image nhẹ + cài deps giống silver
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

            # Model / reference / current / output
            "MODEL_NAME": "cnn_lstm_forecast",
            "REF_PREFIX": "drift/reference",
            "REF_TAG": "",  # để rỗng = dùng latest.json
            "CURRENT_PREFIX": "drift/current/metrics",
            "PSI_PREFIX": "drift/psi",

            # PSI knobs
            "PSI_BINS": "10",
            "PSI_EPS": "1e-6",
            "MAX_SAMPLES_PER_SERVICE": "200000",

            # current selection
            "CURRENT_DAYS": "7",
            "CURRENT_DATE_FRACTION": "0.0",
            "CURRENT_PICK_MODE": "last",
            "CURRENT_SEED": "42",

            # save pointer
            "SAVE_LATEST_POINTER": "true",

            # gating (optional) -> nếu set thì exit 2 khi vượt ngưỡng
            # "PSI_THRESHOLD": "0.2",
        },

        # MinIO credentials (namespace airflow) -> phải có AWS_ACCESS_KEY_ID/AWS_SECRET_ACCESS_KEY
        env_from=[
            k8s.V1EnvFromSource(secret_ref=k8s.V1SecretEnvSource(name="minio-cred"))
        ],

        # Mount script từ ConfigMap
        # Lưu ý: ConfigMap drift-psi-script phải nằm trong namespace airflow (không phải cronjob)
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
