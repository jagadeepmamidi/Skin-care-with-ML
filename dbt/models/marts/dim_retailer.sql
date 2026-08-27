SELECT DISTINCT
    md5(retailer) AS retailer_sk,
    retailer AS retailer_name
FROM {{ ref('stg_prices') }}
