SELECT
    md5(CAST(p.product_id AS VARCHAR) || '|' || CAST(p.event_ts AS VARCHAR) || '|' || p.retailer) AS price_event_sk,
    p.product_id,
    CAST(strftime(CAST(p.event_ts AS DATE), '%Y%m%d') AS INTEGER) AS date_sk,
    md5(p.retailer) AS retailer_sk,
    p.event_ts,
    p.price,
    p.list_price,
    p.discount,
    p.prev_price,
    p.price_delta,
    p.retailer
FROM {{ ref('int_price_changes') }} p
