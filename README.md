# Skincare Intelligence Data Platform

End-to-end **data engineering + analytics engineering + ML** platform built on the original Sephora cosmetics catalog (1,472 products). The notebook recommendation engine is unchanged in spirit: it now reads a **Gold feature table**, not `cosmetics.csv`.

```text
cosmetics.csv + Product API + price history + events
        → Python ingestion (lineage, idempotent batches)
        → MinIO / local S3-style lake (Bronze)
        → PySpark (Silver Parquet, ingredient explosion, 1M-event aggregations)
        → dbt star schema + SCD Type 2 snapshot (Gold)
        → DuckDB / PostgreSQL warehouse
        → Streamlit / Power BI  +  content-based recommendations
```

Quality gates (GX-style suites + dbt tests) quarantine bad rows instead of crashing. Incremental watermarks mean reruns do not reload the full event history.

## Why this is not "CSV → Pandas → Postgres"

| Capability | Where it lives |
| --- | --- |
| Multi-source ingestion + lineage (`source`, `batch_id`, `record_hash`, `schema_version`) | `src/skincare_platform/ingestion/` |
| Medallion lake with Hive-style partitions | `data/lake/{bronze,silver,gold,quarantine}` |
| Spark ETL on large synthetic events | `src/skincare_platform/spark/` |
| Dimensional model, incremental merge, SCD2 | `dbt/` |
| Orchestration, retries, XCom, backfills | `airflow/dags/` |
| Data quality + dead-letter | `data_quality/` + `quarantine/` |
| ML as a downstream consumer | `ml/recommendation/` + `marts.gold_ml_product_features` |
| One-command local platform | `docker-compose.yml` |
| CI | `.github/workflows/ci.yml` |
| Optional Kafka micro-batch | `src/skincare_platform/streaming/` |

## Quick start (local, no Docker)

Python 3.11+ and a JDK 17+ (for Spark).

```bash
python -m pip install -e ".[dev,dbt,dashboard]"
cp .env.example .env
make smoke          # 5k events, tests
# or the full-sized batch:
make pipeline EVENTS=1000000
make dashboard      # http://localhost:8501
python -m skincare_platform.cli recommend "Crème de la Mer"
```

`make pipeline` will:

1. Generate price history (90 days) and customer events
2. Ingest four sources into Bronze JSON/JSONL with lineage
3. Quarantine invalid prices / ratings / null ids
4. Run PySpark Bronze → Silver
5. Enforce data-quality suites
6. Load DuckDB + `dbt run/test/snapshot`
7. Publish Gold ML features

## Docker Compose

```bash
docker compose up --build -d
# Airflow UI  http://localhost:8080  (airflow / airflow)
# MinIO       http://localhost:9001  (minioadmin / minioadmin)
# Product API http://localhost:8088/v1/products
# Dashboard   http://localhost:8501
```

Streaming profile (Redpanda):

```bash
docker compose --profile streaming up -d
```

## Repository map

```text
ingestion/ spark/ dbt/ airflow/ data_quality/ warehouse/
data_generator logic → src/skincare_platform/generators/
ml/recommendation/          Gold consumer
dashboards/                 Streamlit + Power BI spec
infrastructure/terraform/   optional AWS S3 + CloudWatch
docs/                       architecture + pipeline runbook
```

The original files `cosmetics.csv` and `m.ipynb` are kept. Prefer `data/raw/cosmetics.csv` for new work.

## Resume bullet (only after you have run this repo)

> Engineered a containerized batch (+ optional streaming) skincare data platform with Python, Airflow, PySpark, dbt, MinIO/S3 and Parquet. Implemented Bronze/Silver/Gold processing, incremental ETL, a Kimball star schema with SCD Type 2, automated quality gates and dead-letter quarantine, and Gold ML features that power a content-based recommendation engine and analytics dashboards.

## License / data

Historical product rows come from the public Sephora cosmetics ingredient dataset used in the original project. Synthetic prices and clickstream events are generated and are not real customer data.
