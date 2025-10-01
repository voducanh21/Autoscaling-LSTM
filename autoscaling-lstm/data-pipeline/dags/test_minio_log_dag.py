from airflow import DAG
from airflow.operators.bash import BashOperator
from datetime import datetime

with DAG(
        dag_id="test_minio_log_dag",
        schedule=None,
        start_date=datetime(2025, 10, 1),
        catchup=False,
        tags=["test", "minio", "log"],
) as dag:
    t1 = BashOperator(
        task_id="say_hello",
        bash_command="echo 'Hello from Airflow! Logging to MinIO works!'"
    )
