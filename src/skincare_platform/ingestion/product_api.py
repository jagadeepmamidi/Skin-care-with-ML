"""Source 2 — product catalog API (local FastAPI + optional Makeup API)."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import httpx

from skincare_platform.config import Settings
from skincare_platform.lake import Lake, partition_prefix, write_json, write_jsonl
from skincare_platform.lineage import Lineage, attach_lineage, make_batch_id, stable_product_id
from skincare_platform.quality.quarantine import quarantine_records, split_valid_invalid
from skincare_platform.transforms import (
    is_valid_price,
    normalize_brand,
    normalize_category,
    to_float,
)

SOURCE = "product_api"
HASH_FIELDS = ["product_id", "brand", "product_name", "price", "category"]

EXTRA_CATALOG = [
    {
        "brand": "The Ordinary",
        "name": "Niacinamide 10% + Zinc 1%",
        "price": 12.0,
        "category": "Treatment",
        "rating": 4.5,
        "ingredients": "Aqua, Niacinamide, Pentylene Glycol, Zinc PCA, Tamarindus Indica Seed Gum, Xanthan Gum, Isoceteth-20, Ethoxydiglycol, Phenoxyethanol, Chlorphenesin",
        "combination": 1,
        "dry": 1,
        "normal": 1,
        "oily": 1,
        "sensitive": 1,
    },
    {
        "brand": "The Ordinary",
        "name": "Hyaluronic Acid 2% + B5",
        "price": 8.9,
        "category": "Treatment",
        "rating": 4.3,
        "ingredients": "Aqua, Sodium Hyaluronate, Pentylene Glycol, Propanediol, Sodium Hyaluronate Crosspolymer, Panthenol, Ahnfeltia Concinna Extract, Glycerin, Trisodium Ethylenediamine Disuccinate, Citric Acid, Isoceteth-20, Ethoxydiglycol, Caprylyl Glycol, Hexylene Glycol, Phenoxyethanol, Chlorphenesin",
        "combination": 1,
        "dry": 1,
        "normal": 1,
        "oily": 1,
        "sensitive": 1,
    },
    {
        "brand": "CeraVe",
        "name": "Moisturizing Cream",
        "price": 19.99,
        "category": "Moisturizer",
        "rating": 4.6,
        "ingredients": "Aqua, Glycerin, Cetearyl Alcohol, Caprylic/Capric Triglyceride, Cetyl Alcohol, Ceteareth-20, Petrolatum, Dimethicone, Phenoxyethanol, Behentrimonium Methosulfate, Glyceryl Stearate, Potassium Phosphate, Ceramide NP, Ceramide AP, Ceramide EOP, Carbomer, Niacinamide, Cetearyl Glucoside, Sodium Lauroyl Lactylate, Sodium Hyaluronate, Cholesterol, Phytosphingosine, Xanthan Gum, Dipotassium Phosphate, Tocopherol",
        "combination": 1,
        "dry": 1,
        "normal": 1,
        "oily": 0,
        "sensitive": 1,
    },
    {
        "brand": "La Roche-Posay",
        "name": "Toleriane Double Repair Face Moisturizer",
        "price": 21.99,
        "category": "Moisturizer",
        "rating": 4.4,
        "ingredients": "Aqua, Glycerin, Dimethicone, Niacinamide, Ammonium Polyacryloyldimethyl Taurate, Ceramide NP, Sodium Hyaluronate, Glyceryl Stearate, PEG-100 Stearate, Stearic Acid, Myristic Acid, Palmitic Acid, Capryloyl Glycine, Caprylyl Glycol, Cetyl Alcohol, Disodium EDTA, Sodium Hydroxide, Xanthan Gum, Tocopherol",
        "combination": 1,
        "dry": 1,
        "normal": 1,
        "oily": 1,
        "sensitive": 1,
    },
    {
        "brand": "Paula's Choice",
        "name": "2% BHA Liquid Exfoliant",
        "price": 35.0,
        "category": "Treatment",
        "rating": 4.7,
        "ingredients": "Water, Methylpropanediol, Butylene Glycol, Salicylic Acid, Polysorbate 20, Camellia Oleifera Leaf Extract, Sodium Hydroxide, Tetrasodium EDTA, Methyl Gluceth-20, Green Tea Extract",
        "combination": 1,
        "dry": 0,
        "normal": 1,
        "oily": 1,
        "sensitive": 0,
    },
]


def _to_product(item: dict[str, Any], source_system: str) -> dict[str, Any]:
    brand = str(item.get("brand") or item.get("Brand") or "Unknown").strip()
    name = str(item.get("name") or item.get("product_name") or "").strip()
    price = to_float(item.get("price") or item.get("price_sign") and item.get("price"))
    if price is None:
        price = to_float(item.get("price"))
    return {
        "product_id": stable_product_id(brand, name) if name else None,
        "source_product_id": str(item.get("id") or item.get("product_id") or ""),
        "brand": brand,
        "brand_normalized": normalize_brand(brand),
        "product_name": name,
        "category": normalize_category(item.get("category") or item.get("product_type") or item.get("Label")),
        "price": price,
        "rating": to_float(item.get("rating") or item.get("rank")),
        "ingredients": item.get("ingredients") or item.get("description") or "",
        "combination": int(item.get("combination") or 0),
        "dry": int(item.get("dry") or 0),
        "normal": int(item.get("normal") or 0),
        "oily": int(item.get("oily") or 0),
        "sensitive": int(item.get("sensitive") or 0),
        "currency": str(item.get("currency") or "USD"),
        "retailer": str(item.get("retailer") or source_system),
        "source_system": source_system,
        "product_api_url": item.get("product_api_url") or item.get("product_link"),
    }


def fetch_local_catalog(settings: Settings) -> list[dict[str, Any]]:
    records = [_to_product(item, "local_catalog_api") for item in EXTRA_CATALOG]
    try:
        with httpx.Client(timeout=5.0) as client:
            resp = client.get(f"{settings.product_api_url.rstrip('/')}/v1/products")
            resp.raise_for_status()
            payload = resp.json()
            items = payload.get("products", payload) if isinstance(payload, dict) else payload
            records.extend(_to_product(item, "local_product_api") for item in items)
    except Exception:
        pass
    return records


def fetch_makeup_api(settings: Settings) -> list[dict[str, Any]]:
    if not settings.makeup_api_enabled:
        return []
    try:
        with httpx.Client(timeout=15.0, follow_redirects=True) as client:
            resp = client.get(settings.makeup_api_url, params={"product_type": "foundation"})
            resp.raise_for_status()
            items = resp.json()
            out = []
            for item in items[:80]:
                rec = _to_product(item, "makeup_api")
                if rec["product_name"]:
                    out.append(rec)
            return out
    except Exception:
        return []


def validate_api_product(record: dict[str, Any]) -> list[str]:
    reasons: list[str] = []
    if not record.get("product_id"):
        reasons.append("product_id_null")
    if not record.get("product_name"):
        reasons.append("product_name_null")
    if record.get("price") is not None and not is_valid_price(record.get("price")):
        reasons.append("invalid_price")
    return reasons


def ingest_product_api(
    lake: Lake,
    settings: Settings,
    ingested_at: datetime | None = None,
) -> dict[str, Any]:
    when = ingested_at or datetime.now(UTC)
    lineage = Lineage(
        source=SOURCE,
        ingested_at=when.replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        batch_id=make_batch_id("product_api", when),
        file_name="products.json",
    )
    records = fetch_local_catalog(settings) + fetch_makeup_api(settings)
    seen: set[int] = set()
    unique: list[dict[str, Any]] = []
    for rec in records:
        pid = rec.get("product_id")
        if pid in seen:
            continue
        seen.add(pid)
        unique.append(rec)
    decorated = [attach_lineage(rec, lineage, HASH_FIELDS) for rec in unique]
    valid, invalid = split_valid_invalid(decorated, validate_api_product, lineage.batch_id)
    quarantine_key = quarantine_records(lake, "invalid_products", lineage.batch_id, invalid)

    prefix = partition_prefix("bronze", "product_api", when, extra=f"batch_id={lineage.batch_id}")
    bronze_key = f"{prefix}/products.json"
    write_json(lake, bronze_key, valid)
    write_jsonl(lake, f"{prefix}/products.jsonl", valid)
    write_json(
        lake,
        f"{prefix}/_manifest.json",
        {
            "dataset": "product_api",
            "source": SOURCE,
            "batch_id": lineage.batch_id,
            "ingested_at": lineage.ingested_at,
            "row_count": len(valid),
            "quarantine_count": len(invalid),
            "quarantine_key": quarantine_key,
            "bronze_key": bronze_key,
        },
    )
    return {
        "batch_id": lineage.batch_id,
        "bronze_key": bronze_key,
        "row_count": len(valid),
        "quarantine_count": len(invalid),
        "quarantine_key": quarantine_key,
        "ingested_at": lineage.ingested_at,
    }
