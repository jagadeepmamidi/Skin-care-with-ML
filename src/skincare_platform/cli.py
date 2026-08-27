"""CLI for the Skincare Intelligence Data Platform."""

from __future__ import annotations

import argparse
import json
import sys

from skincare_platform.config import get_settings
from skincare_platform.lineage import utcnow_iso


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="skincare-platform")
    sub = parser.add_subparsers(dest="command", required=True)

    gen = sub.add_parser("generate", help="Generate synthetic prices and events")
    gen.add_argument("--events", type=int, default=None)
    gen.add_argument("--price-days", type=int, default=None)
    gen.add_argument("--force", action="store_true")

    sub.add_parser("ingest", help="Ingest all sources into Bronze")

    sub.add_parser("silver", help="Spark Bronze → Silver")
    sub.add_parser("gold", help="Load warehouse and run dbt")
    sub.add_parser("quality", help="Run data-quality suites")

    run = sub.add_parser("run-pipeline", help="Full medallion pipeline")
    run.add_argument("--events", type=int, default=None)
    run.add_argument("--price-days", type=int, default=None)
    run.add_argument("--full-refresh", action="store_true")
    run.add_argument("--skip-dbt", action="store_true")
    run.add_argument("--skip-spark", action="store_true")
    run.add_argument("--regenerate", action="store_true")

    rec = sub.add_parser("recommend", help="Recommend products from Gold features")
    rec.add_argument("product_name")
    rec.add_argument("-k", type=int, default=10)

    api = sub.add_parser("serve-api", help="Run local product API")
    api.add_argument("--host", default="0.0.0.0")
    api.add_argument("--port", type=int, default=8088)

    sub.add_parser("export-powerbi", help="Export Gold marts as CSV for Power BI")

    args = parser.parse_args(argv)
    settings = get_settings()

    if args.command == "generate":
        from skincare_platform.orchestration.pipeline import generate_synthetic

        out = generate_synthetic(
            settings,
            event_count=args.events or settings.event_count,
            price_days=args.price_days or settings.price_days,
            force=args.force,
        )
        print(json.dumps(out, indent=2))
        return 0

    if args.command == "ingest":
        from skincare_platform.orchestration.pipeline import ingest_all

        print(json.dumps(ingest_all(settings), indent=2, default=str))
        return 0

    if args.command == "silver":
        from skincare_platform.spark.bronze_to_silver import run_bronze_to_silver

        print(json.dumps(run_bronze_to_silver(settings.lake_root_resolved()), indent=2, default=str))
        return 0

    if args.command == "gold":
        from skincare_platform.orchestration.pipeline import run_dbt
        from skincare_platform.warehouse.load import load_silver_to_duckdb

        counts = load_silver_to_duckdb(settings, settings.lake_root_resolved())
        dbt = run_dbt(settings)
        print(json.dumps({"warehouse": counts, "dbt": dbt}, indent=2, default=str))
        return 0

    if args.command == "quality":
        from skincare_platform.lake import get_lake
        from skincare_platform.orchestration.pipeline import run_quality

        print(json.dumps(run_quality(settings, get_lake(settings), f"cli_{utcnow_iso()}"), indent=2))
        return 0

    if args.command == "run-pipeline":
        from skincare_platform.orchestration.pipeline import run_pipeline

        result = run_pipeline(
            settings,
            event_count=args.events,
            price_days=args.price_days,
            incremental=not args.full_refresh,
            skip_dbt=args.skip_dbt,
            skip_spark=args.skip_spark,
            regenerate=args.regenerate,
        )
        print(json.dumps(result.as_dict(), indent=2, default=str))
        return 0 if result.success else 1

    if args.command == "recommend":
        from skincare_platform.ml.features import IngredientRecommender

        recs = IngredientRecommender.from_settings(settings).recommend(args.product_name, k=args.k)
        print(recs.to_string(index=False))
        return 0

    if args.command == "serve-api":
        from skincare_platform.api.product_api import serve

        serve(host=args.host, port=args.port)
        return 0

    if args.command == "export-powerbi":
        from skincare_platform.dashboards.export import export_powerbi_csvs

        print(json.dumps(export_powerbi_csvs(settings), indent=2))
        return 0

    parser.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
