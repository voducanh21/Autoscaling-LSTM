# dags/drift_psi_dag.py
import pendulum
from airflow import DAG
from airflow.operators.python import ShortCircuitOperator
from airflow.operators.trigger_dagrun import TriggerDagRunOperator
from airflow.providers.cncf.kubernetes.operators.pod import KubernetesPodOperator
from kubernetes import client as k8s

VN_TZ = pendulum.timezone("Asia/Ho_Chi_Minh")

RETRAIN_DAG_ID = "train_cnn_lstm_dag"  # DAG retrain bạn muốn kích hoạt

def _should_trigger_retrain(ti) -> bool:
    """
    compute_psi sẽ push XCom {"drift": true/false, "rc": <int>}
    trigger retrain chỉ chạy khi drift == True
    """
    x = ti.xcom_pull(task_ids="compute_psi")
    try:
        return bool((x or {}).get("drift", False))
    except Exception:
        return False


with DAG(
        dag_id="drift_psi",
        start_date=pendulum.datetime(2025, 10, 20, tz=VN_TZ),
        schedule="0 2 * * 1",  # 02:00 mỗi Thứ 2 (weekly)
        catchup=False,
        max_active_runs=1,
        tags=["drift", "psi"],
) as dag:

    # 1) Compute PSI (rc=2 => drift=true nhưng EXIT 0 để task không fail)
    psi = KubernetesPodOperator(
        task_id="compute_psi",
        name="drift-psi",
        namespace="airflow",
        image="ducanhvo/train-lstm:latest",
        image_pull_policy="Always",
        cmds=["/bin/sh", "-lc"],
        arguments=[
            r"""
set -e
echo "[INFO] Start PSI job..."
set +e
python /app/compute_psi.py
rc=$?
set -e

mkdir -p /airflow/xcom

if [ "$rc" -eq 2 ]; then
  echo "[INFO] PSI>=threshold (rc=2) -> drift=true"
  echo '{"drift": true, "rc": 2}' > /airflow/xcom/return.json
  exit 0
elif [ "$rc" -eq 0 ]; then
  echo "[INFO] PSI<threshold (rc=0) -> drift=false"
  echo '{"drift": false, "rc": 0}' > /airflow/xcom/return.json
  exit 0
else
  echo "[ERROR] PSI job failed rc=$rc"
  echo '{"drift": null, "rc": '"$rc"'}' > /airflow/xcom/return.json
  exit "$rc"
fi
"""
        ],
        do_xcom_push=True,
        env_vars={
            # --- S3 / MinIO ---
            "S3_ENDPOINT": "https://minio.voducanh.id.vn",
            "S3_BUCKET": "datalake",
            "AWS_S3_ADDRESSING_STYLE": "path",

            # --- Model / drift paths (đổi cho đúng hệ bạn) ---
            # Nếu bạn muốn retrain cnn_lstm_forecast thì để đúng model này
            "MODEL_NAME": "cnn_lstm_forecast",
            "REF_PREFIX": "drift/reference",
            "CURRENT_PREFIX": "drift/current/metrics1",  # bạn nói current nằm metrics1
            "PSI_PREFIX": "drift/psi",

            # --- Current selection ---
            "CURRENT_DAYS": "7",
            "CURRENT_PICK_MODE": "last",
            "CURRENT_SEED": "42",

            # --- PSI knobs ---
            "PSI_BINS": "10",
            "PSI_EPS": "0.000001",
            "MAX_SAMPLES_PER_SERVICE": "200000",

            # --- Gate threshold ---
            "PSI_THRESHOLD": "0.2",
            "GATE_MODE": "mean",

            # --- Timezone ---
            "TIMEZONE": "Asia/Ho_Chi_Minh",

            # --- Evidently artifacts (nếu muốn) ---
            "SAVE_EVIDENTLY": "true",
            "EVIDENTLY_PREFIX": "drift/evidently",
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

    # 2) Gate: chỉ trigger retrain khi drift=true
    gate = ShortCircuitOperator(
        task_id="gate_retrain",
        python_callable=_should_trigger_retrain,
    )

    # 3) Trigger retrain DAG
    trigger_retrain = TriggerDagRunOperator(
        task_id="trigger_retrain_dag",
        trigger_dag_id=RETRAIN_DAG_ID,
        wait_for_completion=False,
        reset_dag_run=False,  # không xoá run cũ; tạo run mới
        conf={
            "reason": "psi_drift",
            "source_dag": "drift_psi",
            "ts": "{{ ts }}",
            "psi_rc": "{{ ti.xcom_pull(task_ids='compute_psi')['rc'] }}",
        },
    )

    psi >> gate >> trigger_retrain
