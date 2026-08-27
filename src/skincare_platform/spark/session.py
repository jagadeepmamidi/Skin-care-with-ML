"""Local Spark session factory."""

from __future__ import annotations

from pyspark.sql import SparkSession


def build_spark(app_name: str = "skincare-platform", shuffle_partitions: int = 8) -> SparkSession:
    return (
        SparkSession.builder.appName(app_name)
        .master("local[*]")
        .config("spark.sql.session.timeZone", "UTC")
        .config("spark.sql.shuffle.partitions", str(shuffle_partitions))
        .config("spark.ui.showConsoleProgress", "false")
        .config("spark.driver.memory", "2g")
        .config("spark.sql.adaptive.enabled", "true")
        .getOrCreate()
    )
