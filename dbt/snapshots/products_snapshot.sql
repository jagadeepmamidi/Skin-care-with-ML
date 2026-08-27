{% snapshot products_snapshot %}

{{
    config(
      target_schema='snapshots',
      unique_key='product_id',
      strategy='check',
      check_cols=['price', 'category', 'brand_normalized', 'rating'],
      invalidate_hard_deletes=True
    )
}}

SELECT
    product_id,
    brand_normalized,
    product_name,
    category,
    price,
    rating,
    ingested_at
FROM {{ ref('stg_products') }}

{% endsnapshot %}
