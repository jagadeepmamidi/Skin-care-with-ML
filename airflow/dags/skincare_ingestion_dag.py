"""Airflow DAG: Skincare Intelligence batch platform.

The DAG calls the same Python orchestration used by `skincare-platform run-pipeline`,
so local CLI runs and Airflow runs stay identical.
"""

from __future__ import annotations

from datetime import datetime, timedelta

from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.utils.trigger_rule import TriggerRule

default_args = {
    "owner": "skincare-platform",
    "depends_on_past": False,
    "retries": 2,
    "retry_delay": timedelta(minutes=5),
    "execution_timeout": timedelta(hours=2),
}


def _settings():
    from skincare_platform.config import get_settings

    return get_settings()


def validate_sources(**context) -> str:
    settings = _settings()
    csv_path = settings.raw_csv_path
    if not csv_path.exists():
        raise FileNotFoundError(f"Missing source CSV: {csv_path}")
    context["ti"].xcom_push(key="csv_path", value=str(csv_path))
    return str(csv_path)


def ingest_csv(**context) -> dict:
    from skincare_platform.ingestion.cosmetics import ingest_cosmetics
    from skincare_platform.lake import get_lake

    settings = _settings()
    return ingest_cosmetics(get_lake(settings), settings.raw_csv_path)


def ingest_api(**context) -> dict:
    from skincare_platform.ingestion.product_api import ingest_product_api
    from skincare_platform.lake import get_lake

    settings = _settings()
    return ingest_product_api(get_lake(settings), settings)


def ingest_events_and_prices(**context) -> dict:
    from skincare_platform.orchestration.pipeline import generate_synthetic, ingest_all

    settings = _settings()
    generate_synthetic(settings, settings.event_count, settings.price_days)
    return ingest_all(settings, incremental=True)


def bronze_already_loaded(**context) -> str:
    return "bronze_ok"


def spark_clean(**context) -> dict:
    from skincare_platform.spark.bronze_to_silver import run_bronze_to_silver

    return run_bronze_to_silver(_settings().lake_root_resolved())


def dbt_run(**context) -> dict:
    from skincare_platform.orchestration.pipeline import run_dbt
    from skincare_platform.warehouse.load import load_silver_to_duckdb

    settings = _settings()
    load_silver_to_duckdb(settings, settings.lake_root_resolved())
    return run_dbt(settings)


def data_quality(**context) -> dict:
    from skincare_platform.lake import get_lake
    from skincare_platform.orchestration.pipeline import run_quality

    settings = _settings()
    return run_quality(settings, get_lake(settings), context["run_id"])


def gold_ml(**context) -> dict:
    from skincare_platform.lake import get_lake
    from skincare_platform.ml.features import export_ml_features, write_gold_ml_parquet

    settings = _settings()
    export = export_ml_features(settings)
    write_gold_ml_parquet(settings, get_lake(settings))
    return export


def update_dashboard(**context) -> dict:
    from skincare_platform.dashboards.export import export_powerbi_csvs

    return export_powerbi_csvs(_settings())


with DAG(
    dag_id="skincare_medallion_pipeline",
    default_args=default_args,
    description="Bronze → Silver → Gold skincare platform with quality gates",
    start_date=datetime(2026, 1, 1),
    schedule="@daily",
    catchup=False,
    max_active_runs=1,
    tags=["skincare", "medallion", "dbt", "spark"],
) as dag:
    start = PythonOperator(task_id="start", python_callable=lambda: "start")
    validate = PythonOperator(task_id="validate_sources", python_callable=validate_sources)
    t_csv = PythonOperator(task_id="ingest_csv", python_callable=ingest_csv)
    t_api = PythonOperator(task_id="ingest_api", python_callable=ingest_api)
    t_events = PythonOperator(task_id="ingest_events", python_callable=ingest_events_and_prices)
    bronze = PythonOperator(task_id="bronze_load", python_callable=bronze_already_loaded)
    spark = PythonOperator(task_id="spark_clean", python_callable=spark_clean)
    silver = PythonOperator(task_id="silver_load", python_callable=lambda: "silver_ok")
    dbt = PythonOperator(task_id="dbt_run", python_callable=dbt_run)
    dbt_test = PythonOperator(task_id="dbt_test", python_callable=lambda: "tests_run_in_dbt_run")
    quality = PythonOperator(task_id="data_quality", python_callable=data_quality)
    gold = PythonOperator(task_id="gold_load", python_callable=gold_ml)
    dash = PythonOperator(task_id="update_dashboard", python_callable=update_dashboard)
    ml = PythonOperator(
        task_id="ml_features",
        python_callable=gold_ml,
        trigger_rule=TriggerRule.ALL_SUCCESS,
    )

    start >> validate >> [t_csv, t_api, t_events] >> bronze >> spark >> silver >> dbt >> dbt_test >> quality >> gold
    gold >> [dash, ml]
