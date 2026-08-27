"""Batch lineage helpers: ids, hashes, ingestion timestamps."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from typing import Any

SCHEMA_VERSION = "1.0.0"


def utcnow() -> datetime:
    return datetime.now(UTC)


def utcnow_iso() -> str:
    return utcnow().replace(microsecond=0).isoformat().replace("+00:00", "Z")


def make_batch_id(source: str, when: datetime | None = None) -> str:
    ts = (when or utcnow()).strftime("%Y%m%d_%H%M%S")
    return f"batch_{source}_{ts}"


def record_hash(payload: dict[str, Any]) -> str:
    canonical = json.dumps(payload, sort_keys=True, default=str, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def stable_product_id(brand: str, name: str) -> int:
    """Deterministic 32-bit product id from brand + name."""
    digest = hashlib.md5(f"{brand.strip().lower()}|{name.strip().lower()}".encode()).hexdigest()
    return int(digest[:8], 16)


@dataclass(frozen=True)
class Lineage:
    source: str
    ingested_at: str
    batch_id: str
    file_name: str
    schema_version: str = SCHEMA_VERSION

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def attach_lineage(record: dict[str, Any], lineage: Lineage, hash_fields: list[str]) -> dict[str, Any]:
    hashed = {field: record.get(field) for field in hash_fields}
    out = dict(record)
    out.update(lineage.as_dict())
    out["record_hash"] = record_hash(hashed)
    return out
