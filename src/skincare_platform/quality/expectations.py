"""Great Expectations-style data quality gates over lake datasets."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pandas as pd

from skincare_platform.lake import Lake, write_json


@dataclass
class ExpectationResult:
    expectation_type: str
    kwargs: dict[str, Any]
    success: bool
    observed: Any
    message: str


@dataclass
class SuiteResult:
    suite_name: str
    success: bool
    results: list[ExpectationResult] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "suite_name": self.suite_name,
            "success": self.success,
            "results": [
                {
                    "expectation_type": r.expectation_type,
                    "kwargs": r.kwargs,
                    "success": r.success,
                    "observed": r.observed,
                    "message": r.message,
                }
                for r in self.results
            ],
        }


def _col(frame: pd.DataFrame, column: str) -> pd.Series:
    if column not in frame.columns:
        return pd.Series(dtype="object")
    return frame[column]


def evaluate_expectation(frame: pd.DataFrame, spec: dict[str, Any]) -> ExpectationResult:
    etype = spec["expectation_type"]
    kwargs = spec.get("kwargs", {})
    column = kwargs.get("column")

    if etype == "expect_table_row_count_to_be_between":
        n = len(frame)
        ok = kwargs.get("min_value", 0) <= n <= kwargs.get("max_value", 10**18)
        return ExpectationResult(etype, kwargs, ok, n, f"row_count={n}")

    if etype == "expect_column_to_exist":
        ok = column in frame.columns
        return ExpectationResult(etype, kwargs, ok, ok, f"column_exists={ok}")

    series = _col(frame, column) if column else pd.Series(dtype="object")

    if etype == "expect_column_values_to_not_be_null":
        nulls = int(series.isna().sum()) if len(series) else 0
        ok = nulls == 0
        return ExpectationResult(etype, kwargs, ok, nulls, f"nulls={nulls}")

    if etype == "expect_column_values_to_be_unique":
        dupes = int(series.duplicated().sum()) if len(series) else 0
        ok = dupes == 0
        return ExpectationResult(etype, kwargs, ok, dupes, f"duplicates={dupes}")

    if etype == "expect_column_values_to_be_between":
        numeric = pd.to_numeric(series, errors="coerce")
        lo, hi = kwargs.get("min_value"), kwargs.get("max_value")
        mask = numeric.notna()
        if lo is not None:
            mask &= numeric >= lo
        if hi is not None:
            mask &= numeric <= hi
        bad = int((~mask & series.notna()).sum()) if len(series) else 0
        ok = bad == 0
        return ExpectationResult(etype, kwargs, ok, bad, f"out_of_range={bad}")

    if etype == "expect_column_values_to_be_in_set":
        allowed = set(kwargs.get("value_set", []))
        bad = int((~series.isin(allowed) & series.notna()).sum()) if len(series) else 0
        ok = bad == 0
        return ExpectationResult(etype, kwargs, ok, bad, f"unexpected={bad}")

    if etype == "expect_column_pair_values_a_to_be_greater_than_b":
        a = pd.to_numeric(frame[kwargs["column_A"]], errors="coerce")
        b = pd.to_numeric(frame[kwargs["column_B"]], errors="coerce")
        bad = int((a < b).sum())
        ok = bad == 0
        return ExpectationResult(etype, kwargs, ok, bad, f"a_lt_b={bad}")

    return ExpectationResult(etype, kwargs, False, None, f"unknown expectation {etype}")


def load_suite(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def run_suite(frame: pd.DataFrame, suite: dict[str, Any]) -> SuiteResult:
    results = [evaluate_expectation(frame, spec) for spec in suite.get("expectations", [])]
    name = suite.get("expectation_suite_name", "unnamed")
    return SuiteResult(name, all(r.success for r in results), results)


def run_freshness_check(
    max_timestamp: str | None,
    max_age_hours: int = 24,
    now_iso: str | None = None,
) -> ExpectationResult:
    from datetime import UTC, datetime

    kwargs = {"max_age_hours": max_age_hours}
    if not max_timestamp:
        return ExpectationResult("expect_freshness", kwargs, False, None, "missing timestamp")
    now = datetime.fromisoformat(now_iso.replace("Z", "+00:00")) if now_iso else datetime.now(UTC)
    ts = datetime.fromisoformat(str(max_timestamp).replace("Z", "+00:00"))
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=UTC)
    age_hours = (now - ts).total_seconds() / 3600
    ok = age_hours <= max_age_hours
    return ExpectationResult("expect_freshness", kwargs, ok, age_hours, f"age_hours={age_hours:.2f}")


def persist_suite_result(lake: Lake, result: SuiteResult, run_id: str) -> str:
    key = f"gold/quality/run_id={run_id}/{result.suite_name}.json"
    write_json(lake, key, result.as_dict())
    return key
