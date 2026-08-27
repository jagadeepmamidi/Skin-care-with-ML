"""Load Silver parquet into DuckDB or PostgreSQL landing tables."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import duckdb

from skincare_platform.config import Settings

LANDING_TABLES = {
    "raw_products": "silver/products",
    "raw_ingredients": "silver/ingredients",
    "raw_product_ingredients": "silver/product_ingredients",
    "raw_prices": "silver/prices",
    "raw_events": "silver/events",
    "raw_product_activity": "silver/product_activity",
    "raw_event_daily": "silver/event_daily",
}

BOOTSTRAP_SQL = """
CREATE SCHEMA IF NOT EXISTS raw;
CREATE SCHEMA IF NOT EXISTS staging;
CREATE SCHEMA IF NOT EXISTS intermediate;
CREATE SCHEMA IF NOT EXISTS marts;
CREATE SCHEMA IF NOT EXISTS meta;

CREATE TABLE IF NOT EXISTS meta.watermarks (
    source_name VARCHAR PRIMARY KEY,
    last_timestamp VARCHAR,
    last_batch_id VARCHAR,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS meta.pipeline_runs (
    run_id VARCHAR PRIMARY KEY,
    started_at TIMESTAMP,
    finished_at TIMESTAMP,
    status VARCHAR,
    details JSON
);
"""


def connect_duckdb(path: Path) -> duckdb.DuckDBPyConnection:
    path.parent.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(str(path))
    con.execute(BOOTSTRAP_SQL)
    return con


def parquet_glob(lake_root: Path, relative: str) -> str:
    return str((lake_root / relative).as_posix()) + "/**/*.parquet"


def load_silver_to_duckdb(settings: Settings, lake_root: Path) -> dict[str, int]:
    con = connect_duckdb(settings.duckdb_path_resolved())
    counts: dict[str, int] = {}
    try:
        for table, relative in LANDING_TABLES.items():
            glob = parquet_glob(lake_root, relative)
            con.execute(f"CREATE OR REPLACE TABLE raw.{table} AS SELECT * FROM read_parquet('{glob}')")
            counts[table] = con.execute(f"SELECT COUNT(*) FROM raw.{table}").fetchone()[0]
        return counts
    finally:
        con.close()


def upsert_watermark(settings: Settings, source: str, timestamp: str | None, batch_id: str) -> None:
    if not timestamp:
        return
    con = connect_duckdb(settings.duckdb_path_resolved())
    try:
        con.execute(
            """
            INSERT INTO meta.watermarks (source_name, last_timestamp, last_batch_id, updated_at)
            VALUES (?, ?, ?, now())
            ON CONFLICT (source_name) DO UPDATE SET
              last_timestamp = excluded.last_timestamp,
              last_batch_id = excluded.last_batch_id,
              updated_at = now()
            """,
            [source, timestamp, batch_id],
        )
    finally:
        con.close()


def load_watermark(settings: Settings, source: str) -> str | None:
    path = settings.duckdb_path_resolved()
    if not path.exists():
        return None
    con = duckdb.connect(str(path))
    try:
        con.execute(BOOTSTRAP_SQL)
        row = con.execute(
            "SELECT last_timestamp FROM meta.watermarks WHERE source_name = ?",
            [source],
        ).fetchone()
        return row[0] if row else None
    finally:
        con.close()


def record_pipeline_run(settings: Settings, run_id: str, status: str, details: dict[str, Any]) -> None:
    import json

    con = connect_duckdb(settings.duckdb_path_resolved())
    try:
        con.execute(
            """
            INSERT OR REPLACE INTO meta.pipeline_runs (run_id, started_at, finished_at, status, details)
            VALUES (?, now(), now(), ?, ?::JSON)
            """,
            [run_id, status, json.dumps(details, default=str)],
        )
    finally:
        con.close()


def postgres_copy_from_duckdb(settings: Settings) -> None:
    """Optional: push DuckDB marts into Postgres after dbt."""
    con = connect_duckdb(settings.duckdb_path_resolved())
    try:
        con.execute("INSTALL postgres; LOAD postgres;")
        con.execute(f"ATTACH '{settings.postgres_url}' AS pg (TYPE POSTGRES)")
        tables = con.execute(
            "SELECT table_schema, table_name FROM information_schema.tables "
            "WHERE table_schema IN ('marts', 'raw', 'meta')"
        ).fetchall()
        for schema, table in tables:
            con.execute(
                f"CREATE SCHEMA IF NOT EXISTS pg.{schema}; "
                f"CREATE OR REPLACE TABLE pg.{schema}.{table} AS SELECT * FROM {schema}.{table}"
            )
    finally:
        con.close()
