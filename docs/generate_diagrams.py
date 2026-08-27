"""Draw architecture and star-schema diagrams for docs/."""

from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch

ROOT = Path(__file__).resolve().parents[1]


def box(ax, x, y, w, h, text, color):
    patch = FancyBboxPatch(
        (x, y), w, h, boxstyle="round,pad=0.02,rounding_size=0.08",
        facecolor=color, edgecolor="#1f2937", linewidth=1.2,
    )
    ax.add_patch(patch)
    ax.text(x + w / 2, y + h / 2, text, ha="center", va="center", fontsize=8, color="#111827", wrap=True)


def architecture():
    fig, ax = plt.subplots(figsize=(12, 7))
    ax.set_xlim(0, 12)
    ax.set_ylim(0, 8)
    ax.axis("off")
    ax.set_title("Skincare Intelligence Data Platform", fontsize=14, pad=12)

    box(ax, 0.4, 6.6, 2.4, 0.9, "cosmetics.csv\nHistorical", "#dbeafe")
    box(ax, 3.3, 6.6, 2.4, 0.9, "Product API\nMakeup + local", "#dbeafe")
    box(ax, 6.2, 6.6, 2.4, 0.9, "Price history\nSynthetic", "#dbeafe")
    box(ax, 9.1, 6.6, 2.4, 0.9, "Events / Kafka\n1M interactions", "#dbeafe")

    box(ax, 3.3, 5.2, 5.4, 0.8, "Python ingestion + lineage  |  Apache Airflow", "#fef3c7")

    box(ax, 0.8, 3.6, 3.2, 1.1, "BRONZE\nJSON/JSONL + metadata", "#fecaca")
    box(ax, 4.4, 3.6, 3.2, 1.1, "SILVER\nSpark Parquet", "#fde68a")
    box(ax, 8.0, 3.6, 3.2, 1.1, "GOLD\ndbt star schema", "#bbf7d0")

    box(ax, 0.8, 2.3, 10.4, 0.7, "MinIO / S3 data lake   +   quarantine/ dead-letter", "#e5e7eb")

    box(ax, 0.8, 0.6, 3.2, 1.1, "DuckDB / PostgreSQL\nAnalytics warehouse", "#c7d2fe")
    box(ax, 4.4, 0.6, 3.2, 1.1, "Streamlit / Power BI\nDashboards", "#ddd6fe")
    box(ax, 8.0, 0.6, 3.2, 1.1, "ML features\nRecommendations", "#fbcfe8")

    fig.tight_layout()
    out = ROOT / "docs" / "architecture.png"
    fig.savefig(out, dpi=140)
    plt.close(fig)
    return out


def data_model():
    fig, ax = plt.subplots(figsize=(11, 6))
    ax.set_xlim(0, 11)
    ax.set_ylim(0, 6)
    ax.axis("off")
    ax.set_title("Star schema — Gold marts", fontsize=14, pad=12)

    box(ax, 4.0, 4.6, 3.0, 0.8, "dim_brand", "#dbeafe")
    box(ax, 0.4, 2.6, 2.6, 0.8, "dim_date", "#dbeafe")
    box(ax, 4.0, 2.6, 3.0, 1.1, "fact_product_events", "#fde68a")
    box(ax, 8.0, 2.6, 2.6, 0.8, "dim_product\n(SCD2 snapshot)", "#dbeafe")
    box(ax, 4.0, 0.6, 3.0, 0.8, "dim_customer", "#dbeafe")
    box(ax, 0.4, 0.6, 2.6, 0.8, "fact_price_history", "#fde68a")
    box(ax, 8.0, 0.6, 2.6, 0.8, "fact_sales", "#fde68a")

    fig.tight_layout()
    out = ROOT / "docs" / "data_model.png"
    fig.savefig(out, dpi=140)
    plt.close(fig)
    return out


if __name__ == "__main__":
    print(architecture())
    print(data_model())
