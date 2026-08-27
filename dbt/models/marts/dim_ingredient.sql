SELECT
    ingredient_id AS ingredient_sk,
    ingredient_id,
    ingredient_name,
    LOWER(ingredient_name) AS ingredient_name_normalized
FROM {{ ref('stg_ingredients') }}
