"""Pure, read-only business rules for the fictional Aurora Supply showroom."""
from __future__ import annotations

import hashlib
import json
import math
import os
from pathlib import Path
from typing import Any

FALLBACK_PRODUCTS = [
    {"sku": "AUR-001", "name": "Monitor Aurora 27", "category": "displays", "stock": 7, "reorder_point": 20},
    {"sku": "AUR-002", "name": "Dock Aurora USB-C", "category": "accessories", "stock": 24, "reorder_point": 15},
    {"sku": "AUR-003", "name": "Teclado Aurora", "category": "accessories", "stock": 0, "reorder_point": 12},
]


def load_products(path: str | None = None) -> tuple[list[dict[str, Any]], str]:
    """Load immutable fixture data; a configured invalid file fails closed."""
    path = path if path is not None else os.environ.get("AURORA_PRODUCTS_PATH")
    raw = json.loads(Path(path).read_text(encoding="utf-8")) if path else FALLBACK_PRODUCTS
    products = raw.get("products") if isinstance(raw, dict) else raw
    if not isinstance(products, list) or not 1 <= len(products) <= 1000:
        raise ValueError("products must be a nonempty list with at most 1000 entries")
    result, seen = [], set()
    for item in products:
        if not isinstance(item, dict):
            raise ValueError("each product must be an object")
        clean = {}
        for field in ("sku", "name", "category"):
            value = item.get(field)
            if not isinstance(value, str) or not value.strip() or len(value) > 160:
                raise ValueError(f"invalid product {field}")
            clean[field] = value.strip()
        if clean["sku"] in seen:
            raise ValueError("duplicate product sku")
        seen.add(clean["sku"])
        for field in ("stock", "reorder_point"):
            value = item.get(field)
            if type(value) is not int or not 0 <= value <= 1_000_000:
                raise ValueError(f"invalid product {field}")
            clean[field] = value
        result.append(clean)
    result.sort(key=lambda p: p["sku"])
    revision = hashlib.sha256(json.dumps(result, sort_keys=True).encode()).hexdigest()[:12]
    return result, revision


class Catalog:
    def __init__(self, path: str | None = None, forecast_path: str | None = None):
        self._products, self.revision = load_products(path)
        self._forecasts = {}
        self._forecast_meta = {}
        forecast_path = forecast_path if forecast_path is not None else os.environ.get("AURORA_FORECASTS_PATH")
        if forecast_path:
            raw = json.loads(Path(forecast_path).read_text(encoding="utf-8"))
            if raw.get("synthetic") is not True or raw.get("horizon_days") != 7:
                raise ValueError("forecast data must be synthetic with horizon_days=7")
            self._forecast_meta = {k: raw[k] for k in ("model_version", "horizon_days", "forecast_origin", "mlflow_run_id") if k in raw}
            if not isinstance(raw.get("forecasts"), list):
                raise ValueError("forecasts must be a list")
            known_skus = {p["sku"] for p in self._products}
            for item in raw["forecasts"]:
                sku, units = item.get("sku"), item.get("forecast_7d_units")
                if sku not in known_skus or sku in self._forecasts:
                    raise ValueError("unknown or duplicate forecast sku")
                if type(units) not in (int, float) or not math.isfinite(units) or not 0 <= units <= 1_000_000:
                    raise ValueError("invalid forecast quantity")
                self._forecasts[sku] = {"forecast_7d_units": units, **self._forecast_meta}

    def _envelope(self, **fields: Any) -> dict[str, Any]:
        return {"company": "Aurora Supply", "synthetic_data": True,
                "data_revision": self.revision, **fields}

    def list_products(self, category: str | None = None, limit: int = 50) -> dict[str, Any]:
        if type(limit) is not int or not 1 <= limit <= 100:
            raise ValueError("limit must be an integer between 1 and 100")
        if category is not None and (not isinstance(category, str) or len(category) > 160):
            raise ValueError("invalid category")
        selected = [dict(p) for p in self._products if category is None or p["category"].casefold() == category.casefold()]
        return self._envelope(products=selected[:limit], total=len(selected), returned=min(limit, len(selected)))

    def get_stock(self, sku: str) -> dict[str, Any]:
        if not isinstance(sku, str) or not 1 <= len(sku) <= 160:
            raise ValueError("invalid sku")
        product = next((p for p in self._products if p["sku"] == sku), None)
        if product is None:
            raise ValueError("unknown sku; use list_products first")
        return self._envelope(product=dict(product), source="versioned synthetic inventory")

    def get_replenishment_recommendation(self, sku: str) -> dict[str, Any]:
        product = self.get_stock(sku)["product"]
        forecast = self._forecasts.get(sku)
        target = max(product["reorder_point"], math.ceil(forecast["forecast_7d_units"])) if forecast else product["reorder_point"]
        quantity = max(0, target - product["stock"])
        return self._envelope(sku=sku, stock=product["stock"], reorder_point=product["reorder_point"],
                              target_stock=target, recommended_quantity=quantity,
                              rule="max(0, max(reorder_point, ceil(forecast_7d_units)) - stock)" if forecast else "max(0, reorder_point - stock)",
                              forecast=dict(forecast) if forecast else None,
                              recommendation_type="forecast-informed inventory proposal" if forecast else "deterministic inventory policy, not a trained forecast",
                              order_created=False, requires_human_approval=True,
                              explanation="Read-only proposal. No inventory, order or payment was modified.")
