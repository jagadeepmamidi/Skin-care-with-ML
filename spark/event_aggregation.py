"""Spark-submit entrypoint for event aggregations (views, conversion)."""

from skincare_platform.config import get_settings
from skincare_platform.spark.bronze_to_silver import silver_events
from skincare_platform.spark.session import build_spark

if __name__ == "__main__":
    spark = build_spark("event-aggregation")
    try:
        print(silver_events(spark, get_settings().lake_root_resolved()))
    finally:
        spark.stop()
