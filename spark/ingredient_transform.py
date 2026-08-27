"""Spark-submit entrypoint for ingredient tokenization + bridge table."""

from skincare_platform.config import get_settings
from skincare_platform.spark.bronze_to_silver import silver_products
from skincare_platform.spark.session import build_spark

if __name__ == "__main__":
    spark = build_spark("ingredient-transform")
    try:
        print(silver_products(spark, get_settings().lake_root_resolved()))
    finally:
        spark.stop()
