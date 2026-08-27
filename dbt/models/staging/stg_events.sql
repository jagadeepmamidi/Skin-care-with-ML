SELECT
    event_id,
    CAST(user_id AS BIGINT) AS user_id,
    CAST(product_id AS BIGINT) AS product_id,
    event_type,
    CAST(event_ts AS TIMESTAMP) AS event_ts,
    CAST(timestamp AS VARCHAR) AS event_timestamp,
    session_id,
    search_query,
    CAST(review_rating AS DOUBLE) AS review_rating,
    source,
    batch_id,
    record_hash,
    ingested_at
FROM {{ source('raw', 'raw_events') }}
WHERE event_id IS NOT NULL
