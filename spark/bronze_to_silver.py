"""Spark-submit entrypoint: Bronze JSONL → Silver Parquet."""

from pathlib import Path

from skincare_platform.config import get_settings
from skincare_platform.spark.bronze_to_silver import run_bronze_to_silver

if __name__ == "__main__":
    settings = get_settings()
    stats = run_bronze_to_silver(Path(settings.lake_root_resolved()))
    print(stats)
