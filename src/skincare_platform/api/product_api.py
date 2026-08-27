"""Local product catalog API used as Source #2."""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from pydantic import BaseModel

from skincare_platform.config import get_settings
from skincare_platform.ingestion.cosmetics import load_cosmetics_csv, row_to_record
from skincare_platform.ingestion.product_api import EXTRA_CATALOG, _to_product

app = FastAPI(title="Skincare Product API", version="1.0.0")


class Product(BaseModel):
    product_id: int | None
    brand: str
    name: str
    price: float | None
    category: str
    rating: float | None = None
    ingredients: str | None = None


def _catalog() -> list[dict]:
    settings = get_settings()
    items = [_to_product(row, "local_catalog_api") for row in EXTRA_CATALOG]
    csv_path: Path = settings.raw_csv_path
    if csv_path.exists():
        frame = load_cosmetics_csv(csv_path)
        for row in frame.head(40).to_dict(orient="records"):
            rec = row_to_record(row)
            rec["name"] = rec["product_name"]
            rec["source_system"] = "sephora_mirror"
            items.append(rec)
    for item in items:
        item.setdefault("name", item.get("product_name"))
    return items


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/v1/products")
def list_products(limit: int = 100) -> dict:
    products = _catalog()[:limit]
    return {"count": len(products), "products": products}


@app.get("/v1/products/{product_id}")
def get_product(product_id: int) -> dict:
    for item in _catalog():
        if item.get("product_id") == product_id:
            return item
    return {"error": "not_found", "product_id": product_id}


def serve(host: str = "0.0.0.0", port: int = 8088) -> None:
    import uvicorn

    uvicorn.run("skincare_platform.api.product_api:app", host=host, port=port, reload=False)
