import streamlit as st
import duckdb
from pathlib import Path
import os

st.set_page_config(page_title="Skincare Intelligence", layout="wide")
st.title("Skincare Intelligence — Gold Analytics")
st.caption("Reads marts built by the medallion pipeline (DuckDB).")

db_path = os.environ.get("DUCKDB_PATH", "data/warehouse/skincare.duckdb")
if not Path(db_path).exists():
    st.warning(
        f"Warehouse not found at `{db_path}`. Run `make pipeline` first, then reload."
    )
    st.stop()

con = duckdb.connect(db_path, read_only=True)

kpis = con.execute("SELECT * FROM marts.gold_analytics_kpis").df().iloc[0]
c1, c2, c3, c4 = st.columns(4)
c1.metric("Products", int(kpis.total_products))
c2.metric("Avg price", f"${kpis.avg_price:.2f}")
c3.metric("Avg rating", f"{kpis.avg_rating:.2f}")
c4.metric("Events", int(kpis.total_events))

tab1, tab2, tab3, tab4 = st.tabs(
    ["Product landscape", "Ingredient intelligence", "Pricing", "Customer behaviour"]
)

with tab1:
    st.subheader("Products by category")
    st.bar_chart(
        con.execute("SELECT category, COUNT(*) n FROM marts.dim_product GROUP BY 1 ORDER BY 2 DESC").df(),
        x="category",
        y="n",
    )
    st.subheader("Top brands")
    st.dataframe(
        con.execute(
            "SELECT brand, COUNT(*) products, AVG(price) avg_price, AVG(rating) avg_rating "
            "FROM marts.dim_product GROUP BY 1 ORDER BY products DESC LIMIT 20"
        ).df()
    )

with tab2:
    st.subheader("Most common ingredients")
    st.dataframe(
        con.execute(
            """
            SELECT i.ingredient_name, COUNT(*) AS product_count
            FROM intermediate.int_product_ingredients b
            JOIN marts.dim_ingredient i ON i.ingredient_id = b.ingredient_id
            GROUP BY 1
            ORDER BY 2 DESC
            LIMIT 25
            """
        ).df()
    )

with tab3:
    st.subheader("Average price by brand")
    st.dataframe(
        con.execute(
            "SELECT brand, AVG(price) avg_price FROM marts.dim_product GROUP BY 1 ORDER BY avg_price DESC LIMIT 20"
        ).df()
    )
    st.subheader("Discounted observations")
    st.line_chart(
        con.execute(
            """
            SELECT CAST(event_ts AS DATE) AS day, AVG(discount) avg_discount
            FROM marts.fact_price_history
            GROUP BY 1
            ORDER BY 1
            """
        ).df(),
        x="day",
        y="avg_discount",
    )

with tab4:
    st.subheader("Most viewed products")
    st.dataframe(
        con.execute(
            """
            SELECT p.product_name, p.brand, f.views, f.purchases, f.conversion_rate
            FROM intermediate.int_product_activity f
            JOIN marts.dim_product p ON p.product_id = f.product_id
            ORDER BY f.views DESC
            LIMIT 20
            """
        ).df()
    )
    st.subheader("Event mix")
    st.bar_chart(
        con.execute("SELECT event_type, COUNT(*) n FROM marts.fact_product_events GROUP BY 1").df(),
        x="event_type",
        y="n",
    )
