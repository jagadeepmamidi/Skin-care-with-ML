"""End-to-end batch orchestration used by CLI and Airflow."""

from __future__ import annotations

import json
import os
import subprocess
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pandas as pd

from skincare_platform.config import Settings, get_settings
from skincare_platform.generators.events import generate_events, write_events
from skincare_platform.generators.pricing import generate_price_history, write_price_history
from skincare_platform.ingestion.cosmetics import (
    ingest_cosmetics,
    load_cosmetics_csv,
    row_to_record,
)
from skincare_platform.ingestion.events import ingest_events
from skincare_platform.ingestion.pricing import ingest_pricing
from skincare_platform.ingestion.product_api import ingest_product_api
from skincare_platform.lake import Lake, get_lake, load_watermarks, save_watermarks
from skincare_platform.lineage import make_batch_id
from skincare_platform.ml.features import export_ml_features, write_gold_ml_parquet
from skincare_platform.quality.expectations import load_suite, persist_suite_result, run_suite
from skincare_platform.spark.bronze_to_silver import run_bronze_to_silver
from skincare_platform.transforms import is_valid_price, is_valid_rating
from skincare_platform.warehouse.load import (
    load_silver_to_duckdb,
    load_watermark,
    record_pipeline_run,
    upsert_watermark,
)


@dataclass
class PipelineResult:
    run_id: str
    steps: dict[str, Any] = field(default_factory=dict)
    success: bool = True

    def as_dict(self) -> dict[str, Any]:
        return {"run_id": self.run_id, "success": self.success, "steps": self.steps}


def _product_frame(csv_path: Path) -> pd.DataFrame:
    raw = load_cosmetics_csv(csv_path)
    records = [row_to_record(row) for row in raw.to_dict(orient="records")]
    frame = pd.DataFrame(records)
    frame = frame[frame["product_id"].notna()]
    frame = frame[frame["price"].map(is_valid_price)]
    frame = frame[frame["rating"].map(is_valid_rating)]
    return frame


def generate_synthetic(
    settings: Settings,
    event_count: int,
    price_days: int,
    force: bool = False,
) -> dict[str, str]:
    products = _product_frame(settings.raw_csv_path)
    gen_root = settings.generated_root
    prices_path = gen_root / "price_history.parquet"
    events_path = gen_root / "events.parquet"
    if force or not prices_path.exists():
        write_price_history(generate_price_history(products, days=price_days), prices_path)
    if force or not events_path.exists():
        write_events(generate_events(products, n_events=event_count, days=price_days), events_path)
    return {"prices": str(prices_path), "events": str(events_path)}


def ingest_all(settings: Settings, lake: Lake | None = None, incremental: bool = True) -> dict[str, Any]:
    lake = lake or get_lake(settings)
    marks = load_watermarks(lake)
    price_wm = marks.get("pricing", {}).get("last_timestamp") if incremental else None
    event_wm = marks.get("events", {}).get("last_timestamp") if incremental else None
    if incremental:
        price_wm = price_wm or load_watermark(settings, "pricing")
        event_wm = event_wm or load_watermark(settings, "events")

    cosmetics = ingest_cosmetics(lake, settings.raw_csv_path)
    api = ingest_product_api(lake, settings)
    prices_path = settings.generated_root / "price_history.parquet"
    events_path = settings.generated_root / "events.parquet"
    pricing = ingest_pricing(lake, prices_path, watermark=price_wm)
    events = ingest_events(lake, events_path, watermark=event_wm)

    if pricing.get("max_timestamp"):
        marks["pricing"] = {
            "last_timestamp": pricing["max_timestamp"],
            "last_batch_id": pricing["batch_id"],
        }
        upsert_watermark(settings, "pricing", pricing["max_timestamp"], pricing["batch_id"])
    if events.get("max_timestamp"):
        marks["events"] = {
            "last_timestamp": events["max_timestamp"],
            "last_batch_id": events["batch_id"],
        }
        upsert_watermark(settings, "events", events["max_timestamp"], events["batch_id"])
    save_watermarks(lake, marks)
    return {"cosmetics": cosmetics, "product_api": api, "pricing": pricing, "events": events}


def run_quality(settings: Settings, lake: Lake, run_id: str) -> dict[str, Any]:
    import pyarrow.parquet as pq

    results = {}
    mapping = {
        "products_silver": settings.quality_dir / "products_silver.json",
        "events_silver": settings.quality_dir / "events_silver.json",
        "prices_silver": settings.quality_dir / "prices_silver.json",
    }
    frames = {
        "products_silver": settings.lake_root_resolved() / "silver" / "products",
        "events_silver": settings.lake_root_resolved() / "silver" / "events",
        "prices_silver": settings.lake_root_resolved() / "silver" / "prices",
    }
    for name, suite_path in mapping.items():
        if not suite_path.exists():
            continue
        table = pq.read_table(frames[name])
        frame = table.to_pandas()
        suite = load_suite(suite_path)
        result = run_suite(frame, suite)
        persist_suite_result(lake, result, run_id)
        results[name] = result.as_dict()
        if not result.success:
            raise RuntimeError(f"Quality gate failed: {name} {result.as_dict()}")
    return results


def run_dbt(settings: Settings, extra_args: list[str] | None = None) -> dict[str, Any]:
    env = os.environ.copy()
    env["DUCKDB_PATH"] = str(settings.duckdb_path_resolved())
    env["DBT_TARGET"] = "duckdb"
    cmd = [
        "dbt",
        "run",
        "--project-dir",
        str(settings.dbt_project_dir),
        "--profiles-dir",
        str(settings.dbt_project_dir),
    ]
    if extra_args:
        cmd.extend(extra_args)
    proc = subprocess.run(cmd, env=env, check=False, capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError(f"dbt run failed:\n{proc.stdout}\n{proc.stderr}")
    test_cmd = [
        "dbt",
        "test",
        "--project-dir",
        str(settings.dbt_project_dir),
        "--profiles-dir",
        str(settings.dbt_project_dir),
    ]
    test_proc = subprocess.run(test_cmd, env=env, check=False, capture_output=True, text=True)
    snap_cmd = [
        "dbt",
        "snapshot",
        "--project-dir",
        str(settings.dbt_project_dir),
        "--profiles-dir",
        str(settings.dbt_project_dir),
    ]
    snap_proc = subprocess.run(snap_cmd, env=env, check=False, capture_output=True, text=True)
    return {
        "run_returncode": proc.returncode,
        "test_returncode": test_proc.returncode,
        "snapshot_returncode": snap_proc.returncode,
        "run_stdout": proc.stdout[-4000:],
        "test_stdout": test_proc.stdout[-4000:],
        "snapshot_stdout": snap_proc.stdout[-2000:],
        "test_stderr": test_proc.stderr[-2000:],
    }


def run_pipeline(
    settings: Settings | None = None,
    event_count: int | None = None,
    price_days: int | None = None,
    incremental: bool = True,
    skip_dbt: bool = False,
    skip_spark: bool = False,
    regenerate: bool = False,
) -> PipelineResult:
    settings = settings or get_settings()
    run_id = make_batch_id("pipeline")
    result = PipelineResult(run_id=run_id)
    lake = get_lake(settings)
    started = datetime.now(UTC).isoformat()
    try:
        result.steps["generate"] = generate_synthetic(
            settings,
            event_count=event_count or settings.event_count,
            price_days=price_days or settings.price_days,
            force=regenerate,
        )
        result.steps["ingest"] = ingest_all(settings, lake, incremental=incremental)
        if not skip_spark:
            result.steps["silver"] = run_bronze_to_silver(settings.lake_root_resolved())
            result.steps["quality"] = run_quality(settings, lake, run_id)
        result.steps["warehouse"] = load_silver_to_duckdb(settings, settings.lake_root_resolved())
        if not skip_dbt:
            result.steps["dbt"] = run_dbt(settings)
        result.steps["ml_features"] = export_ml_features(settings)
        write_gold_ml_parquet(settings, lake)
        record_pipeline_run(settings, run_id, "success", result.as_dict())
        result.success = True
    except Exception as exc:
        result.success = False
        result.steps["error"] = f"{type(exc).__name__}: {exc}"
        record_pipeline_run(settings, run_id, "failed", result.as_dict())
        raise
    result.steps["started_at"] = started
    result.steps["finished_at"] = datetime.now(UTC).isoformat()
    manifest_path = settings.lake_root_resolved() / "_state" / "last_pipeline_run.json"
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(result.as_dict(), indent=2, default=str))
    return result
