"""Optional Kafka / file-drop streaming producer for customer events."""

from __future__ import annotations

import json
import time
from typing import Any

from skincare_platform.config import get_settings
from skincare_platform.generators.events import generate_events
from skincare_platform.ingestion.cosmetics import load_cosmetics_csv, row_to_record
from skincare_platform.lake import get_lake, partition_prefix, write_jsonl
from skincare_platform.lineage import utcnow


def _products():
    import pandas as pd

    settings = get_settings()
    raw = load_cosmetics_csv(settings.raw_csv_path)
    return pd.DataFrame([row_to_record(r) for r in raw.to_dict(orient="records")])


def publish_microbatch(n_events: int = 500, sink: str = "lake") -> dict[str, Any]:
    """Emit a small event batch to Kafka (if configured) and always to Bronze streaming prefix."""
    settings = get_settings()
    frame = generate_events(_products(), n_events=n_events, days=1, include_bad_rows=False)
    records = frame.to_dict(orient="records")
    sent_kafka = 0
    if sink in {"kafka", "both"}:
        try:
            from confluent_kafka import Producer

            producer = Producer({"bootstrap.servers": settings.kafka_bootstrap_servers})
            for rec in records:
                producer.produce(settings.kafka_topic_events, json.dumps(rec, default=str).encode())
                sent_kafka += 1
            producer.flush(10)
        except Exception as exc:
            sent_kafka = f"kafka_unavailable:{exc}"  # type: ignore[assignment]

    lake = get_lake(settings)
    when = utcnow()
    key = f"{partition_prefix('bronze', 'events_stream', when)}/events.jsonl"
    write_jsonl(lake, key, records)
    return {"events": len(records), "bronze_key": key, "kafka": sent_kafka}


def consume_loop(seconds: int = 5) -> None:
    """Best-effort Kafka consumer writing to Bronze. Exits if Kafka is down."""
    settings = get_settings()
    try:
        from confluent_kafka import Consumer
    except Exception:
        return
    consumer = Consumer(
        {
            "bootstrap.servers": settings.kafka_bootstrap_servers,
            "group.id": "skincare-bronze",
            "auto.offset.reset": "earliest",
        }
    )
    consumer.subscribe([settings.kafka_topic_events])
    deadline = time.time() + seconds
    batch: list[dict[str, Any]] = []
    while time.time() < deadline:
        msg = consumer.poll(1.0)
        if msg is None or msg.error():
            continue
        batch.append(json.loads(msg.value().decode()))
    consumer.close()
    if batch:
        lake = get_lake(settings)
        key = f"{partition_prefix('bronze', 'events_stream', utcnow())}/kafka.jsonl"
        write_jsonl(lake, key, batch)
