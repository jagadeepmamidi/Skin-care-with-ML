# Power BI dashboard spec

Gold CSVs are exported by `make export-powerbi` into `dashboards/powerbi/exports/`.

Import those files into Power BI Desktop and create relationships:

- `fact_product_events.product_id` → `dim_product.product_id`
- `fact_product_events.date_sk` → `dim_date.date_sk`
- `fact_product_events.customer_sk` → `dim_customer.customer_sk`
- `fact_price_history.product_id` → `dim_product.product_id`
- `fact_price_history.date_sk` → `dim_date.date_sk`
- `fact_price_history.retailer_sk` → `dim_retailer.retailer_sk`
- `fact_sales.product_id` → `dim_product.product_id`

## Pages

1. **Product landscape** — total products, average price, average rating, products by brand/category.
2. **Ingredient intelligence** — most common ingredients, ingredient-product relationships (use `int_product_ingredients` if exported from DuckDB).
3. **Pricing intelligence** — average price by brand, price changes over time, discount trends.
4. **Customer behaviour** — most viewed products, conversion rate, event mix.

Suggested measures:

```dax
Total Products = DISTINCTCOUNT(dim_product[product_id])
Avg Price = AVERAGE(dim_product[price])
Conversion Rate = DIVIDE(CALCULATE(COUNTROWS(fact_product_events), fact_product_events[event_type] = "PURCHASE"),
                         CALCULATE(COUNTROWS(fact_product_events), fact_product_events[event_type] = "VIEW_PRODUCT"))
Revenue = SUM(fact_sales[revenue])
```
