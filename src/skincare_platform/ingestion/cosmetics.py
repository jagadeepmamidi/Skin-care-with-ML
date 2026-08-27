"""Source 1 — historical Sephora cosmetics.csv → Bronze."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pandas as pd

from skincare_platform.lake import Lake, partition_prefix, write_json, write_jsonl
from skincare_platform.lineage import Lineage, attach_lineage, make_batch_id, stable_product_id
from skincare_platform.quality.quarantine import quarantine_records, split_valid_invalid
from skincare_platform.transforms import (
    is_valid_price,
    is_valid_rating,
    normalize_brand,
    normalize_category,
    to_float,
    to_int_flag,
)

SOURCE = "sephora_dataset"
HASH_FIELDS = ["product_id", "brand", "product_name", "price", "ingredients"]


def load_cosmetics_csv(path: Path) -> pd.DataFrame:
    frame = pd.read_csv(path, encoding="utf-8-sig")
    frame.columns = [c.replace("\ufeff", "").strip() for c in frame.columns]
    return frame


def row_to_record(row: dict[str, Any]) -> dict[str, Any]:
    brand = str(row.get("Brand") or "").strip()
    name = str(row.get("Name") or "").strip()
    price = to_float(row.get("Price"))
    rating = to_float(row.get("Rank"))
    return {
        "product_id": stable_product_id(brand, name) if brand and name else None,
        "brand": brand,
        "brand_normalized": normalize_brand(brand),
        "product_name": name,
        "category": normalize_category(row.get("Label")),
        "price": price,
        "rating": rating,
        "ingredients": row.get("Ingredients"),
        "combination": to_int_flag(row.get("Combination")),
        "dry": to_int_flag(row.get("Dry")),
        "normal": to_int_flag(row.get("Normal")),
        "oily": to_int_flag(row.get("Oily")),
        "sensitive": to_int_flag(row.get("Sensitive")),
        "currency": "USD",
        "retailer": "Sephora",
    }


def validate_product(record: dict[str, Any]) -> list[str]:
    reasons: list[str] = []
    if record.get("product_id") is None:
        reasons.append("product_id_null")
    if not record.get("brand"):
        reasons.append("brand_null")
    if not record.get("product_name"):
        reasons.append("product_name_null")
    if not is_valid_price(record.get("price")):
        reasons.append("invalid_price")
    if not is_valid_rating(record.get("rating")):
        reasons.append("invalid_rating")
    if not record.get("ingredients"):
        reasons.append("ingredients_null")
    return reasons


def inject_bad_rows(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Deterministic malformed rows so quarantine is demonstrable."""
    poison = [
        {
            "product_id": None,
            "brand": "BAD DATA CO",
            "brand_normalized": "Bad Data Co",
            "product_name": "Null ID Cream",
            "category": "Moisturizer",
            "price": 18.0,
            "rating": 4.0,
            "ingredients": "Water",
            "combination": 1,
            "dry": 1,
            "normal": 1,
            "oily": 1,
            "sensitive": 1,
            "currency": "USD",
            "retailer": "Sephora",
        },
        {
            "product_id": 1,
            "brand": "BAD DATA CO",
            "brand_normalized": "Bad Data Co",
            "product_name": "Negative Price Serum",
            "category": "Treatment",
            "price": -100.0,
            "rating": 4.2,
            "ingredients": "Water, Glycerin",
            "combination": 1,
            "dry": 0,
            "normal": 1,
            "oily": 1,
            "sensitive": 0,
            "currency": "USD",
            "retailer": "Sephora",
        },
        {
            "product_id": 2,
            "brand": "BAD DATA CO",
            "brand_normalized": "Bad Data Co",
            "product_name": "Impossible Rating Mask",
            "category": "Face Mask",
            "price": 22.0,
            "rating": 20.0,
            "ingredients": "Kaolin",
            "combination": 0,
            "dry": 1,
            "normal": 1,
            "oily": 0,
            "sensitive": 1,
            "currency": "USD",
            "retailer": "Sephora",
        },
    ]
    return records + poison


def ingest_cosmetics(
    lake: Lake,
    csv_path: Path,
    ingested_at: datetime | None = None,
    include_bad_rows: bool = True,
) -> dict[str, Any]:
    when = ingested_at or datetime.now(UTC)
    lineage = Lineage(
        source=SOURCE,
        ingested_at=when.replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        batch_id=make_batch_id("cosmetics", when),
        file_name=csv_path.name,
    )
    frame = load_cosmetics_csv(csv_path)
    records = [row_to_record(row) for row in frame.to_dict(orient="records")]
    if include_bad_rows:
        records = inject_bad_rows(records)
    decorated = [attach_lineage(rec, lineage, HASH_FIELDS) for rec in records]
    valid, invalid = split_valid_invalid(decorated, validate_product, lineage.batch_id)
    quarantine_key = quarantine_records(lake, "invalid_products", lineage.batch_id, invalid)

    prefix = partition_prefix("bronze", "cosmetics", when, extra=f"batch_id={lineage.batch_id}")
    bronze_key = f"{prefix}/products.jsonl"
    write_jsonl(lake, bronze_key, valid)
    write_json(
        lake,
        f"{prefix}/_manifest.json",
        {
            "dataset": "cosmetics",
            "source": SOURCE,
            "batch_id": lineage.batch_id,
            "ingested_at": lineage.ingested_at,
            "file_name": csv_path.name,
            "schema_version": lineage.schema_version,
            "row_count": len(valid),
            "quarantine_count": len(invalid),
            "quarantine_key": quarantine_key,
            "bronze_key": bronze_key,
        },
    )
    return {
        "batch_id": lineage.batch_id,
        "bronze_key": bronze_key,
        "row_count": len(valid),
        "quarantine_count": len(invalid),
        "quarantine_key": quarantine_key,
        "ingested_at": lineage.ingested_at,
    }
