{{
  config(
    materialized='incremental',
    unique_key='product_id',
    incremental_strategy='merge'
  )
}}

WITH current_products AS (
    SELECT
        p.product_id,
        md5(CAST(p.product_id AS VARCHAR) || '|' || CAST(p.ingested_at AS VARCHAR)) AS product_sk,
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
        p.ingredient_count,
        p.retailer,
        p.source,
        CAST(p.ingested_at AS TIMESTAMP) AS valid_from,
        CAST(NULL AS TIMESTAMP) AS valid_to,
        TRUE AS is_current,
        p.record_hash
    FROM {{ ref('stg_products') }} p
)

SELECT * FROM current_products
{% if is_incremental() %}
WHERE record_hash NOT IN (SELECT record_hash FROM {{ this }} WHERE is_current)
{% endif %}
