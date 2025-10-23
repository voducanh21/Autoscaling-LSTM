from datetime import datetime
from airflow import DAG
from airflow.providers.cncf.kubernetes.operators.pod import KubernetesPodOperator
from kubernetes import client as k8s

with DAG(
        dag_id="gold_metrics_dag",
        description="Gold layer: aggregate silver → gold",
        start_date=datetime(2025, 10, 18),
        schedule=None,
        catchup=False,
        max_active_runs=1,
        tags=["gold", "metrics"],
) as dag:
    gold = KubernetesPodOperator(
        task_id="gold_metrics",
        name="gold-metrics",
        namespace="airflow",
        image="python:3.11-slim",
        cmds=["/bin/sh", "-lc"],
        arguments=[
            "pip install -q pandas pyarrow fsspec s3fs tzdata && "
            "python /app/gold_aggregator.py"
        ],
        env_vars={
            "S3_BUCKET": "datalake",
            "SILVER_PREFIX": "silver/metrics",
            "GOLD_PREFIX": "gold/metrics",
            "S3_ENDPOINT": "http://minio.minio.svc.cluster.local:9000",
            "TIMEZONE": "Asia/Ho_Chi_Minh",
        },
        env_from=[
            k8s.V1EnvFromSource(secret_ref=k8s.V1SecretEnvSource(name="minio-cred"))
        ],
        volumes=[
            k8s.V1Volume(
                name="gold-scripts",
                config_map=k8s.V1ConfigMapVolumeSource(name="gold-metrics-script"),
            )
        ],
        volume_mounts=[
            k8s.V1VolumeMount(name="gold-scripts", mount_path="/app", read_only=True)
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
                                        values=["bronze-metrics", "silver-metrics", "gold-metrics"],
                                    )
                                ]
                            ),
                            topology_key="kubernetes.io/hostname",
                        ),
                    )
                ]
            )
        ),
        labels={"airflow-task": "gold-metrics"},
        is_delete_operator_pod=True,
        get_logs=True,
        in_cluster=True,
    )
