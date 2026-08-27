"""Synthetic price history with realistic promotions and incremental timestamps."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

RETAILERS = ["Sephora", "Ulta", "Brand.com"]


def generate_price_history(
    products: pd.DataFrame,
    days: int = 90,
    end: datetime | None = None,
    seed: int = 42,
    include_bad_rows: bool = True,
) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    end = end or datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
    start = end - timedelta(days=days - 1)
    rows: list[dict] = []
    for _, product in products.iterrows():
        base = float(product["price"])
        product_id = int(product["product_id"])
        price = base
        discount = 0.0
        promo_day = int(rng.integers(10, max(11, days - 5)))
        promo_len = int(rng.integers(3, 10))
        for day in range(days):
            ts = start + timedelta(days=day)
            if promo_day <= day < promo_day + promo_len:
                discount = float(rng.choice([10, 12, 15, 20, 25]))
                price = round(base * (1 - discount / 100), 2)
            else:
                discount = 0.0
                price = base
            retailer = RETAILERS[int(product_id) % len(RETAILERS)]
            rows.append(
                {
                    "product_id": product_id,
                    "timestamp": ts.isoformat().replace("+00:00", "Z"),
                    "price": price,
                    "list_price": base,
                    "retailer": retailer,
                    "currency": "USD",
                    "discount": discount,
                }
            )
    if include_bad_rows:
        rows.append(
            {
                "product_id": None,
                "timestamp": end.isoformat().replace("+00:00", "Z"),
                "price": -5.0,
                "list_price": 10.0,
                "retailer": "Sephora",
                "currency": "USD",
                "discount": 0.0,
            }
        )
    frame = pd.DataFrame(rows)
    return frame


def write_price_history(frame: pd.DataFrame, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_parquet(path, index=False)
    return path
