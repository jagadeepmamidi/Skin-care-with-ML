"""Runtime configuration for the Skincare Intelligence Data Platform."""

from __future__ import annotations

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    environment: str = "local"
    log_level: str = "INFO"

    repo_root: Path = Field(default_factory=lambda: Path(__file__).resolve().parents[2])

    lake_backend: str = "local"
    lake_root: Path = Path("./data/lake")
    s3_bucket: str = "skincare-lake"
    s3_endpoint_url: str | None = "http://localhost:9000"
    s3_access_key: str = "minioadmin"
    s3_secret_key: str = "minioadmin"
    aws_default_region: str = "us-east-1"

    warehouse_backend: str = "duckdb"
    duckdb_path: Path = Path("./data/warehouse/skincare.duckdb")
    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_db: str = "skincare"
    postgres_user: str = "skincare"
    postgres_password: str = "skincare"

    product_api_url: str = "http://localhost:8088"
    makeup_api_url: str = "http://makeup-api.herokuapp.com/api/v1/products.json"
    makeup_api_enabled: bool = True

    event_count: int = 1_000_000
    price_days: int = 90
    incremental: bool = True

    kafka_bootstrap_servers: str = "localhost:9092"
    kafka_topic_events: str = "skincare.events"

    schema_version: str = "1.0.0"

    @property
    def raw_csv_path(self) -> Path:
        candidate = self.repo_root / "data" / "raw" / "cosmetics.csv"
        if candidate.exists():
            return candidate
        return self.repo_root / "cosmetics.csv"

    @property
    def generated_root(self) -> Path:
        return self.repo_root / "data" / "generated"

    @property
    def dbt_project_dir(self) -> Path:
        return self.repo_root / "dbt"

    @property
    def quality_dir(self) -> Path:
        return self.repo_root / "data_quality" / "expectations"

    @property
    def postgres_url(self) -> str:
        return (
            f"postgresql://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    def lake_root_resolved(self) -> Path:
        root = self.lake_root
        if not root.is_absolute():
            root = self.repo_root / root
        return root

    def duckdb_path_resolved(self) -> Path:
        path = self.duckdb_path
        if not path.is_absolute():
            path = self.repo_root / path
        return path


def get_settings() -> Settings:
    return Settings()
