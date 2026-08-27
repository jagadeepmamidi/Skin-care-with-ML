"""S3-compatible data lake (local filesystem, MinIO, or AWS S3)."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from io import BytesIO
from pathlib import Path
from typing import Any, Protocol

import orjson
import pandas as pd

from skincare_platform.config import Settings


class Lake(Protocol):
    def put_bytes(self, key: str, data: bytes, content_type: str = "application/octet-stream") -> str: ...
    def get_bytes(self, key: str) -> bytes: ...
    def exists(self, key: str) -> bool: ...
    def list_keys(self, prefix: str) -> list[str]: ...
    def uri(self, key: str) -> str: ...


@dataclass
class LocalLake:
    root: Path

    def __post_init__(self) -> None:
        self.root.mkdir(parents=True, exist_ok=True)

    def _path(self, key: str) -> Path:
        return self.root / key.lstrip("/")

    def put_bytes(self, key: str, data: bytes, content_type: str = "application/octet-stream") -> str:
        path = self._path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return self.uri(key)

    def get_bytes(self, key: str) -> bytes:
        return self._path(key).read_bytes()

    def exists(self, key: str) -> bool:
        return self._path(key).exists()

    def list_keys(self, prefix: str) -> list[str]:
        base = self._path(prefix)
        if not base.exists():
            return []
        if base.is_file():
            return [prefix.rstrip("/")]
        keys: list[str] = []
        for path in base.rglob("*"):
            if path.is_file():
                keys.append(str(path.relative_to(self.root)).replace("\\", "/"))
        return sorted(keys)

    def uri(self, key: str) -> str:
        return str(self._path(key))


class S3Lake:
    def __init__(
        self,
        bucket: str,
        endpoint_url: str | None,
        access_key: str,
        secret_key: str,
        region: str,
    ) -> None:
        import boto3
        from botocore.client import Config

        self.bucket = bucket
        self.endpoint_url = endpoint_url
        self._client = boto3.client(
            "s3",
            endpoint_url=endpoint_url or None,
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
            region_name=region,
            config=Config(signature_version="s3v4"),
        )
        self._ensure_bucket()

    def _ensure_bucket(self) -> None:
        try:
            self._client.head_bucket(Bucket=self.bucket)
        except Exception:
            kwargs: dict[str, Any] = {"Bucket": self.bucket}
            self._client.create_bucket(**kwargs)

    def put_bytes(self, key: str, data: bytes, content_type: str = "application/octet-stream") -> str:
        self._client.put_object(Bucket=self.bucket, Key=key, Body=data, ContentType=content_type)
        return self.uri(key)

    def get_bytes(self, key: str) -> bytes:
        resp = self._client.get_object(Bucket=self.bucket, Key=key)
        return resp["Body"].read()

    def exists(self, key: str) -> bool:
        try:
            self._client.head_object(Bucket=self.bucket, Key=key)
            return True
        except Exception:
            return False

    def list_keys(self, prefix: str) -> list[str]:
        keys: list[str] = []
        token = None
        while True:
            kwargs: dict[str, Any] = {"Bucket": self.bucket, "Prefix": prefix}
            if token:
                kwargs["ContinuationToken"] = token
            resp = self._client.list_objects_v2(**kwargs)
            for item in resp.get("Contents", []):
                keys.append(item["Key"])
            if not resp.get("IsTruncated"):
                break
            token = resp.get("NextContinuationToken")
        return keys

    def uri(self, key: str) -> str:
        if self.endpoint_url:
            return f"s3://{self.bucket}/{key}"
        return f"s3://{self.bucket}/{key}"


def get_lake(settings: Settings) -> Lake:
    backend = settings.lake_backend.lower()
    if backend in {"local", "file", "filesystem"}:
        return LocalLake(settings.lake_root_resolved())
    if backend in {"minio", "s3"}:
        return S3Lake(
            bucket=settings.s3_bucket,
            endpoint_url=settings.s3_endpoint_url if backend == "minio" else None,
            access_key=settings.s3_access_key,
            secret_key=settings.s3_secret_key,
            region=settings.aws_default_region,
        )
    raise ValueError(f"Unknown lake backend: {settings.lake_backend}")


def partition_prefix(layer: str, dataset: str, when: datetime, extra: str | None = None) -> str:
    parts = [
        layer,
        dataset,
        f"year={when:%Y}",
        f"month={when:%m}",
        f"day={when:%d}",
    ]
    if extra:
        parts.append(extra)
    return "/".join(parts)


def write_jsonl(lake: Lake, key: str, records: list[dict[str, Any]]) -> str:
    body = b"\n".join(orjson.dumps(row) for row in records) + (b"\n" if records else b"")
    return lake.put_bytes(key, body, content_type="application/x-ndjson")


def write_json(lake: Lake, key: str, payload: Any) -> str:
    return lake.put_bytes(key, orjson.dumps(payload, option=orjson.OPT_INDENT_2), "application/json")


def write_parquet(lake: Lake, key: str, frame: pd.DataFrame) -> str:
    buffer = BytesIO()
    frame.to_parquet(buffer, index=False)
    return lake.put_bytes(key, buffer.getvalue(), content_type="application/vnd.apache.parquet")


def read_jsonl(lake: Lake, key: str) -> list[dict[str, Any]]:
    text = lake.get_bytes(key).decode("utf-8")
    return [json.loads(line) for line in text.splitlines() if line.strip()]


def read_json(lake: Lake, key: str) -> Any:
    return orjson.loads(lake.get_bytes(key))


STATE_KEY = "_state/watermarks.json"


def load_watermarks(lake: Lake) -> dict[str, Any]:
    if not lake.exists(STATE_KEY):
        return {}
    return read_json(lake, STATE_KEY)


def save_watermarks(lake: Lake, watermarks: dict[str, Any]) -> str:
    return write_json(lake, STATE_KEY, watermarks)
