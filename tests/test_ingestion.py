"""Ingestion + incremental watermark tests (no Spark)."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from skincare_platform.generators.events import generate_events, write_events
from skincare_platform.generators.pricing import generate_price_history, write_price_history
from skincare_platform.ingestion.cosmetics import (
    ingest_cosmetics,
    load_cosmetics_csv,
    row_to_record,
)
from skincare_platform.ingestion.events import ingest_events
from skincare_platform.ingestion.pricing import ingest_pricing
from skincare_platform.lake import LocalLake


@pytest.fixture
def csv_path() -> Path:
    return Path("cosmetics.csv")


def test_cosmetics_ingestion_quarantines_bad_rows(tmp_path: Path, csv_path: Path):
    lake = LocalLake(tmp_path / "lake")
    result = ingest_cosmetics(lake, csv_path, include_bad_rows=True)
    assert result["row_count"] >= 1400
    assert result["quarantine_count"] >= 3
    assert lake.exists(result["bronze_key"])
    qkeys = lake.list_keys("quarantine/")
    assert any("invalid_products" in k for k in qkeys)


def test_lineage_columns_present(tmp_path: Path, csv_path: Path):
    lake = LocalLake(tmp_path / "lake")
    result = ingest_cosmetics(lake, csv_path, include_bad_rows=False)
    from skincare_platform.lake import read_jsonl

    rows = read_jsonl(lake, result["bronze_key"])
    sample = rows[0]
    for col in ["source", "ingested_at", "batch_id", "file_name", "record_hash", "schema_version", "product_id"]:
        assert col in sample
    assert sample["source"] == "sephora_dataset"


def test_incremental_event_ingest(tmp_path: Path, csv_path: Path):
    lake = LocalLake(tmp_path / "lake")
    products = pd.DataFrame([row_to_record(r) for r in load_cosmetics_csv(csv_path).to_dict(orient="records")])
    products = products.dropna(subset=["product_id"])
    events_path = tmp_path / "events.parquet"
    frame = generate_events(products, n_events=2000, days=10, include_bad_rows=True)
    write_events(frame, events_path)

    first = ingest_events(lake, events_path, watermark=None)
    assert first["row_count"] >= 1900
    second = ingest_events(lake, events_path, watermark=first["max_timestamp"])
    assert second["row_count"] == 0


def test_price_generation_has_time_dimension(tmp_path: Path, csv_path: Path):
    products = pd.DataFrame([row_to_record(r) for r in load_cosmetics_csv(csv_path).head(20).to_dict(orient="records")])
    prices = generate_price_history(products, days=14, include_bad_rows=False)
    assert prices["timestamp"].nunique() >= 14
    assert set(["product_id", "timestamp", "price", "retailer", "currency", "discount"]).issubset(prices.columns)
    path = write_price_history(prices, tmp_path / "prices.parquet")
    lake = LocalLake(tmp_path / "lake")
    result = ingest_pricing(lake, path)
    assert result["row_count"] == len(prices)
