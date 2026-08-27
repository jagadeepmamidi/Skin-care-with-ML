# Project story: why this platform exists

This document is the interview narrative for the **Skincare Intelligence Data Platform**.
It covers the business problem, the engineering problems, why each technology was chosen, and how those choices show up in the code.

---

## 1. Problem statement

### Business problem

Buying skincare is hard. Ingredient lists are long, brands reuse similar formulas under different names, and a product that works for oily skin can irritate sensitive skin. The original project solved a **product-discovery** problem:

> Given a catalog of Sephora products and their ingredient lists, recommend similar products using chemistry (content-based similarity), not collaborative filtering.

That original work (`cosmetics.csv` + `m.ipynb`) is a valid data-science prototype. It is **not** a data platform.

### Engineering problem

The prototype had a single static file:

- 1,472 products
- one CSV
- the notebook reads the file directly
- no history, no events, no quality gates, no warehouse

That is fine for a class project. It fails as soon as the setting looks like a company:

| Real-world need | What the CSV notebook cannot do |
| --- | --- |
| Products arrive from more than one system | There is only one file |
| Prices change over time | Price is a single column, overwritten |
| Analysts need conversion / popularity | There are no customer events |
| Bad data should not poison ML | Invalid rows crash or silently pollute |
| Yesterday’s load should not reload everything | Full refresh only |
| Product category/price history must be reconstructable | No SCD / no audit log |
| Downstream ML should not own cleaning | The notebook *is* the cleaning |

The platform’s job is therefore:

> Ingest messy multi-source skincare data, keep a raw copy, clean it at scale, model it for analytics, prove it is trustworthy, and serve **the same Gold tables** to BI and to the recommendation engine.

The ML work is not thrown away. It becomes a **consumer** of `marts.gold_ml_product_features`.

---

## 2. What “good” looks like for this project

A strong data-engineering portfolio has to answer interviewer questions that a Pandas script cannot:

1. **Where did this row come from?** → lineage (`source`, `batch_id`, `record_hash`, `ingested_at`, `schema_version`)
2. **Can I reprocess last Tuesday?** → Bronze is immutable; partitions by date/batch
3. **What happens when price = -100?** → quarantine / dead-letter, pipeline continues
4. **Do you reload 100 million events every night?** → watermarks + incremental extract + dbt `merge`
5. **How do analysts query this?** → star schema, facts and dimensions, documented grain
6. **How did the product look in April vs August?** → SCD Type 2 snapshot
7. **Who runs this at 2am when it fails?** → Airflow retries, timeouts, task graph
8. **How do I know Gold is safe for ML?** → quality suites + dbt tests as gates
9. **Can someone else run it?** → Docker Compose + Makefile + CI

Every technology below exists to answer one of those questions. Nothing was added as decoration.

---

## 3. Architecture in one paragraph

Four sources (historical CSV, product API, synthetic price history, customer events) are ingested by Python with lineage metadata into a **Bronze** lake (local filesystem or MinIO/S3). **PySpark** turns Bronze into **Silver** Parquet: types, dedup, ingredient tokenization, event aggregations. **dbt** builds a Kimball star schema in **DuckDB** (local) or **PostgreSQL** (Compose/cloud): dimensions, facts, SCD2 snapshot, ML feature table. **Great-Expectations-style suites** and **dbt tests** fail the run if Gold is wrong. **Airflow** orchestrates the same Python functions the CLI uses. **Streamlit / Power BI exports** and the **recommendation engine** both read Gold.

```text
CSV + API + prices + events
        → ingest + lineage + quarantine
        → Bronze (raw, partitioned)
        → Spark Silver (Parquet, cleaned)
        → quality gate
        → dbt Gold (star schema + ML features)
        → dashboard  |  recommendations
```

---

## 4. Why each technology

### Python (ingestion, generators, orchestration glue)

**Problem:** sources do not look alike (CSV BOM, HTTP JSON, Parquet events). Someone has to attach lineage, hash records, and isolate poison rows before Spark.

**Why Python:** the industry default for ingestion micro-jobs; one language from extract → Spark submit → ML consumer. Pandas is used *only* where the data is small (1.5k products) or for vectorized event ingest. It is not the system of record.

**What we did:** `src/skincare_platform/ingestion/` writes Bronze. `lineage.py` stamps `source`, `batch_id`, `record_hash`, `schema_version`. Cosmetics CSV even has a UTF-8 BOM on `Label`; ingestion strips it so the pipeline does not depend on Excel’s export quirks.

### Multiple sources (not “just the CSV”)

**Problem:** Spark + a lake for 1,472 static rows is not defensible in an interview.

**Why four sources:**
- **Source 1 — `cosmetics.csv`:** historical snapshot (Sephora catalog). Real data.
- **Source 2 — Product API:** FastAPI catalog + optional Makeup API. Shows HTTP ingestion, schema drift, brand/name matching into the same `product_id` space.
- **Source 3 — Price history:** time dimension. Enables incremental ETL and `fact_price_history`.
- **Source 4 — Events:** volume. Views/cart/purchase/review give conversion, popularity, and a legitimate Spark workload.

Synthetic prices/events are labeled synthetic. That is honest and still production-shaped: watermarks, late-arriving poison rows, and 100k–1M scale.

### Object storage / data lake (local filesystem + MinIO, S3-compatible)

**Problem:** a database is a bad place to dump raw API payloads. You lose the original bytes, you pay to store junk, and you cannot replay.

**Why a lake, not “load CSV into Postgres”:**
- Bronze is **what arrived**, not what we wish arrived
- Hive-style partitions `year=/month=/day=/batch_id=` make date-scoped reprocessing cheap
- The same code path works locally (`LAKE_BACKEND=local`) and on MinIO/S3 (`boto3`)

**Why MinIO instead of AWS S3 first:** S3 APIs without a cloud bill. Terraform in `infrastructure/terraform/` is the later cutover (bucket + CloudWatch), not the day-one dependency.

**Why Parquet in Silver/Gold:** columnar, compressed, typed, Splittable for Spark. JSONL is used in Bronze for products because that is the native API/CSV shape.

### Medallion (Bronze → Silver → Gold)

**Problem:** if cleaning happens in the same step as loading, you cannot debug “did the API send garbage, or did our job corrupt it?”

| Layer | Contract | Why it exists |
| --- | --- | --- |
| **Bronze** | Raw + lineage. Almost no transforms. | Audit, replay, schema debugging |
| **Silver** | Deduped, typed, exploded ingredients, valid rows only | One clean entity per concept |
| **Gold** | Business grain: facts/dims/ML features | Analysts and models never see Bronze |
| **quarantine/** | Invalid rows + reason + run id | Fault tolerance without silent drops |

This is the standard lakehouse pattern interviewers expect in 2025–2026.

### Apache Spark (PySpark)

**Problem:** ingredient explosion and 100k–1M event aggregations are relational but large. Pandas would work for 1.5k products and fail the “why Spark?” question at event scale.

**Why Spark, not Pandas-for-everything:**
- Schema enforcement and windowed dedup (`row_number` over `product_id`)
- Ingredient tokenization UDF → `silver/ingredients` + `silver/product_ingredients`
- Event aggregations: views, add-to-cart, purchases, conversion rate, daily counts

**Why local `master=local[*]`:** the jobs are real Spark SQL. A cluster (Glue / EMR / Dataproc) is an infra swap, not a rewrite. `spark/*.py` entrypoints are spark-submit shaped.

**Honest constraint:** Spark is overkill for 1,472 products alone. That is why events exist. If asked, say: *“Spark is justified by the interaction dataset and by keeping one engine for batch; products ride the same job graph.”*

### dbt (SQL transformation layer)

**Problem:** Spark should not own dimensional modeling. Mixing “explode ingredients” with “what is a sale?” makes both harder to test.

**Why dbt:**
- Transformations are SQL files reviewers can read
- Built-in tests (`not_null`, `unique`, `accepted_values`, custom `non_negative`)
- Incremental `merge` on `dim_product`
- Snapshots for SCD Type 2 without hand-rolled history tables

Layers:

- `staging/` — 1:1 with Silver, light casts
- `intermediate/` — ingredient bridge, activity, price deltas
- `marts/` — dims, facts, `gold_ml_product_features`, KPIs

**Why this split (ingest vs dbt):** Airflow can retry Spark without rebuilding marts, and analysts can change a metric without touching Python.

### Star schema (Kimball) + SCD Type 2

**Problem:** a wide product table cannot answer “revenue by day and brand” or “what was this SKU’s category last quarter?” without copying columns everywhere.

**Why facts and dimensions:**

- `fact_product_events` grain = one interaction
- `fact_sales` grain = one `PURCHASE`
- `fact_price_history` grain = product × retailer × timestamp
- `dim_product` / `dim_brand` / `dim_ingredient` / `dim_date` / `dim_customer` / `dim_retailer`

That vocabulary (grain, natural vs surrogate key, conformed dimensions) is the DE interview core.

**Why SCD2:** price and category change. Overwriting Gold lies about the past. `dbt snapshot products_snapshot` keeps `dbt_valid_from` / `dbt_valid_to`. Current-row `dim_product` stays simple for ML; history lives in the snapshot.

**Keys:** natural key is `(brand, product_name)`; `product_id` is a stable MD5 integer so CSV and API rows can unify; `product_sk` versions a row.

### Incremental processing + watermarks

**Problem:** `DELETE + reload` does not survive a year of clickstream.

**How we solved it:**
- Generated events/prices are timestamped
- Ingest keeps `timestamp > last_processed_timestamp`
- State in lake `_state/watermarks.json` and warehouse `meta.watermarks`
- dbt `dim_product` is `incremental` + `merge`

A second run on the same files loads **zero** new event/price rows. That is the demo for idempotency.

### DuckDB (local warehouse) and PostgreSQL (Compose / production-shaped)

**Problem:** Gold must be SQL-queryable. A Spark warehouse-only design is painful for a laptop demo.

**Why DuckDB locally:** embedded, reads Parquet, zero daemon, CI-friendly. dbt-duckdb builds `marts.*` in `data/warehouse/skincare.duckdb`.

**Why PostgreSQL still exists:** it is what companies run. Compose starts Postgres; dbt has a `postgres` profile; `warehouse/schemas/init.sql` bootstraps `raw/staging/marts/meta`. Same models, different adapter.

**Why not Snowflake/BigQuery/Athena as the default:** cost and accounts. Athena is the documented cloud query engine over S3; it is optional, not required to understand the model.

### Data quality (GX-style suites + dbt tests + quarantine)

**Problem:** beginner DE repos skip tests. Then ML trains on `rating = 20` and `price = -100`.

**Why two layers:**
- **Ingest-time quarantine:** cheap, row-level, does not stop the batch. Poison rows are injected on purpose so this is demonstrable.
- **Silver suites** (`data_quality/expectations/*.json`): table-level gates (`product_id` unique, price ≥ 0, event types in set). Failure **stops** Gold.
- **dbt tests:** warehouse constraints after SQL. Catches model bugs Spark would not see.

The suite format matches Great Expectations (`expect_column_values_to_be_between`, etc.) so the idea is portable. The runner is in-process Python so CI does not need GX Cloud.

Quarantine payload: `reason`, `pipeline_run_id`, `timestamp`, `original_record`.

### Apache Airflow

**Problem:** `make pipeline` is not how production runs a 2am job with retries.

**Why Airflow (not cron, not only CLI):**
- Explicit DAG: validate → parallel ingest → Spark → dbt → quality → Gold → dashboard/ML
- `retries`, `execution_timeout`, `catchup`, `max_active_runs`, XCom
- Backfill DAG (`skincare_transformation`) separate from daily ingest
- Quality-only DAG to re-check without re-pulling sources

**Critical design:** DAG callables import `skincare_platform.*`. CLI and Airflow cannot drift.

### FastAPI product catalog

**Problem:** “API ingestion” that only reads a checked-in JSON file is fake.

**Why a small HTTP service:** Airflow/ingest can `GET /v1/products`. Docker Compose publishes `:8088`. Makeup API is optional (`MAKEUP_API_ENABLED`) so the pipeline still runs offline.

### Streamlit + Power BI exports

**Problem:** Gold with no visual is unfinished analytics engineering. Native Power BI `.pbix` cannot run in Linux CI.

**Why both:**
- Streamlit (`dashboards/app.py`) is the runnable demo (landscape, ingredients, pricing, behaviour)
- `make export-powerbi` writes CSVs + relationship/measure spec for Desktop

Same marts, two consumption paths.

### ML as a downstream consumer (scikit-learn)

**Problem:** if the recommender keeps reading `cosmetics.csv`, the platform is a side project.

**How we solved it:** `IngredientRecommender` loads `marts.gold_ml_product_features` (ingredients, skin flags, popularity_score from views/conversion). Count-vectorizer + cosine similarity is the original method, now on governed data.

That is the story: **DE produces features; ML consumes them.**

### Docker Compose

**Problem:** “install Airflow, Postgres, MinIO, JDK…” loses reviewers.

**Why Compose:** one `docker compose up` for Postgres, MinIO, product API, Airflow, dashboard. Redpanda is a profile so Kafka is not required to see batch value.

### GitHub Actions

**Problem:** untested DAGs rot.

**Why CI:** ruff → pytest (including Spark) → `run-pipeline` smoke → Docker image build. The same quality bar as the laptop demo.

### Kafka / Redpanda + streaming producer (optional)

**Problem:** batch-only platforms cannot talk about late events or clickstream.

**Why not Kafka as the main path:** the dimensional model had to be right first. Streaming is a second pipeline: synthetic events → Kafka or file micro-batch → Bronze `events_stream/` → same Silver/Gold later.

Redpanda in Compose is Kafka-protocol without ZooKeeper ops.

### Terraform / AWS stubs

**Problem:** putting “S3 + Glue + Athena” on a resume before anything is applied is the failure mode we avoided.

**What exists:** a real S3 bucket + prefix + CloudWatch log group module, documented as a **cutover**, not the runtime. Local MinIO remains the lake you can actually run.

---

## 5. Problems we hit in this dataset, and the fix

| Issue | Why it matters | Fix |
| --- | --- | --- |
| CSV header is `\ufeffLabel` (BOM) | Join/groupby on `Label` breaks | `encoding=utf-8-sig` in cosmetics ingest |
| No native `product_id` | Cannot join prices/events/API | Stable MD5 int from `(brand, name)` |
| Ingredients are one comma-separated string | Cannot count “niacinamide products” | Spark explode → ingredient dim + bridge |
| Brands are `LA MER` vs `La Mer` | Duplicate dimensions | `normalize_brand` aliases |
| Empty / junk ingredient tokens (`#NAME?`, “visit the website”) | Pollutes popularity | Tokenizer stop-list in `transforms.py` |
| Invalid price/rating/null id | Would break ML and averages | Quarantine at ingest; Silver filters; GX-style + dbt tests |
| 1,472 rows too small for Spark | Interview “why Spark?” | 100k–1M synthetic events with realistic type mix |
| Full reload of events | Not how production works | Watermarks; proven second ingest = 0 rows |
| Recommender could return the query product (identical Mini SKU at similarity 1.0) | Bad UX | Exclude self by index, not by “drop first sorted row” |
| dbt custom schemas became `main_marts` | Python expected `marts.*` | `generate_schema_name` macro uses the schema as-is |
| DuckDB `ON CONFLICT ... CURRENT_TIMESTAMP` binder error | Pipeline died after Spark succeeded | `now()` + `excluded.` columns |
| Row-wise JSONL for 1M events | Too slow / too much RAM | Vectorized Parquet Bronze for prices & events |
| Java 21 vs Spark 3.5 | Local session warnings/failures | Document JDK 17; CI uses Temurin 17 |

---

## 6. End-to-end flow (what actually runs)

`python -m skincare_platform.cli run-pipeline`:

1. Generate (or reuse) price history and events from the product catalog
2. Ingest four sources → Bronze + quarantine
3. Persist watermarks
4. Spark Bronze → Silver Parquet
5. Run Silver expectation suites (fail closed)
6. Load Silver into DuckDB `raw.*`
7. `dbt run` + `dbt test` + `dbt snapshot`
8. Export `gold_ml_product_features` for the recommender and lake `gold/recommendations/`

Airflow DAG `skincare_medallion_pipeline` is the same graph with retries.

---

## 7. What this is *not*, on purpose

- Not a fake “we used 15 logos.” Kafka and AWS are optional and labeled.
- Not a replacement for clinical dermatology advice.
- Synthetic events are not real customers. They exist to create volume, time, and conversion metrics.
- Power BI Desktop is not in CI; CSVs + a relationship spec are.

---

## 8. Interview answers (short)

**“Why not Pandas to Postgres?”**
Because we needed replayable raw data, multi-source lineage, incremental facts, SCD2, quality gates, and an ML contract. Postgres is the serving layer, not the lake.

**“Why Spark for 1.5k products?”**
Spark is the engine for events and ingredient explosion. Products use the same graph so we do not maintain two ETLs. Scale the event generator to 1M with `make pipeline EVENTS=1000000`.

**“How do you know data is good?”**
Poison rows are quarantined with reasons. Silver suites must pass before dbt. dbt tests must pass before ML export. A failed gate raises and the run is recorded in `meta.pipeline_runs`.

**“How would you productionize further?”**
Point `LAKE_BACKEND=s3` at the Terraform bucket, run dbt with the Postgres profile against RDS, replace local Spark with Glue/EMR using the same `bronze_to_silver.py`, and promote the Airflow DAG. Streaming already writes the same Bronze layout.

**“What is the ML integration?”**
`gold_ml_product_features` has ingredients, skin-type flags, price, rating, and a popularity score from event conversions. The cosine-similarity recommender reads that table, not `cosmetics.csv`.
