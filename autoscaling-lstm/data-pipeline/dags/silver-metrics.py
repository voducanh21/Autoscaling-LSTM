from datetime import datetime
from airflow import DAG
from airflow.providers.cncf.kubernetes.operators.pod import KubernetesPodOperator
from kubernetes import client as k8s

with DAG(
        dag_id="silver_metrics_dag",
        start_date=datetime(2025, 10, 20),
        # 1 week / 1 run (Monday 02:00)
        schedule="0 2 * * 1",
        catchup=False,
        max_active_runs=1,
        tags=["silver", "metrics"],
) as dag:
    silver = KubernetesPodOperator(
        task_id="silver_metrics",
        name="silver-metrics",
        namespace="airflow",
        image="python:3.11-slim",
        cmds=["/bin/sh", "-lc"],
        arguments=[
            "pip install -q pandas pyarrow fsspec s3fs tzdata && "
            "python /app/silver_builder.py"
        ],
        env_vars={
            # storage
            "S3_BUCKET": "datalake",
            "BRONZE_PREFIX": "bronze/metrics",
            "SILVER_PREFIX": "silver/metrics",
            "S3_ENDPOINT": "https://minio.voducanh.id.vn",
            "AWS_S3_ADDRESSING_STYLE": "path",
            "AWS_DEFAULT_REGION": "us-east-1",

            # time / processing
            "TIMEZONE": "Asia/Ho_Chi_Minh",
            "BRONZE_LOOKBACK_DAYS": "8",

            # optional tuning (keep defaults if you don't need)
            # "HORIZON_MINUTES": "5",
            # "FREQ": "1min",
            # "MAX_FFILL_MINUTES": "10",
            # "SILVER_WRITE_MODE": "overwrite",
            # "SILVER_PART_NAME": "part-0.parquet",

            # optional marker customization
            # "BRONZE_MARKER_DIR": "bronze/metrics/_markers",
            # "BRONZE_MARKER_NAME": "silver_builder_last_7d.json",
        },
        env_from=[
            k8s.V1EnvFromSource(secret_ref=k8s.V1SecretEnvSource(name="minio-cred"))
        ],
        volumes=[
            k8s.V1Volume(
                name="silver-scripts",
                config_map=k8s.V1ConfigMapVolumeSource(
                    # IMPORTANT: ConfigMap must exist in namespace "airflow"
                    name="silver-metrics-script"
                ),
            )
        ],
        volume_mounts=[
            k8s.V1VolumeMount(
                name="silver-scripts", mount_path="/app", read_only=True
            )
        ],
        affinity=k8s.V1Affinity(
            pod_anti_affinity=k8s.V1PodAntiAffinity(
                preferred_during_scheduling_ignored_during_execution=[
                    k8s.V1WeightedPodAffinityTerm(
                        weight=100,
                        pod_affinity_term=k8s.V1PodAffinityTerm(
                            label_selector=k8s.V1LabelSelector(
                                match_expressions=[
                                    k8s.V1LabelSelectorRequirement(
                                        key="airflow-task",
                                        operator="In",
                                        values=["bronze-metrics", "gold-metrics", "silver-metrics"],
                                    )
                                ]
                            ),
                            topology_key="kubernetes.io/hostname",
                        ),
                    )
                ]
            )
        ),
        labels={"airflow-task": "silver-metrics"},
        is_delete_operator_pod=True,
        get_logs=True,
        in_cluster=True,
    )
