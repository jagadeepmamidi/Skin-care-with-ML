SELECT
    (SELECT COUNT(*) FROM {{ ref('dim_product') }}) AS total_products,
    (SELECT AVG(price) FROM {{ ref('dim_product') }}) AS avg_price,
    (SELECT AVG(rating) FROM {{ ref('dim_product') }}) AS avg_rating,
    (SELECT COUNT(*) FROM {{ ref('dim_brand') }}) AS total_brands,
    (SELECT COUNT(*) FROM {{ ref('dim_ingredient') }}) AS total_ingredients,
    (SELECT COUNT(*) FROM {{ ref('fact_product_events') }}) AS total_events,
    (SELECT COUNT(*) FROM {{ ref('fact_sales') }}) AS total_purchases,
    (SELECT SUM(revenue) FROM {{ ref('fact_sales') }}) AS total_revenue
