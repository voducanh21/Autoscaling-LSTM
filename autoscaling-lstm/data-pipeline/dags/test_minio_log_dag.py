from airflow import DAG
from airflow.operators.python import PythonOperator
from datetime import datetime
import logging
import time

def test_log():
    logging.info("=== TEST REMOTE LOGGING START ===")
    for i in range(3):
        logging.info(f"Step {i+1}/3: working...")
        time.sleep(2)
    logging.warning("This is a sample warning log.")
    logging.error("This is a sample error log.")
    logging.info("=== TEST REMOTE LOGGING DONE ===")

with DAG(
        dag_id="test_remote_logging_dag",
        start_date=datetime(2025, 10, 12),
        schedule_interval=None,
        catchup=False,
        tags=["test", "logging"],
) as dag:
    test_task = PythonOperator(
        task_id="check_logs",
        python_callable=test_log,
    )
