"""Dead-letter / quarantine writer for malformed records."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from skincare_platform.lake import Lake, write_jsonl
from skincare_platform.lineage import utcnow_iso


def quarantine_records(
    lake: Lake,
    dataset: str,
    batch_id: str,
    invalid: list[dict[str, Any]],
) -> str | None:
    if not invalid:
        return None
    key = f"quarantine/{dataset}/batch_id={batch_id}/invalid.jsonl"
    write_jsonl(lake, key, invalid)
    return key


def split_valid_invalid(
    records: list[dict[str, Any]],
    validator: Callable[[dict[str, Any]], list[str]],
    batch_id: str,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    valid: list[dict[str, Any]] = []
    invalid: list[dict[str, Any]] = []
    for record in records:
        reasons = validator(record)
        if reasons:
            invalid.append(
                {
                    "reason": ",".join(reasons),
                    "reasons": reasons,
                    "pipeline_run_id": batch_id,
                    "timestamp": utcnow_iso(),
                    "original_record": record,
                }
            )
        else:
            valid.append(record)
    return valid, invalid
