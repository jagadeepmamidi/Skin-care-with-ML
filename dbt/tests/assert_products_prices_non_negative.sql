SELECT *
FROM {{ ref('stg_products') }}
WHERE price < 0
