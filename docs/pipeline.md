# Pipeline runbook

## Daily batch (Airflow DAG `skincare_medallion_pipeline`)

1. `validate_sources` — cosmetics.csv must exist.
2. Parallel ingest:
   - `ingest_csv` historical Sephora extract
   - `ingest_api` local FastAPI + optional Makeup API
   - `ingest_events` synthetic price history + customer events (watermarked)
3. `spark_clean` Bronze JSONL → Silver Parquet (dedup, types, ingredient explosion, event aggregations)
4. Quality suites in `data_quality/expectations/` — failure stops the DAG
5. `dbt run` + `dbt test` + `dbt snapshot` (SCD Type 2 on products)
6. Gold ML feature table → recommendation engine
7. Power BI CSV export

## Incremental loading

Watermarks live in:

- lake `_state/watermarks.json`
- warehouse `meta.watermarks`

Events and prices only extract `timestamp > last_processed_timestamp`.

Re-running the same generated files after a successful run ingests **zero** new incremental rows (idempotent).

## Dead-letter

Malformed bronze records are written to:

```
quarantine/invalid_products/batch_id=.../invalid.jsonl
quarantine/invalid_prices/...
quarantine/invalid_events/...
```

Each row includes `reason`, `pipeline_run_id`, `timestamp`, and `original_record`.

## Backfill

Trigger DAG `skincare_transformation` with catchup enabled, or:

```bash
python -m skincare_platform.cli run-pipeline --full-refresh --regenerate
```

## Streaming (optional)

```bash
docker compose --profile streaming up -d
python -c "from skincare_platform.streaming import publish_microbatch; print(publish_microbatch(500, sink='both'))"
```
