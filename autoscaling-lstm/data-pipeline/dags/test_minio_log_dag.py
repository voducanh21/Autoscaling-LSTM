from datetime import datetime
from airflow import DAG
from airflow.operators.python import PythonOperator


def test_write_log():
    import logging
    logging.info("===== Test log ghi vào MinIO =====")
    logging.warning("Dòng WARNING để kiểm tra màu sắc log.")
    print("Dòng print() này cũng phải thấy trong log nếu MinIO hoạt động.")
    return "done"


with DAG(
        dag_id="test_minio_log_dag",
        description="Kiểm tra xem Airflow có ghi log lên MinIO thành công không",
        start_date=datetime(2025, 10, 1),
        schedule=None,
        catchup=False,
        tags=["test", "minio"],
) as dag:

    test_task = PythonOperator(
        task_id="write_test_log",
        python_callable=test_write_log,
    )

    test_task
