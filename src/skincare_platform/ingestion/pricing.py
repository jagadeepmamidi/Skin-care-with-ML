"""Source 3 — synthetic / incremental price history → Bronze (vectorized)."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pandas as pd

from skincare_platform.lake import Lake, partition_prefix, write_json, write_parquet
from skincare_platform.lineage import Lineage, make_batch_id, record_hash
from skincare_platform.quality.quarantine import quarantine_records
from skincare_platform.transforms import is_valid_price, to_float

SOURCE = "price_history"


def ingest_pricing(
    lake: Lake,
    parquet_path: Path,
    ingested_at: datetime | None = None,
    watermark: str | None = None,
) -> dict[str, Any]:
    when = ingested_at or datetime.now(UTC)
    lineage = Lineage(
        source=SOURCE,
        ingested_at=when.replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        batch_id=make_batch_id("pricing", when),
        file_name=parquet_path.name,
    )
    frame = pd.read_parquet(parquet_path)
    if watermark:
        frame = frame[frame["timestamp"] > watermark].copy()
    else:
        frame = frame.copy()
    frame["timestamp"] = frame["timestamp"].astype(str)
    frame["price"] = frame["price"].map(to_float)
    frame["discount"] = frame["discount"].map(lambda v: to_float(v, 0.0))
    frame["source"] = lineage.source
    frame["ingested_at"] = lineage.ingested_at
    frame["batch_id"] = lineage.batch_id
    frame["file_name"] = lineage.file_name
    frame["schema_version"] = lineage.schema_version
    frame["record_hash"] = [
        record_hash(
            {
                "product_id": rec["product_id"],
                "timestamp": rec["timestamp"],
                "retailer": rec["retailer"],
                "price": rec["price"],
            }
        )
        for rec in frame[["product_id", "timestamp", "retailer", "price"]].to_dict(orient="records")
    ]
    invalid_mask = frame["product_id"].isna() | ~frame["price"].map(is_valid_price) | frame["timestamp"].eq("")
    invalid_rows = []
    if invalid_mask.any():
        for rec in frame.loc[invalid_mask].to_dict(orient="records"):
            reasons = []
            if rec.get("product_id") is None or pd.isna(rec.get("product_id")):
                reasons.append("product_id_null")
            if not is_valid_price(rec.get("price")):
                reasons.append("invalid_price")
            invalid_rows.append(
                {
                    "reason": ",".join(reasons) or "invalid_price",
                    "reasons": reasons,
                    "pipeline_run_id": lineage.batch_id,
                    "timestamp": lineage.ingested_at,
                    "original_record": rec,
                }
            )
    valid = frame.loc[~invalid_mask].copy()
    quarantine_key = quarantine_records(lake, "invalid_prices", lineage.batch_id, invalid_rows)
    prefix = partition_prefix("bronze", "pricing", when, extra=f"batch_id={lineage.batch_id}")
    bronze_key = f"{prefix}/prices.parquet"
    write_parquet(lake, bronze_key, valid)
    max_ts = str(valid["timestamp"].max()) if len(valid) else watermark
    write_json(
        lake,
        f"{prefix}/_manifest.json",
        {
            "dataset": "pricing",
            "source": SOURCE,
            "batch_id": lineage.batch_id,
            "ingested_at": lineage.ingested_at,
            "watermark": watermark,
            "row_count": int(len(valid)),
            "quarantine_count": int(invalid_mask.sum()),
            "quarantine_key": quarantine_key,
            "max_timestamp": max_ts,
            "bronze_key": bronze_key,
        },
    )
    return {
        "batch_id": lineage.batch_id,
        "bronze_key": bronze_key,
        "row_count": int(len(valid)),
        "quarantine_count": int(invalid_mask.sum()),
        "max_timestamp": max_ts,
        "ingested_at": lineage.ingested_at,
    }
