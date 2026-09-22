"""Reusable Aurora Supply features from the public, historical synthetic dataset."""
from datetime import timedelta
import json
from pathlib import Path

import pandas as pd
from feast import Entity, FeatureService, FeatureView, Field, FileSource, ValueType
from feast.feast_object import ALL_RESOURCE_TYPES
from feast.permissions.action import ALL_ACTIONS, READ, AuthzedAction
from feast.permissions.permission import Permission
from feast.permissions.policy import RoleBasedPolicy
from feast.types import Float64, Int64

REPO = Path(__file__).resolve().parent
DATA = REPO.parent
# This eight-row snapshot is deliberately historical; it is never labeled live inventory.
demand = pd.read_csv(DATA / "demand.csv")
last_day = demand["date"].max()
window = demand[demand["date"] > (pd.Timestamp(last_day) - pd.Timedelta(days=7)).strftime("%Y-%m-%d")]
weekly = window.groupby("sku")["units"].sum()
forecasts = {m["sku"]: m for m in json.loads((DATA / "forecasts.json").read_text())["forecasts"]}
rows = []
for product in json.loads((DATA / "products.json").read_text()):
    sku = product["sku"]
    rows.append({"sku": sku, "event_timestamp": pd.Timestamp(last_day, tz="UTC"),
                 "units_last_7d": int(weekly[sku]), "avg_daily_units_7d": float(weekly[sku] / 7),
                 "stock": product["stock"], "reorder_point": product["reorder_point"],
                 "forecast_7d_units": float(forecasts[sku]["forecast_7d_units"])})
(REPO / "data").mkdir(exist_ok=True)
pd.DataFrame(rows).to_parquet(REPO / "data/aurora_features.parquet", index=False)

sku = Entity(name="sku", join_keys=["sku"], value_type=ValueType.STRING,
             description="Aurora Supply synthetic product SKU")
source = FileSource(name="aurora_historical_features", path=str(REPO / "data/aurora_features.parquet"),
                    timestamp_field="event_timestamp", description="2025 synthetic demand, inventory fixture, and measured Ray forecast")
inventory = FeatureView(name="aurora_inventory", entities=[sku], ttl=timedelta(days=730), online=True,
    source=source, schema=[Field(name="units_last_7d", dtype=Int64), Field(name="avg_daily_units_7d", dtype=Float64),
                          Field(name="stock", dtype=Int64), Field(name="reorder_point", dtype=Int64),
                          Field(name="forecast_7d_units", dtype=Float64)],
    description="Historical inventory and demand features reused by the replenishment workflow",
    tags={"company": "Aurora Supply", "data": "synthetic-CC0", "as_of": last_day})
replenishment = FeatureService(name="aurora_replenishment_features", features=[inventory],
                               description="Shared feature contract for forecasting and inventory decisions")
reader = Permission(name="aurora_feature_reader", types=ALL_RESOURCE_TYPES,
                    policy=RoleBasedPolicy(roles=["aurora-feast-reader"]), actions=[AuthzedAction.DESCRIBE] + READ)
writer = Permission(name="aurora_feature_writer", types=ALL_RESOURCE_TYPES,
                    policy=RoleBasedPolicy(roles=["aurora-feast-writer", "cluster-admin"]), actions=ALL_ACTIONS)
