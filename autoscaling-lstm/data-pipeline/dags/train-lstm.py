from datetime import datetime
from airflow import DAG
from airflow.providers.cncf.kubernetes.operators.pod import KubernetesPodOperator
from kubernetes import client as k8s

with DAG(
        dag_id="train_lstm_dag",
        description="Train and register LSTM model to MLflow (2 stages)",
        start_date=datetime(2025, 10, 27),
        schedule="0 */6 * * *",      # chạy mỗi 6 tiếng
        catchup=False,
        max_active_runs=1,
        tags=["train", "lstm", "mlflow"],
) as dag:

    # --- Mount ConfigMap chứa script huấn luyện ---
    volume_train = k8s.V1Volume(
        name="train-lstm-script",
        config_map=k8s.V1ConfigMapVolumeSource(name="train-lstm-script")
    )
    mount_train = k8s.V1VolumeMount(
        name="train-lstm-script",
        mount_path="/app/train",
        read_only=True
    )

    # --- Mount ConfigMap chứa script đăng ký ---
    volume_register = k8s.V1Volume(
        name="register-model-script",
        config_map=k8s.V1ConfigMapVolumeSource(name="register-model-script")
    )
    mount_register = k8s.V1VolumeMount(
        name="register-model-script",
        mount_path="/app/register",
        read_only=True
    )

    # ==============================================================
    # 🧩 STAGE 1: Huấn luyện mô hình (Train)
    # ==============================================================
    train_lstm = KubernetesPodOperator(
        task_id="train_lstm",
        name="train-lstm",
        namespace="airflow",
        image="ducanhvo/train-lstm:latest",
        image_pull_policy="Always",
        cmds=["python"],
        arguments=["/app/train/train_lstm.py"],
        env_vars={
            # --- MINIO / MLFLOW CONFIG ---
            "AWS_STORAGE_FORCE_HTTP": "true",
            "S3_ENDPOINT": "http://minio.minio.svc.cluster.local:9000",
            "MLFLOW_S3_ENDPOINT_URL": "http://minio.minio.svc.cluster.local:9000",
            "MLFLOW_ARTIFACTS_DESTINATION": "s3://datalake/mlflow",
            "S3_BUCKET": "datalake",
            "SILVER_PREFIX": "silver/metrics",
            "MLFLOW_TRACKING_URI": "http://mlflow.mlflow.svc.cluster.local:5000",
            # --- THAM SỐ HUẤN LUYỆN ---
            "TARGET": "rps_1m",
            "WINDOW_SIZE": "30",
            "EPOCHS": "40",
            "BATCH_SIZE": "64",
        },
        env_from=[
            k8s.V1EnvFromSource(secret_ref=k8s.V1SecretEnvSource(name="minio-cred"))
        ],
        volumes=[volume_train],
        volume_mounts=[mount_train],
        node_selector={"kubernetes.io/hostname": "k3n-m03"},
        is_delete_operator_pod=True,
        get_logs=True,
        in_cluster=True,
    )

    # ==============================================================
    # 🧩 STAGE 2: Đăng ký và promote mô hình (Register)
    # ==============================================================
    register_model = KubernetesPodOperator(
        task_id="register_model",
        name="register-model",
        namespace="airflow",
        image="python:3.11-slim",
        image_pull_policy="IfNotPresent",
        cmds=["/bin/sh", "-lc"],
        arguments=[
            "pip install -q mlflow kubernetes && "
            "python /app/register/register_model.py"
        ],
        env_vars={
            "MLFLOW_TRACKING_URI": "http://mlflow.mlflow.svc.cluster.local:5000",
            "MODEL_NAME": "lstm-autoscaler",
            "CONFIGMAP_NAME": "lstm-config",
            "CONFIGMAP_NAMESPACE": "model",
        },
        env_from=[
            k8s.V1EnvFromSource(secret_ref=k8s.V1SecretEnvSource(name="minio-cred"))
        ],
        volumes=[volume_register],
        volume_mounts=[mount_register],
        node_selector={"kubernetes.io/hostname": "k3n-m03"},
        is_delete_operator_pod=True,
        get_logs=True,
        in_cluster=True,
    )

    # --- DAG flow ---
    train_lstm >> register_model
