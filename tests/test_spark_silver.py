"""Lightweight Spark job tests."""

from pathlib import Path

import pytest

from skincare_platform.ingestion.cosmetics import ingest_cosmetics
from skincare_platform.lake import LocalLake
from skincare_platform.spark.bronze_to_silver import silver_products
from skincare_platform.spark.session import build_spark


@pytest.mark.spark
def test_silver_products_explode_ingredients(tmp_path: Path):
    lake_root = tmp_path / "lake"
    lake = LocalLake(lake_root)
    ingest_cosmetics(lake, Path("cosmetics.csv"), include_bad_rows=True)
    spark = build_spark("test-silver", shuffle_partitions=2)
    try:
        stats = silver_products(spark, lake_root)
    finally:
        spark.stop()
    assert stats["products"] >= 1400
    assert stats["ingredients"] >= 200
    assert stats["product_ingredients"] > stats["products"]
    assert (lake_root / "silver" / "products").exists()
    assert (lake_root / "silver" / "ingredients").exists()
