SELECT
    CAST(ingredient_id AS BIGINT) AS ingredient_id,
    ingredient_name
FROM {{ source('raw', 'raw_ingredients') }}
