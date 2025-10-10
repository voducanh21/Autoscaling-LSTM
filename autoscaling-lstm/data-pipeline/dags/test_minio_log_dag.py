from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.python import PythonOperator
import logging
import os

def test_log_function(**context):
    log = logging.getLogger("airflow.test_logs_dag")
    log.info("✅ INFO: Log ghi thành công vào Airflow logging system.")
    log.warning("⚠️ WARNING: Kiểm tra ghi log cảnh báo.")
    log.error("❌ ERROR: Mẫu log lỗi (chỉ để test).")

    log_dir = os.getenv("AIRFLOW_LOG_FOLDER", "/opt/airflow/logs")
    task_instance = context['ti']
    log_path = f"{log_dir}/dag_id={task_instance.dag_id}/run_id={task_instance.run_id}/task_id={task_instance.task_id}/attempt=1.log"
    log.info(f"📁 Đường dẫn log dự kiến: {log_path}")

default_args = {
    'owner': 'airflow',
    'retries': 0,
    'retry_delay': timedelta(minutes=1),
}

with DAG(
        dag_id='test_logs_dag',
        default_args=default_args,
        schedule=None,             # ✅ dùng schedule thay vì schedule_interval
        start_date=datetime(2025, 1, 1),
        catchup=False,
        tags=['debug', 'logging'],
) as dag:

    test_log = PythonOperator(
        task_id='check_logs',
        python_callable=test_log_function,
        provide_context=True,
    )

    test_log
