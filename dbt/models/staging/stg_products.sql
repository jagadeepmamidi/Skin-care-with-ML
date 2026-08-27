SELECT
    CAST(product_id AS BIGINT) AS product_id,
    brand,
    brand_normalized,
    product_name,
    category,
    CAST(price AS DOUBLE) AS price,
    CAST(rating AS DOUBLE) AS rating,
    ingredients,
    CAST(combination AS INTEGER) AS combination,
    CAST(dry AS INTEGER) AS dry,
    CAST(normal AS INTEGER) AS normal,
    CAST(oily AS INTEGER) AS oily,
    CAST(sensitive AS INTEGER) AS sensitive,
    currency,
    retailer,
    source,
    ingested_at,
    batch_id,
    record_hash,
    schema_version,
    CAST(ingredient_count AS INTEGER) AS ingredient_count
FROM {{ source('raw', 'raw_products') }}
WHERE product_id IS NOT NULL
