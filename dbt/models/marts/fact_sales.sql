SELECT
    md5(e.event_id) AS sale_sk,
    e.event_id,
    e.product_id,
    e.user_id AS customer_sk,
    CAST(strftime(CAST(e.event_ts AS DATE), '%Y%m%d') AS INTEGER) AS date_sk,
    e.event_ts,
    pr.price AS unit_price,
    1 AS quantity,
    pr.price AS revenue,
    pr.brand,
    pr.category
FROM {{ ref('stg_events') }} e
INNER JOIN {{ ref('stg_products') }} pr
  ON e.product_id = pr.product_id
WHERE e.event_type = 'PURCHASE'
