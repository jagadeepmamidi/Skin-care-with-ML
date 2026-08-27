SELECT
    CAST(product_id AS BIGINT) AS product_id,
    CAST(ingredient_id AS BIGINT) AS ingredient_id
FROM {{ source('raw', 'raw_product_ingredients') }}
