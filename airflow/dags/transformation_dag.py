"""Dedicated transformation DAG (Spark + dbt) for backfills."""

from datetime import datetime, timedelta

from airflow import DAG
from airflow.operators.python import PythonOperator

default_args = {
    "owner": "skincare-platform",
    "retries": 1,
    "retry_delay": timedelta(minutes=3),
    "execution_timeout": timedelta(hours=2),
}


def spark_job():
    from skincare_platform.config import get_settings
    from skincare_platform.spark.bronze_to_silver import run_bronze_to_silver

    return run_bronze_to_silver(get_settings().lake_root_resolved())


def dbt_job():
    from skincare_platform.config import get_settings
    from skincare_platform.orchestration.pipeline import run_dbt
    from skincare_platform.warehouse.load import load_silver_to_duckdb

    settings = get_settings()
    load_silver_to_duckdb(settings, settings.lake_root_resolved())
    return run_dbt(settings)


with DAG(
    dag_id="skincare_transformation",
    default_args=default_args,
    start_date=datetime(2026, 1, 1),
    schedule=None,
    catchup=True,
    tags=["skincare", "spark", "dbt", "backfill"],
) as dag:
    PythonOperator(task_id="spark_clean", python_callable=spark_job) >> PythonOperator(
        task_id="dbt_run", python_callable=dbt_job
    )
