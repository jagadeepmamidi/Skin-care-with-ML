"""Synthetic customer interaction events (views, search, cart, purchase, review)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

EVENT_TYPES = np.array(["VIEW_PRODUCT", "SEARCH", "ADD_TO_CART", "PURCHASE", "REVIEW"])
EVENT_P = np.array([0.62, 0.12, 0.14, 0.08, 0.04])


def generate_events(
    products: pd.DataFrame,
    n_events: int = 1_000_000,
    n_users: int = 25_000,
    days: int = 90,
    end: datetime | None = None,
    seed: int = 7,
    include_bad_rows: bool = True,
) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    end = end or datetime.now(UTC).replace(microsecond=0)
    start = end - timedelta(days=days)
    product_ids = products["product_id"].astype(int).to_numpy()
    weights = np.clip(products["rating"].fillna(3.5).to_numpy(dtype=float), 1.0, 5.0)
    weights = weights / weights.sum()

    offsets = rng.random(n_events) * (end - start).total_seconds()
    timestamps = np.array(
        [start + timedelta(seconds=float(s)) for s in offsets], dtype=object
    )
    event_types = rng.choice(EVENT_TYPES, size=n_events, p=EVENT_P)
    user_ids = rng.integers(1, n_users + 1, size=n_events)
    session_ids = rng.integers(1, n_users * 8, size=n_events)
    chosen = rng.choice(product_ids, size=n_events, p=weights)

    search_mask = event_types == "SEARCH"
    product_col = chosen.astype(object)
    product_col[search_mask] = None

    queries = np.array([None] * n_events, dtype=object)
    sample_names = products["product_name"].astype(str).to_numpy()
    if search_mask.any():
        queries[search_mask] = rng.choice(sample_names, size=int(search_mask.sum()))

    ratings = np.array([None] * n_events, dtype=object)
    review_mask = event_types == "REVIEW"
    if review_mask.any():
        ratings[review_mask] = rng.integers(1, 6, size=int(review_mask.sum()))

    event_ids = np.array([f"evt_{i:09d}" for i in range(n_events)])
    frame = pd.DataFrame(
        {
            "event_id": event_ids,
            "user_id": user_ids,
            "product_id": product_col,
            "event_type": event_types,
            "timestamp": [ts.isoformat().replace("+00:00", "Z") for ts in timestamps],
            "session_id": [f"ses_{sid}" for sid in session_ids],
            "search_query": queries,
            "review_rating": ratings,
        }
    )
    if include_bad_rows:
        bad = pd.DataFrame(
            [
                {
                    "event_id": None,
                    "user_id": 0,
                    "product_id": int(product_ids[0]),
                    "event_type": "VIEW_PRODUCT",
                    "timestamp": start.isoformat().replace("+00:00", "Z"),
                    "session_id": "ses_bad",
                    "search_query": None,
                    "review_rating": None,
                },
                {
                    "event_id": "evt_bad_type",
                    "user_id": 1,
                    "product_id": int(product_ids[0]),
                    "event_type": "EXPLODE_CART",
                    "timestamp": start.isoformat().replace("+00:00", "Z"),
                    "session_id": "ses_bad",
                    "search_query": None,
                    "review_rating": None,
                },
            ]
        )
        frame = pd.concat([frame, bad], ignore_index=True)
    return frame.sort_values("timestamp").reset_index(drop=True)


def write_events(frame: pd.DataFrame, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_parquet(path, index=False)
    return path
