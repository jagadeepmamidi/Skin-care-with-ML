"""Quality-only DAG — rerun GX-style suites + dbt tests without re-ingesting."""

from datetime import datetime, timedelta

from airflow import DAG
from airflow.operators.python import PythonOperator

default_args = {"owner": "skincare-platform", "retries": 1, "retry_delay": timedelta(minutes=2)}


def quality():
    from skincare_platform.config import get_settings
    from skincare_platform.lake import get_lake
    from skincare_platform.orchestration.pipeline import run_quality

    settings = get_settings()
    return run_quality(settings, get_lake(settings), "quality_dag")


def dbt_test():
    from skincare_platform.config import get_settings
    from skincare_platform.orchestration.pipeline import run_dbt

    return run_dbt(get_settings())


with DAG(
    dag_id="skincare_quality",
    default_args=default_args,
    start_date=datetime(2026, 1, 1),
    schedule="@hourly",
    catchup=False,
    tags=["skincare", "quality"],
) as dag:
    PythonOperator(task_id="data_quality", python_callable=quality)
    PythonOperator(task_id="dbt_test", python_callable=dbt_test)
