# dags/train_cnn_lstm_with_reference.py

from __future__ import annotations

import pendulum
from airflow import DAG
from airflow.operators.empty import EmptyOperator
from airflow.operators.python import BranchPythonOperator
from airflow.providers.cncf.kubernetes.operators.kubernetes_pod import KubernetesPodOperator
from airflow.utils.trigger_rule import TriggerRule

from kubernetes.client import models as k8s


# =========================
# Config
# =========================
DAG_ID = "train_cnn_lstm_with_reference"
NAMESPACE = "airflow"
IMAGE = "ducanhvo/train-lstm:latest"

TZ = pendulum.timezone("Asia/Ho_Chi_Minh")

# ConfigMaps in namespace airflow (as you provided)
CM_TRAIN = "train-cnn-lstm-script"
CM_REGISTER = "register-model-script"
CM_REFERENCE = "drift-reference-script"

# Secret in namespace airflow (minio creds)
SECRET_MINIO = "minio-cred"

SERVICE_ACCOUNT = "register-model-sa"  # must exist in namespace airflow
NODE_SELECTOR = {"kubernetes.io/hostname": "k3n-m03"}

# Volumes (mount scripts into /app/train, /app/register, /app/drift)
vol_train = k8s.V1Volume(
    name="train-cnn-lstm-script",
    config_map=k8s.V1ConfigMapVolumeSource(
        name=CM_TRAIN,
        items=[k8s.V1KeyToPath(key="train_cnn_lstm.py", path="train_cnn_lstm.py")],
    ),
)
vm_train = k8s.V1VolumeMount(name="train-cnn-lstm-script", mount_path="/app/train", read_only=True)

vol_register = k8s.V1Volume(
    name="register-model-script",
    config_map=k8s.V1ConfigMapVolumeSource(
        name=CM_REGISTER,
        items=[k8s.V1KeyToPath(key="register_model.py", path="register_model.py")],
    ),
)
vm_register = k8s.V1VolumeMount(name="register-model-script", mount_path="/app/register", read_only=True)

vol_reference = k8s.V1Volume(
    name="drift-reference-script",
    config_map=k8s.V1ConfigMapVolumeSource(
        name=CM_REFERENCE,
        items=[k8s.V1KeyToPath(key="save_reference.py", path="save_reference.py")],
    ),
)
vm_reference = k8s.V1VolumeMount(name="drift-reference-script", mount_path="/app/drift", read_only=True)

VOLUMES = [vol_train, vol_register, vol_reference]
VOLUME_MOUNTS = [vm_train, vm_register, vm_reference]


def _minio_env_vars():
    return [
        k8s.V1EnvVar(
            name="AWS_ACCESS_KEY_ID",
            value_from=k8s.V1EnvVarSource(
                secret_key_ref=k8s.V1SecretKeySelector(name=SECRET_MINIO, key="AWS_ACCESS_KEY_ID")
            ),
        ),
        k8s.V1EnvVar(
            name="AWS_SECRET_ACCESS_KEY",
            value_from=k8s.V1EnvVarSource(
                secret_key_ref=k8s.V1SecretKeySelector(name=SECRET_MINIO, key="AWS_SECRET_ACCESS_KEY")
            ),
        ),
    ]


def _base_env():
    # Same spirit as your CronJob env (keep consistent across tasks).
    # Add/adjust values here if your cluster differs.
    base = {
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
        "HORIZON_MINUTES": "5",
        "TIMEZONE": "Asia/Ho_Chi_Minh",

        # --- Split 80/10/10 ---
        "TRAIN_FRAC": "0.80",
        "VAL_FRAC": "0.10",
        "EXTRA_EMBARGO_MINUTES": "0",

        # --- FULL DATA MODE ---
        "DATE_FRACTION": "1.0",
        "DATE_PICK_MODE": "all",
        "DATE_SEED": "42",

        # --- Model / Experiment ---
        "MODEL_NAME": "cnn_lstm_forecast",
        "EXPERIMENT_NAME": "cnn_lstm_forecast",
    }
    return base


def _train_env():
    e = dict(_base_env())
    # training script default REGISTER_MODEL=false; set explicit to avoid surprises
    e["REGISTER_MODEL"] = "false"
    return e


def _register_env():
    e = dict(_base_env())

    # --- Register behavior ---
    e.update(
        {
            "COMPARE_WITH_PRODUCTION": "true",
            "TARGET_STAGE": "Production",
            "ARCHIVE_OLD": "true",
            "MIN_IMPROVE_WAPE": "0.0",
            "MIN_IMPROVE_P95": "0.0",
            "MIN_IMPROVE_UNDER": "0.0",
            "PROMOTED_EXIT_CODE": "10",

            # --- Patch serving ---
            "K8S_ENABLE": "true",
            "K8S_NAMESPACE": "model",
            "SERVING_CONFIGMAP": "lstm-config",
            "CONFIG_KEY_MODEL_URI": "MODEL_URI",
            "RESTART_DEPLOYMENTS": "lstm-serving",
        }
    )
    return e


def _reference_env():
    e = dict(_base_env())
    e.update(
        {
            "REF_PREFIX": "drift/reference",
            "SAVE_LATEST_POINTER": "true",
            "REF_PER_SERVICE": "true",
            "REF_MAX_ROWS_PER_SERVICE": "200000",
            # save_reference.py auto-generates REF_TAG if not provided
        }
    )
    return e


def branch_on_promotion(**context) -> str:
    """
    Read XCom from register task (written by /airflow/xcom/return.json).
    Return task_id to follow.
    """
    ti = context["ti"]
    x = ti.xcom_pull(task_ids="register_model")
    promoted = False
    if isinstance(x, dict):
        promoted = bool(x.get("promoted", False))
    return "save_reference" if promoted else "skip_reference"


with DAG(
        dag_id=DAG_ID,
        start_date=pendulum.datetime(2025, 1, 1, tz=TZ),
        schedule="0 */6 * * *",
        catchup=False,
        max_active_runs=1,
        default_args={
            "owner": "airflow",
            "retries": 0,
        },
        tags=["ml", "training", "mlflow", "drift"],
) as dag:

    # 1) TRAIN
    train_model = KubernetesPodOperator(
        task_id="train_model",
        name="train-cnn-lstm",
        namespace=NAMESPACE,
        image=IMAGE,
        image_pull_policy="Always",
        service_account_name=SERVICE_ACCOUNT,
        node_selector=NODE_SELECTOR,
        is_delete_operator_pod=True,
        get_logs=True,
        in_cluster=True,
        cmds=["/bin/sh", "-c"],
        arguments=[
            r"""
set -e
echo "[INFO] Start training CNN+LSTM..."
python /app/train/train_cnn_lstm.py
echo "[INFO] Training done."
"""
        ],
        env_vars=[k8s.V1EnvVar(name=k, value=v) for k, v in _train_env().items()] + _minio_env_vars(),
        volumes=VOLUMES,
        volume_mounts=VOLUME_MOUNTS,
    )

    # 2) REGISTER (must succeed even when promoted exit code = 10)
    #    Also must push XCom {promoted: true/false, rc: ..., ...}
    register_model = KubernetesPodOperator(
        task_id="register_model",
        name="register-model",
        namespace=NAMESPACE,
        image=IMAGE,
        image_pull_policy="Always",
        service_account_name=SERVICE_ACCOUNT,
        node_selector=NODE_SELECTOR,
        is_delete_operator_pod=True,
        get_logs=True,
        in_cluster=True,
        do_xcom_push=True,  # reads /airflow/xcom/return.json
        cmds=["/bin/sh", "-c"],
        arguments=[
            r"""
set -e
echo "[INFO] Running register..."
set +e
python /app/register/register_model.py
rc=$?
set -e

# Write XCom payload
mkdir -p /airflow/xcom

if [ "$rc" -eq 10 ]; then
  echo '[INFO] Promoted to Production (rc=10)'
  echo "{\"promoted\": true, \"rc\": 10}" > /airflow/xcom/return.json
  exit 0
elif [ "$rc" -eq 0 ]; then
  echo '[INFO] Not promoted (rc=0)'
  echo "{\"promoted\": false, \"rc\": 0}" > /airflow/xcom/return.json
  exit 0
else
  echo "[ERROR] Register failed with rc=$rc"
  echo "{\"promoted\": false, \"rc\": $rc, \"error\": \"register_failed\"}" > /airflow/xcom/return.json
  exit "$rc"
fi
"""
        ],
        env_vars=[k8s.V1EnvVar(name=k, value=v) for k, v in _register_env().items()] + _minio_env_vars(),
        volumes=VOLUMES,
        volume_mounts=VOLUME_MOUNTS,
    )

    # 2.5) BRANCH
    decide_reference = BranchPythonOperator(
        task_id="decide_reference",
        python_callable=branch_on_promotion,
    )

    skip_reference = EmptyOperator(task_id="skip_reference")

    # 3) REFERENCE (only when promoted)
    save_reference = KubernetesPodOperator(
        task_id="save_reference",
        name="save-drift-reference",
        namespace=NAMESPACE,
        image=IMAGE,
        image_pull_policy="Always",
        service_account_name=SERVICE_ACCOUNT,
        node_selector=NODE_SELECTOR,
        is_delete_operator_pod=True,
        get_logs=True,
        in_cluster=True,
        cmds=["/bin/sh", "-c"],
        arguments=[
            r"""
set -e
echo "[INFO] Saving drift reference..."
python /app/drift/save_reference.py
echo "[INFO] Drift reference saved."
"""
        ],
        env_vars=[k8s.V1EnvVar(name=k, value=v) for k, v in _reference_env().items()] + _minio_env_vars(),
        volumes=VOLUMES,
        volume_mounts=VOLUME_MOUNTS,
        trigger_rule=TriggerRule.NONE_FAILED_MIN_ONE_SUCCESS,
    )

    done = EmptyOperator(
        task_id="done",
        trigger_rule=TriggerRule.NONE_FAILED_MIN_ONE_SUCCESS,
    )

    # Dependencies
    train_model >> register_model >> decide_reference
    decide_reference >> [save_reference, skip_reference]
    [save_reference, skip_reference] >> done
