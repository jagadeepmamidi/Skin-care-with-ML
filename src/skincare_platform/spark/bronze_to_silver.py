"""Spark Bronze → Silver: schema enforcement, dedup, ingredient explosion, parquet."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from pyspark.sql import DataFrame, SparkSession
from pyspark.sql import functions as F
from pyspark.sql.types import ArrayType, StringType
from pyspark.sql.window import Window

from skincare_platform.spark.session import build_spark
from skincare_platform.transforms import tokenize_ingredients


@F.udf(ArrayType(StringType()))
def tokenize_udf(raw: str | None) -> list[str]:
    return tokenize_ingredients(raw)


def _files(root: Path, dataset: str, filename: str) -> list[str]:
    base = root / "bronze" / dataset
    files = sorted(str(p) for p in base.rglob(filename) if p.is_file())
    if not files:
        raise FileNotFoundError(f"No bronze files for {dataset}/{filename} under {base}")
    return files


def _read_jsonl_dir(spark: SparkSession, paths: list[str]) -> DataFrame:
    return spark.read.option("multiLine", "false").option("mode", "PERMISSIVE").json(paths)


def _read_parquet_dir(spark: SparkSession, paths: list[str]) -> DataFrame:
    return spark.read.parquet(*paths)


def _write_parquet(frame: DataFrame, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    (
        frame.coalesce(1)
        .write.mode("overwrite")
        .option("compression", "snappy")
        .parquet(str(dest))
    )


def silver_products(spark: SparkSession, lake_root: Path) -> dict[str, int]:
    cosmetics = _read_jsonl_dir(spark, _files(lake_root, "cosmetics", "products.jsonl"))
    try:
        api = _read_jsonl_dir(spark, _files(lake_root, "product_api", "products.jsonl"))
        products = cosmetics.unionByName(api, allowMissingColumns=True)
    except FileNotFoundError:
        products = cosmetics

    products = (
        products.filter(F.col("product_id").isNotNull())
        .filter(F.col("price") >= 0)
        .filter((F.col("rating").isNull()) | ((F.col("rating") >= 0) & (F.col("rating") <= 5)))
        .withColumn("price", F.col("price").cast("double"))
        .withColumn("rating", F.col("rating").cast("double"))
        .withColumn("ingested_at", F.col("ingested_at").cast("timestamp"))
    )
    ranked = products.withColumn(
        "rn",
        F.row_number().over(Window.partitionBy("product_id").orderBy(F.col("ingested_at").desc())),
    )
    deduped = ranked.filter(F.col("rn") == 1).drop("rn")
    exploded = (
        deduped.withColumn("ingredient_list", tokenize_udf(F.col("ingredients")))
        .withColumn("ingredient_count", F.size("ingredient_list"))
    )
    _write_parquet(exploded, lake_root / "silver" / "products")

    ingredients = (
        exploded.select(F.explode("ingredient_list").alias("ingredient_name"))
        .filter(F.col("ingredient_name").isNotNull())
        .distinct()
        .withColumn(
            "ingredient_id",
            F.abs(F.hash(F.lower(F.col("ingredient_name")))).cast("long"),
        )
        .select("ingredient_id", "ingredient_name")
    )
    _write_parquet(ingredients, lake_root / "silver" / "ingredients")

    bridge = (
        exploded.select("product_id", F.explode("ingredient_list").alias("ingredient_name"))
        .join(ingredients, on="ingredient_name", how="inner")
        .select("product_id", "ingredient_id")
        .dropDuplicates()
    )
    _write_parquet(bridge, lake_root / "silver" / "product_ingredients")
    return {
        "products": exploded.count(),
        "ingredients": ingredients.count(),
        "product_ingredients": bridge.count(),
    }


def silver_prices(spark: SparkSession, lake_root: Path) -> int:
    frame = (
        _read_parquet_dir(spark, _files(lake_root, "pricing", "prices.parquet"))
        .filter(F.col("product_id").isNotNull())
        .filter(F.col("price") >= 0)
        .withColumn("price", F.col("price").cast("double"))
        .withColumn("discount", F.col("discount").cast("double"))
        .withColumn("event_ts", F.col("timestamp").cast("timestamp"))
        .dropDuplicates(["product_id", "timestamp", "retailer"])
    )
    _write_parquet(frame, lake_root / "silver" / "prices")
    return frame.count()


def silver_events(spark: SparkSession, lake_root: Path) -> dict[str, int]:
    events = (
        _read_parquet_dir(spark, _files(lake_root, "events", "events.parquet"))
        .filter(F.col("event_id").isNotNull())
        .filter(F.col("event_type").isin("VIEW_PRODUCT", "SEARCH", "ADD_TO_CART", "PURCHASE", "REVIEW"))
        .withColumn("event_ts", F.col("timestamp").cast("timestamp"))
        .dropDuplicates(["event_id"])
    )
    _write_parquet(events, lake_root / "silver" / "events")

    product_stats = (
        events.filter(F.col("product_id").isNotNull())
        .groupBy("product_id")
        .agg(
            F.sum(F.when(F.col("event_type") == "VIEW_PRODUCT", 1).otherwise(0)).alias("views"),
            F.sum(F.when(F.col("event_type") == "ADD_TO_CART", 1).otherwise(0)).alias("add_to_cart"),
            F.sum(F.when(F.col("event_type") == "PURCHASE", 1).otherwise(0)).alias("purchases"),
            F.sum(F.when(F.col("event_type") == "REVIEW", 1).otherwise(0)).alias("reviews"),
            F.avg(F.col("review_rating")).alias("avg_review_rating"),
            F.countDistinct("user_id").alias("unique_users"),
        )
        .withColumn(
            "conversion_rate",
            F.when(F.col("views") > 0, F.col("purchases") / F.col("views")).otherwise(F.lit(0.0)),
        )
    )
    _write_parquet(product_stats, lake_root / "silver" / "product_activity")

    daily = (
        events.withColumn("event_date", F.to_date("event_ts"))
        .groupBy("event_date", "event_type")
        .agg(F.count("*").alias("event_count"), F.countDistinct("user_id").alias("unique_users"))
    )
    _write_parquet(daily, lake_root / "silver" / "event_daily")
    return {
        "events": events.count(),
        "product_activity": product_stats.count(),
        "event_daily": daily.count(),
    }


def run_bronze_to_silver(lake_root: Path, spark: SparkSession | None = None) -> dict[str, Any]:
    own_session = spark is None
    spark = spark or build_spark()
    try:
        product_stats = silver_products(spark, lake_root)
        price_count = silver_prices(spark, lake_root)
        event_stats = silver_events(spark, lake_root)
        return {"products": product_stats, "prices": price_count, "events": event_stats}
    finally:
        if own_session:
            spark.stop()


def ingredient_id_for(name: str) -> int:
    return abs(int(hashlib.md5(name.lower().encode()).hexdigest()[:8], 16))
