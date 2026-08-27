# Data model

Star schema implemented by dbt marts:

```text
                     dim_brand
                         │
dim_date ─────── fact_product_events ───── dim_product (SCD2 snapshot)
                         │
                         ▼
                    dim_customer

fact_price_history ── dim_product / dim_date / dim_retailer
fact_sales          ── dim_product / dim_date / dim_customer
```

## Grains

| Table | Grain |
| --- | --- |
| `dim_product` | one current row per `product_id` |
| `snapshots.products_snapshot` | SCD Type 2 history (`dbt_valid_from` / `dbt_valid_to`) |
| `fact_product_events` | one customer interaction |
| `fact_price_history` | one product × retailer × timestamp |
| `fact_sales` | one `PURCHASE` event |
| `gold_ml_product_features` | one feature row per product |

Natural key for products is `(brand, product_name)`; surrogate `product_id` is a stable MD5 integer. `product_sk` is a hash of `product_id` + `ingested_at` for versioned rows.
