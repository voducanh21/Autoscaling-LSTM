# dags/drift_psi_dag.py
import pendulum
from airflow import DAG
from airflow.providers.cncf.kubernetes.operators.pod import KubernetesPodOperator
from kubernetes import client as k8s

VN_TZ = pendulum.timezone("Asia/Ho_Chi_Minh")

with DAG(
        dag_id="drift_psi",
        start_date=pendulum.datetime(2025, 10, 20, tz=VN_TZ),
        schedule="0 2 * * 1",  # weekly 02:00 Monday
        catchup=False,
        max_active_runs=1,
        tags=["drift", "psi"],
) as dag:

    psi = KubernetesPodOperator(
        task_id="compute_psi",
        name="drift-psi",
        namespace="airflow",

        # Use prebuilt image with evidently installed
        image="ducanhvo/train-lstm:latest",
        image_pull_policy="Always",

        # Same behavior as cronjob: run python script directly
        cmds=["/bin/sh", "-c"],
        arguments=[
            "set -e; "
            "echo '[INFO] Start PSI job...'; "
            "python /app/compute_psi.py; "
            "echo '[INFO] PSI job done.'"
        ],

        # Prefer env_vars for non-secret + env_from for secret
        env_vars={
            "S3_ENDPOINT": "https://minio.voducanh.id.vn",
            "S3_BUCKET": "datalake",
            "AWS_S3_ADDRESSING_STYLE": "path",

            "MODEL_NAME": "cnn_lstm_forecast",
            "REF_PREFIX": "drift/reference",
            "CURRENT_PREFIX": "drift/current/metrics",
            "PSI_PREFIX": "drift/psi",

            "CURRENT_DAYS": "7",
            "CURRENT_PICK_MODE": "last",
            "CURRENT_SEED": "42",

            "PSI_BINS": "10",
            "PSI_EPS": "0.000001",
            "MAX_SAMPLES_PER_SERVICE": "200000",

            "TIMEZONE": "Asia/Ho_Chi_Minh",

            # Optional gating (uncomment if needed)
            # "PSI_THRESHOLD": "0.2",
        },

        env_from=[
            k8s.V1EnvFromSource(
                secret_ref=k8s.V1SecretEnvSource(name="minio-cred")
            )
        ],

        volumes=[
            k8s.V1Volume(
                name="drift-psi-script",
                config_map=k8s.V1ConfigMapVolumeSource(name="drift-psi-script"),
            )
        ],
        volume_mounts=[
            k8s.V1VolumeMount(
                name="drift-psi-script",
                mount_path="/app",
                read_only=True,
            )
        ],

        labels={"airflow-task": "drift-psi"},
        is_delete_operator_pod=True,
        get_logs=True,
        in_cluster=True,
    )
