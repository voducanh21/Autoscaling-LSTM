from datetime import datetime
import pendulum

from airflow import DAG
from airflow.providers.cncf.kubernetes.operators.pod import KubernetesPodOperator
from kubernetes import client as k8s

TZ = pendulum.timezone("Asia/Ho_Chi_Minh")

with DAG(
        dag_id="train_lstm_dag",
        description="Train LSTM then register/promote model (equivalent to train-lstm-cronjob)",
        start_date=pendulum.datetime(2025, 10, 27, tz=TZ),
        schedule="0 */6 * * *",
        catchup=False,
        max_active_runs=1,
        tags=["train", "lstm", "mlflow"],
) as dag:
    # =========================
    # Volumes (ConfigMaps)
    # =========================
    volume_train = k8s.V1Volume(
        name="train-lstm-script",
        config_map=k8s.V1ConfigMapVolumeSource(name="train-lstm-script"),
    )
    mount_train = k8s.V1VolumeMount(
        name="train-lstm-script",
        mount_path="/app",   # same as CronJob: python /app/train_lstm.py
        read_only=True,
    )

    volume_register = k8s.V1Volume(
        name="register-model-script",
        config_map=k8s.V1ConfigMapVolumeSource(name="register-model-script"),
    )
    mount_register = k8s.V1VolumeMount(
        name="register-model-script",
        mount_path="/register",  # same as CronJob: python /register/register_model.py
        read_only=True,
    )

    # =========================
    # Single pod = equivalent to CronJob container
    # =========================
    train_then_register = KubernetesPodOperator(
        task_id="train_then_register",
        name="train-lstm",
        namespace="cronjob",  # same namespace as CronJob
        image="ducanhvo/train-lstm:latest",
        image_pull_policy="Always",
        cmds=["/bin/sh", "-c"],
        arguments=[
            r"""
set -e
echo "[INFO] Start training LSTM..."
python /app/train_lstm.py
echo "[INFO] Training done. Running model registry..."
python /register/register_model.py
echo "[INFO] Registry done."
"""
        ],
        env_vars={
            # --- S3 / MinIO ---
            "S3_ENDPOINT": "https://minio.voducanh.id.vn",
            "MLFLOW_S3_ENDPOINT_URL": "https://minio.voducanh.id.vn",
            "MLFLOW_ARTIFACT_ROOT": "s3://datalake/mlflow",
            "MLFLOW_ARTIFACTS_DESTINATION": "s3://datalake/mlflow",
            "S3_BUCKET": "datalake",
            "SILVER_PREFIX": "silver/metrics",
            "AWS_S3_ADDRESSING_STYLE": "path",

            # --- MLflow ---
            "MLFLOW_TRACKING_URI": "http://mlflow.mlflow.svc.cluster.local:5000",

            # --- Training Params ---
            "WINDOW_SIZE": "10",
            "EPOCHS": "20",
            "BATCH_SIZE": "128",

            # --- Split 80/10/10 ---
            "TRAIN_FRAC": "0.80",
            "VAL_FRAC": "0.10",
            "EXTRA_EMBARGO_MINUTES": "0",

            # --- FULL DATA MODE ---
            "DATE_FRACTION": "1.0",
            "DATE_PICK_MODE": "all",
            "DATE_SEED": "42",

            # --- Model / Experiment ---
            "MODEL_NAME": "lstm_forecast",
            "EXPERIMENT_NAME": "lstm_forecast",

            # --- Promotion knobs (optional / keep same as CronJob) ---
            "REQUIRE_BOTH_RPS_AND_CPU": "true",
            "PROMOTION_EPS": "0.0",
            "REQUIRE_BEAT_BASELINE_TEST_WAPE": "false",
        },
        env_from=[
            k8s.V1EnvFromSource(
                secret_ref=k8s.V1SecretEnvSource(name="minio-cred")
            )
        ],
        volumes=[volume_train, volume_register],
        volume_mounts=[mount_train, mount_register],
        node_selector={"kubernetes.io/hostname": "k3n-m03"},
        service_account_name="register-model-sa",  # same as CronJob
        in_cluster=True,
        get_logs=True,
        is_delete_operator_pod=True,
    )

    train_then_register
