SELECT
    CAST(product_id AS BIGINT) AS product_id,
    CAST(event_ts AS TIMESTAMP) AS event_ts,
    CAST(timestamp AS VARCHAR) AS price_timestamp,
    CAST(price AS DOUBLE) AS price,
    CAST(list_price AS DOUBLE) AS list_price,
    CAST(discount AS DOUBLE) AS discount,
    retailer,
    currency,
    source,
    batch_id,
    record_hash,
    ingested_at
FROM {{ source('raw', 'raw_prices') }}
WHERE product_id IS NOT NULL
  AND price >= 0
