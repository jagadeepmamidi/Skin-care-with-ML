"""Pure, Spark-agnostic transforms used by Bronze → Silver jobs."""

from __future__ import annotations

import re
from typing import Any

BRAND_ALIASES = {
    "LA MER": "La Mer",
    "SK-II": "SK-II",
    "DRUNK ELEPHANT": "Drunk Elephant",
    "KIEHL'S SINCE 1851": "Kiehl's",
    "ESTEE LAUDER": "Estée Lauder",
    "ESTÉE LAUDER": "Estée Lauder",
    "L'OREAL": "L'Oréal",
    "LOREAL": "L'Oréal",
}

CATEGORY_ALIASES = {
    "moisturizer": "Moisturizer",
    "moisturiser": "Moisturizer",
    "cleanser": "Cleanser",
    "treatment": "Treatment",
    "face mask": "Face Mask",
    "mask": "Face Mask",
    "eye cream": "Eye Cream",
    "sun protect": "Sun Protect",
    "sunscreen": "Sun Protect",
}

INGREDIENT_STOP = {"", "na", "n/a", "none", "visit the", "#name?"}
INGREDIENT_SPLIT = re.compile(r",(?![^()]*\))")


def normalize_brand(brand: str | None) -> str:
    if not brand:
        return "Unknown"
    raw = " ".join(str(brand).split())
    return BRAND_ALIASES.get(raw.upper(), raw.title() if raw.isupper() else raw)


def normalize_category(label: str | None) -> str:
    if not label:
        return "Unknown"
    key = str(label).strip().lower()
    return CATEGORY_ALIASES.get(key, str(label).strip().title())


def tokenize_ingredients(raw: str | None) -> list[str]:
    if raw is None:
        return []
    text = str(raw).replace("*", " ").replace(".", " ")
    text = re.sub(r"\s+", " ", text)
    parts = [p.strip().strip(".").title() for p in INGREDIENT_SPLIT.split(text)]
    seen: set[str] = set()
    out: list[str] = []
    for part in parts:
        key = part.lower()
        if key in INGREDIENT_STOP or len(part) < 2:
            continue
        if "please" in key and "visit" in key:
            continue
        if key not in seen:
            seen.add(key)
            out.append(part)
    return out


def to_float(value: Any, default: float | None = None) -> float | None:
    if value is None or value == "":
        return default
    try:
        return float(str(value).replace("$", "").replace(",", "").strip())
    except (TypeError, ValueError):
        return default


def to_int_flag(value: Any) -> int:
    if value in (True, 1, "1", "true", "True", "yes"):
        return 1
    return 0


def is_valid_price(price: float | None) -> bool:
    return price is not None and 0 <= price <= 2500


def is_valid_rating(rating: float | None) -> bool:
    if rating is None:
        return True
    return 0 <= rating <= 5
