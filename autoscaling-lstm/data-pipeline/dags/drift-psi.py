# dags/drift_psi_dag.py
import json
import pendulum
from airflow import DAG
from airflow.operators.python import ShortCircuitOperator
from airflow.operators.trigger_dagrun import TriggerDagRunOperator
from airflow.providers.cncf.kubernetes.operators.pod import KubernetesPodOperator
from kubernetes import client as k8s

VN_TZ = pendulum.timezone("Asia/Ho_Chi_Minh")

RETRAIN_DAG_ID = "train_lstm_forecast_dag"  # retrain DAG bạn muốn kích hoạt (đổi đúng DAG id của bạn)

def _should_trigger_retrain(ti) -> bool:
    """
    compute_psi sẽ push XCom JSON qua /airflow/xcom/return.json
    Ưu tiên key: retrain (mới). Fallback: drift (cũ).
    """
    x = ti.xcom_pull(task_ids="compute_psi")
    print(f"[GATE] raw xcom = {x!r}")

    if x in (None, "", "__airflow_xcom_result_empty__"):
        print("[GATE] xcom empty -> False")
        return False

    # KubernetesPodOperator có thể trả về string JSON
    if isinstance(x, str):
        try:
            x = json.loads(x)
            print(f"[GATE] parsed xcom = {x}")
        except Exception as e:
            print(f"[GATE] cannot parse xcom json: {e} -> False")
            return False

    if isinstance(x, dict):
        if "retrain" in x:
            v = bool(x.get("retrain", False))
            print(f"[GATE] retrain={v}")
            return v
        if "drift" in x:
            v = bool(x.get("drift", False))
            print(f"[GATE] drift={v}")
            return v

    print("[GATE] unsupported xcom -> False")
    return False


with DAG(
        dag_id="drift_psi",
        start_date=pendulum.datetime(2026, 1, 6, tz=VN_TZ),
        schedule="0 2 * * 1",  # 02:00 mỗi Thứ 2
        catchup=False,
        max_active_runs=1,
        tags=["drift", "psi"],
) as dag:

    # 1) Compute PSI (KHÔNG dùng exit code để gate nữa)
    # - compute_psi.py sẽ tự ghi /airflow/xcom/return.json với retrain=true/false và psi_overall...
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
python /app/compute_psi.py
echo "[INFO] PSI job done (compute_psi.py should write /airflow/xcom/return.json)"
"""
        ],
        do_xcom_push=True,
        env_vars={
            # --- S3 / MinIO ---
            "S3_ENDPOINT": "https://minio.voducanh.id.vn",
            "S3_BUCKET": "datalake",
            "AWS_S3_ADDRESSING_STYLE": "path",

            # --- DRIFT TARGET ---
            "MODEL_NAME": "lstm_forecast",
            "REF_PREFIX": "drift/reference",
            "CURRENT_PREFIX": "drift/current/metrics1",
            "PSI_PREFIX": "drift/psi",

            # --- Current selection ---
            "CURRENT_DAYS": "7",
            "CURRENT_SEED": "42",

            # --- PSI knobs ---
            "PSI_BINS": "10",
            "PSI_EPS": "0.000001",
            "MAX_SAMPLES_PER_SERVICE": "200000",

            # --- Gate threshold ---
            "PSI_THRESHOLD": "0.2",
            "GATE_MODE": "mean",   # đổi "max" nếu muốn nhạy hơn

            # --- Timezone ---
            "TIMEZONE": "Asia/Ho_Chi_Minh",

            # --- Evidently artifacts (optional) ---
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

    # 2) Gate: chỉ trigger retrain khi retrain/drift=true
    gate = ShortCircuitOperator(
        task_id="gate_retrain",
        python_callable=_should_trigger_retrain,
    )

    # 3) Trigger retrain DAG
    trigger_retrain = TriggerDagRunOperator(
        task_id="trigger_retrain_dag",
        trigger_dag_id=RETRAIN_DAG_ID,
        wait_for_completion=False,
        reset_dag_run=False,
        conf={
            "reason": "psi_drift",
            "source_dag": "drift_psi",
            "ts": "{{ ts }}",
            "xcom": "{{ ti.xcom_pull(task_ids='compute_psi') }}",
            "psi_overall": "{{ (ti.xcom_pull(task_ids='compute_psi') or {}).get('psi_overall') }}",
            "threshold": "{{ (ti.xcom_pull(task_ids='compute_psi') or {}).get('threshold') }}",
            "gate_mode": "{{ (ti.xcom_pull(task_ids='compute_psi') or {}).get('gate_mode') }}",
            "retrain": "{{ (ti.xcom_pull(task_ids='compute_psi') or {}).get('retrain') }}",
            "run_tag": "{{ (ti.xcom_pull(task_ids='compute_psi') or {}).get('run_tag') }}",
            "psi_s3_key": "{{ (ti.xcom_pull(task_ids='compute_psi') or {}).get('psi_s3_key') }}",
            "model_name": "lstm_forecast",
        },
        trigger_rule="all_success",  # chỉ chạy khi gate=True (ShortCircuit sẽ skip downstream nếu False)
    )

    psi >> gate >> trigger_retrain
