"""Integration test for the full medallion pipeline."""

from __future__ import annotations

from pathlib import Path

import pytest

from skincare_platform.config import Settings
from skincare_platform.ml.features import IngredientRecommender
from skincare_platform.orchestration.pipeline import run_pipeline


@pytest.mark.integration
def test_full_pipeline_and_recommender(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    repo = Path(__file__).resolve().parents[1]
    lake_root = tmp_path / "lake"
    duckdb_path = tmp_path / "wh" / "skincare.duckdb"
    monkeypatch.setenv("MAKEUP_API_ENABLED", "false")
    settings = Settings(
        lake_backend="local",
        lake_root=lake_root,
        duckdb_path=duckdb_path,
        makeup_api_enabled=False,
        repo_root=repo,
    )

    result = run_pipeline(
        settings,
        event_count=3000,
        price_days=8,
        incremental=False,
        regenerate=True,
    )
    assert result.success
    ingest = result.steps["ingest"]
    assert ingest["cosmetics"]["quarantine_count"] >= 3
    assert ingest["events"]["row_count"] >= 2900
    silver = result.steps["silver"]
    assert silver["products"]["products"] >= 1400
    assert silver["products"]["ingredients"] >= 100
    assert silver["events"]["events"] >= 2900
    assert (lake_root / "silver" / "products").exists()
    assert (lake_root / "gold" / "recommendations" / "ml_product_features.parquet").exists()
    recs = IngredientRecommender.from_settings(settings).recommend("Crème de la Mer", k=5)
    assert len(recs) == 5
    assert "similarity" in recs.columns
    assert "Crème de la Mer" not in set(recs["product_name"])
