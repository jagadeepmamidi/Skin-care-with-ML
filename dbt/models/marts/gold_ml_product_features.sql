SELECT
    p.product_id,
    p.brand_normalized AS brand,
    p.product_name,
    p.category,
    p.price,
    p.rating,
    p.combination,
    p.dry,
    p.normal,
    p.oily,
    p.sensitive,
    CASE
        WHEN p.combination + p.dry + p.normal + p.oily + p.sensitive = 0 THEN 'unknown'
        WHEN p.sensitive = 1 AND p.oily = 1 THEN 'sensitive_oily'
        WHEN p.sensitive = 1 THEN 'sensitive'
        WHEN p.oily = 1 AND p.dry = 0 THEN 'oily'
        WHEN p.dry = 1 AND p.oily = 0 THEN 'dry'
        ELSE 'balanced'
    END AS skin_type,
    p.ingredients,
    p.ingredient_count,
    COALESCE(a.views, 0) AS views,
    COALESCE(a.purchases, 0) AS purchases,
    COALESCE(a.conversion_rate, 0) AS conversion_rate,
    COALESCE(a.unique_users, 0) AS unique_users,
    (
        COALESCE(p.rating, 0) * 0.35
        + LN(1 + COALESCE(a.views, 0)) * 0.25
        + COALESCE(a.conversion_rate, 0) * 20 * 0.25
        + LN(1 + COALESCE(a.purchases, 0)) * 0.15
    ) AS popularity_score
FROM {{ ref('stg_products') }} p
LEFT JOIN {{ ref('int_product_activity') }} a
  ON p.product_id = a.product_id
