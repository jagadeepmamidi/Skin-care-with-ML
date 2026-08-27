SELECT DISTINCT
    CAST(user_id AS BIGINT) AS customer_sk,
    CAST(user_id AS BIGINT) AS user_id,
    'synthetic' AS customer_type
FROM {{ ref('stg_events') }}
WHERE user_id IS NOT NULL
