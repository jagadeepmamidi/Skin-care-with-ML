SELECT
    CAST(product_id AS BIGINT) AS product_id,
    CAST(views AS BIGINT) AS views,
    CAST(add_to_cart AS BIGINT) AS add_to_cart,
    CAST(purchases AS BIGINT) AS purchases,
    CAST(reviews AS BIGINT) AS reviews,
    CAST(avg_review_rating AS DOUBLE) AS avg_review_rating,
    CAST(unique_users AS BIGINT) AS unique_users,
    CAST(conversion_rate AS DOUBLE) AS conversion_rate
FROM {{ source('raw', 'raw_product_activity') }}
