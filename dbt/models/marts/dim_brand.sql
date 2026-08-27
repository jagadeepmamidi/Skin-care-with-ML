SELECT DISTINCT
    md5(CAST(brand_normalized AS VARCHAR)) AS brand_sk,
    brand_normalized AS brand_name,
    brand AS brand_raw
FROM {{ ref('stg_products') }}
