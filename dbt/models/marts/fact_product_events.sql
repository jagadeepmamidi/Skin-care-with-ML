SELECT
    md5(e.event_id) AS event_sk,
    e.event_id,
    e.event_type,
    e.user_id AS customer_sk,
    e.product_id,
    CAST(strftime(CAST(e.event_ts AS DATE), '%Y%m%d') AS INTEGER) AS date_sk,
    e.event_ts,
    e.session_id,
    e.search_query,
    e.review_rating,
    CASE WHEN e.event_type = 'PURCHASE' THEN 1 ELSE 0 END AS is_purchase,
    CASE WHEN e.event_type = 'VIEW_PRODUCT' THEN 1 ELSE 0 END AS is_view
FROM {{ ref('stg_events') }} e
