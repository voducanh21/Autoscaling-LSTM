# ================================
# DAG: train_lstm_forecast_dag.py
# (UNCHANGED logic; already runs December-only via TRAIN_MONTH/TRAIN_YEAR)
# ================================
from datetime import datetime
from airflow import DAG
from airflow.operators.python import ShortCircuitOperator
from airflow.providers.cncf.kubernetes.operators.pod import KubernetesPodOperator
from kubernetes import client as k8s


def _should_run_reference(ti) -> bool:
    x = ti.xcom_pull(task_ids="register_model")
    try:
        return bool((x or {}).get("promoted", False))
    except Exception:
        return False


with DAG(
        dag_id="train_lstm_forecast_dag",
        start_date=datetime(2025, 10, 20),
        schedule=None,
        catchup=False,
        max_active_runs=1,
        tags=["mlflow", "train", "lstm"],
) as dag:

    train = KubernetesPodOperator(
        task_id="train_model",
        name="train-lstm-forecast",
        namespace="airflow",
        image="ducanhvo/train-lstm:latest",
        image_pull_policy="Always",
        cmds=["/bin/sh", "-lc"],
        arguments=[
            "set -e; "
            "echo '[INFO] Start training LSTM Forecast...'; "
            "python /app/train/train_lstm.py; "
            "echo '[INFO] Training done.'"
        ],
        env_vars={
            "S3_ENDPOINT": "https://minio.voducanh.id.vn",
            "MLFLOW_S3_ENDPOINT_URL": "https://minio.voducanh.id.vn",
            "MLFLOW_ARTIFACT_ROOT": "s3://datalake/mlflow",
            "MLFLOW_ARTIFACTS_DESTINATION": "s3://datalake/mlflow",
            "S3_BUCKET": "datalake",
            "SILVER_PREFIX": "silver/metrics",
            "AWS_S3_ADDRESSING_STYLE": "path",
            "MLFLOW_TRACKING_URI": "http://mlflow.mlflow.svc.cluster.local:5000",
            "WINDOW_SIZE": "10",
            "EPOCHS": "20",
            "BATCH_SIZE": "128",
            "HORIZON_MINUTES": "5",
            "TIMEZONE": "Asia/Ho_Chi_Minh",
            "TRAIN_FRAC": "0.80",
            "VAL_FRAC": "0.10",
            "EXTRA_EMBARGO_MINUTES": "0",
            "DATE_FRACTION": "1.0",
            "DATE_PICK_MODE": "all",
            "DATE_SEED": "42",
            "TRAIN_MONTH": "12",
            "TRAIN_YEAR": "2025",
            "MODEL_NAME": "lstm_forecast",
            "EXPERIMENT_NAME": "lstm_forecast",
        },
        env_from=[k8s.V1EnvFromSource(secret_ref=k8s.V1SecretEnvSource(name="minio-cred"))],
        volumes=[
            k8s.V1Volume(
                name="train-scripts",
                config_map=k8s.V1ConfigMapVolumeSource(
                    name="train-lstm-script",
                    items=[k8s.V1KeyToPath(key="train_lstm.py", path="train_lstm.py")],
                ),
            ),
        ],
        volume_mounts=[k8s.V1VolumeMount(name="train-scripts", mount_path="/app/train", read_only=True)],
        labels={"airflow-task": "train-lstm-forecast"},
        is_delete_operator_pod=True,
        get_logs=True,
        in_cluster=True,
    )

    register = KubernetesPodOperator(
        task_id="register_model",
        name="register-model",
        namespace="airflow",
        image="ducanhvo/train-lstm:latest",
        image_pull_policy="Always",
        cmds=["/bin/sh", "-lc"],
        arguments=[
            r"""
set -e
echo "[INFO] Training done. Running register..."
set +e
python /app/register/register_model.py
rc=$?
set -e

mkdir -p /airflow/xcom

if [ "$rc" -eq 10 ]; then
  echo "[INFO] Promoted to Production -> mark promoted=true"
  echo '{"promoted": true, "rc": 10}' > /airflow/xcom/return.json
  exit 0
elif [ "$rc" -eq 0 ]; then
  echo "[INFO] Not promoted -> promoted=false"
  echo '{"promoted": false, "rc": 0}' > /airflow/xcom/return.json
  exit 0
else
  echo "[ERROR] Register failed with code=$rc"
  exit "$rc"
fi
"""
        ],
        do_xcom_push=True,
        service_account_name="register-model-sa",
        automount_service_account_token=True,
        env_vars={
            "S3_ENDPOINT": "https://minio.voducanh.id.vn",
            "MLFLOW_S3_ENDPOINT_URL": "https://minio.voducanh.id.vn",
            "S3_BUCKET": "datalake",
            "SILVER_PREFIX": "silver/metrics",
            "AWS_S3_ADDRESSING_STYLE": "path",
            "MLFLOW_TRACKING_URI": "http://mlflow.mlflow.svc.cluster.local:5000",
            "MODEL_NAME": "lstm_forecast",
            "EXPERIMENT_NAME": "lstm_forecast",
            "COMPARE_WITH_PRODUCTION": "true",
            "TARGET_STAGE": "Production",
            "ARCHIVE_OLD": "true",
            "MIN_IMPROVE_WAPE": "0.0",
            "MIN_IMPROVE_P95": "0.0",
            "MIN_IMPROVE_UNDER": "0.0",
            "PROMOTED_EXIT_CODE": "10",
            "K8S_ENABLE": "true",
            "K8S_NAMESPACE": "model",
            "RESTART_DEPLOYMENTS": "lstm-serving",
        },
        env_from=[k8s.V1EnvFromSource(secret_ref=k8s.V1SecretEnvSource(name="minio-cred"))],
        volumes=[
            k8s.V1Volume(
                name="register-scripts",
                config_map=k8s.V1ConfigMapVolumeSource(
                    name="register-model-script",
                    items=[k8s.V1KeyToPath(key="register_model.py", path="register_model.py")],
                ),
            ),
        ],
        volume_mounts=[k8s.V1VolumeMount(name="register-scripts", mount_path="/app/register", read_only=True)],
        labels={"airflow-task": "register-model"},
        is_delete_operator_pod=True,
        get_logs=True,
        in_cluster=True,
    )

    gate = ShortCircuitOperator(
        task_id="gate_reference",
        python_callable=_should_run_reference,
    )

    reference = KubernetesPodOperator(
        task_id="save_reference",
        name="drift-reference",
        namespace="airflow",
        image="ducanhvo/train-lstm:latest",
        image_pull_policy="Always",
        cmds=["/bin/sh", "-lc"],
        arguments=[
            "set -e; "
            "echo '[INFO] Promoted -> saving drift reference...'; "
            "python /app/drift/save_reference.py; "
            "echo '[INFO] Drift reference saved.'"
        ],
        env_vars={
            "S3_ENDPOINT": "https://minio.voducanh.id.vn",
            "S3_BUCKET": "datalake",
            "SILVER_PREFIX": "silver/metrics",
            "AWS_S3_ADDRESSING_STYLE": "path",
            "HORIZON_MINUTES": "5",
            "TRAIN_FRAC": "0.80",
            "VAL_FRAC": "0.10",
            "EXTRA_EMBARGO_MINUTES": "0",
            "TIMEZONE": "Asia/Ho_Chi_Minh",
            "DATE_FRACTION": "1.0",
            "DATE_PICK_MODE": "all",
            "DATE_SEED": "42",
            "TRAIN_MONTH": "12",
            "TRAIN_YEAR": "2025",
            "MODEL_NAME": "lstm_forecast",
            "REF_PREFIX": "drift/reference",
            "SAVE_LATEST_POINTER": "true",
            "REF_PER_SERVICE": "true",
            "REF_MAX_ROWS_PER_SERVICE": "200000",
        },
        env_from=[k8s.V1EnvFromSource(secret_ref=k8s.V1SecretEnvSource(name="minio-cred"))],
        volumes=[
            k8s.V1Volume(
                name="ref-scripts",
                config_map=k8s.V1ConfigMapVolumeSource(
                    name="drift-reference-script",
                    items=[k8s.V1KeyToPath(key="save_reference.py", path="save_reference.py")],
                ),
            ),
        ],
        volume_mounts=[k8s.V1VolumeMount(name="ref-scripts", mount_path="/app/drift", read_only=True)],
        labels={"airflow-task": "drift-reference"},
        is_delete_operator_pod=True,
        get_logs=True,
        in_cluster=True,
    )

    train >> register >> gate >> reference
