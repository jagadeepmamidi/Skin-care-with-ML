"""Export Gold marts as Power BI-ready CSVs."""

from __future__ import annotations

import duckdb

from skincare_platform.config import Settings

TABLES = [
    "marts.dim_product",
    "marts.dim_brand",
    "marts.dim_ingredient",
    "marts.dim_date",
    "marts.dim_customer",
    "marts.dim_retailer",
    "marts.fact_product_events",
    "marts.fact_price_history",
    "marts.fact_sales",
    "marts.gold_ml_product_features",
    "marts.gold_analytics_kpis",
]


def export_powerbi_csvs(settings: Settings) -> dict[str, str]:
    out_dir = settings.repo_root / "dashboards" / "powerbi" / "exports"
    out_dir.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(str(settings.duckdb_path_resolved()), read_only=True)
    written: dict[str, str] = {}
    try:
        for table in TABLES:
            name = table.split(".")[-1]
            path = out_dir / f"{name}.csv"
            con.execute(f"COPY (SELECT * FROM {table}) TO '{path.as_posix()}' (HEADER, DELIMITER ',')")
            written[name] = str(path)
    finally:
        con.close()
    return written
