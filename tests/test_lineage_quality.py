"""Unit tests for lineage, transforms, quarantine, and quality gates."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from skincare_platform.lake import LocalLake, load_watermarks, save_watermarks
from skincare_platform.lineage import Lineage, attach_lineage, record_hash, stable_product_id
from skincare_platform.quality.expectations import run_suite
from skincare_platform.quality.quarantine import split_valid_invalid
from skincare_platform.transforms import (
    is_valid_price,
    is_valid_rating,
    normalize_brand,
    tokenize_ingredients,
)


def test_stable_product_id_is_deterministic():
    a = stable_product_id("LA MER", "Crème de la Mer")
    b = stable_product_id("la mer", "Crème de la Mer")
    assert a == b
    assert isinstance(a, int)


def test_record_hash_changes_with_payload():
    h1 = record_hash({"product_id": 1, "price": 10})
    h2 = record_hash({"product_id": 1, "price": 11})
    assert h1 != h2
    assert len(h1) == 64


def test_attach_lineage_fields():
    lineage = Lineage(
        source="sephora_dataset",
        ingested_at="2026-08-27T00:00:00Z",
        batch_id="batch_cosmetics_20260827_000000",
        file_name="cosmetics.csv",
    )
    out = attach_lineage({"product_id": 1, "brand": "X", "price": 10}, lineage, ["product_id", "price"])
    assert out["source"] == "sephora_dataset"
    assert out["schema_version"] == "1.0.0"
    assert out["record_hash"]


def test_tokenize_and_normalize():
    tokens = tokenize_ingredients("Water, Glycerin, Niacinamide, please visit the website")
    assert "Water" in tokens
    assert "Glycerin" in tokens
    assert "Niacinamide" in tokens
    assert normalize_brand("LA MER") == "La Mer"
    assert is_valid_price(12.5)
    assert not is_valid_price(-100)
    assert not is_valid_rating(20)


def test_quarantine_split():
    records = [
        {"product_id": 1, "price": 10},
        {"product_id": None, "price": 10},
        {"product_id": 2, "price": -5},
    ]

    def validator(row):
        reasons = []
        if row["product_id"] is None:
            reasons.append("product_id_null")
        if row["price"] < 0:
            reasons.append("invalid_price")
        return reasons

    valid, invalid = split_valid_invalid(records, validator, "run1")
    assert len(valid) == 1
    assert len(invalid) == 2
    assert "product_id_null" in invalid[0]["reason"]


def test_watermarks_roundtrip(tmp_path: Path):
    lake = LocalLake(tmp_path)
    save_watermarks(lake, {"events": {"last_timestamp": "2026-08-20T00:00:00Z"}})
    marks = load_watermarks(lake)
    assert marks["events"]["last_timestamp"].startswith("2026-08-20")


def test_quality_suite_price_gate():
    frame = pd.DataFrame({"product_id": [1, 2], "price": [10.0, 12.0], "rating": [4.0, 4.2]})
    suite = {
        "expectation_suite_name": "t",
        "expectations": [
            {"expectation_type": "expect_column_values_to_not_be_null", "kwargs": {"column": "product_id"}},
            {"expectation_type": "expect_column_values_to_be_between", "kwargs": {"column": "price", "min_value": 0, "max_value": 100}},
        ],
    }
    result = run_suite(frame, suite)
    assert result.success

    bad = pd.DataFrame({"product_id": [1, None], "price": [10.0, -4.0]})
    failed = run_suite(bad, suite)
    assert not failed.success
