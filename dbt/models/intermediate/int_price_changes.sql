WITH ordered AS (
    SELECT
        product_id,
        event_ts,
        price,
        list_price,
        discount,
        retailer,
        LAG(price) OVER (PARTITION BY product_id, retailer ORDER BY event_ts) AS prev_price
    FROM {{ ref('stg_prices') }}
)
SELECT
    product_id,
    event_ts,
    price,
    list_price,
    discount,
    retailer,
    prev_price,
    CASE WHEN prev_price IS NULL THEN 0 ELSE price - prev_price END AS price_delta
FROM ordered
