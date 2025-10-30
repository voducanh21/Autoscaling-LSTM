from datetime import datetime
from airflow import DAG
from airflow.providers.cncf.kubernetes.operators.pod import KubernetesPodOperator
from kubernetes import client as k8s

with DAG(
        dag_id="train_lstm_dag",
        description="Train LSTM model from Silver metrics and log to MLflow",
        start_date=datetime(2025, 10, 27),
        schedule=None,                 # hoặc "0 */6 * * *" nếu muốn chạy định kỳ 6 tiếng/lần
        catchup=False,
        max_active_runs=1,
        tags=["train", "lstm", "mlflow"],
) as dag:

    # --- Mount ConfigMap chứa script huấn luyện ---
    volume_script = k8s.V1Volume(
        name="train-lstm-script",
        config_map=k8s.V1ConfigMapVolumeSource(name="train-lstm-script")
    )
    mount_script = k8s.V1VolumeMount(
        name="train-lstm-script",
        mount_path="/app",
        read_only=True
    )

    # --- Pod chạy huấn luyện ---
    train_lstm = KubernetesPodOperator(
        task_id="train_lstm",
        name="train-lstm",
        namespace="airflow",
        image="python:3.11-slim",
        image_pull_policy="IfNotPresent",
        cmds=["/bin/sh", "-lc"],
        arguments=[
            "pip install -q pandas pyarrow s3fs fsspec tensorflow==2.16.1 "
            "scikit-learn mlflow tzdata joblib && "
            "python /app/train_lstm.py"
        ],
        env_vars={
            "S3_ENDPOINT": "http://minio.minio.svc.cluster.local:9000",
            "S3_BUCKET": "datalake",
            "SILVER_PREFIX": "silver/metrics",
            "MLFLOW_TRACKING_URI": "http://mlflow.mlflow.svc.cluster.local:5000",
            "TARGET": "rps_1m",
            "WINDOW_SIZE": "30",
            "EPOCHS": "40",
            "BATCH_SIZE": "64",
        },
        env_from=[
            k8s.V1EnvFromSource(secret_ref=k8s.V1SecretEnvSource(name="minio-cred"))
        ],
        volumes=[volume_script],
        volume_mounts=[mount_script],
        affinity={
            "podAntiAffinity": {
                "preferredDuringSchedulingIgnoredDuringExecution": [
                    {
                        "weight": 100,
                        "podAffinityTerm": {
                            "labelSelector": {
                                "matchExpressions": [
                                    {"key": "app", "operator": "In", "values": ["airflow"]}
                                ]
                            },
                            "topologyKey": "kubernetes.io/hostname"
                        }
                    }
                ]
            }
        },
        is_delete_operator_pod=True,
        get_logs=True,
        in_cluster=True,
    )