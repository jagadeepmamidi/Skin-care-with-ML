-- Warehouse bootstrap for Postgres (docker-compose).
CREATE SCHEMA IF NOT EXISTS raw;
CREATE SCHEMA IF NOT EXISTS staging;
CREATE SCHEMA IF NOT EXISTS intermediate;
CREATE SCHEMA IF NOT EXISTS marts;
CREATE SCHEMA IF NOT EXISTS meta;
CREATE SCHEMA IF NOT EXISTS snapshots;

CREATE TABLE IF NOT EXISTS meta.watermarks (
    source_name TEXT PRIMARY KEY,
    last_timestamp TEXT,
    last_batch_id TEXT,
    updated_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS meta.pipeline_runs (
    run_id TEXT PRIMARY KEY,
    started_at TIMESTAMPTZ,
    finished_at TIMESTAMPTZ,
    status TEXT,
    details JSONB
);
