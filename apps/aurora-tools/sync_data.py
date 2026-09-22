#!/usr/bin/env python3
"""Validate and copy canonical synthetic fixtures into the Kustomize build root."""
from pathlib import Path
import shutil
from business import Catalog

root = Path(__file__).resolve().parents[2]
data = root / "data"
Catalog(str(data / "products.json"), str(data / "forecasts.json"))
for name in ("products.json", "forecasts.json"):
    for module in ("backend", "lifecycle"):
        shutil.copyfile(data / name, root / "gitops/components/mcp" / module / name)
print("Validated and synchronized synthetic products and forecasts.")
