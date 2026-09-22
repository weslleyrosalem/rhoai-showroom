"""Materialize and retain an actual point-in-time Aurora feature-contract dataset."""
from pathlib import Path
from datetime import datetime, timezone
import json


def main():
    import pandas as pd
    from feast import FeatureStore
    from feast.infra.offline_stores.file_source import SavedDatasetFileStorage
    repo = Path(__file__).resolve().parent
    store = FeatureStore(repo_path=str(repo))
    # The installed operator has already run feast apply and generated this Parquet source.
    store.materialize(datetime(2025, 12, 31, tzinfo=timezone.utc), datetime(2026, 1, 1, tzinfo=timezone.utc))
    source = pd.read_parquet(repo / "data/aurora_features.parquet")
    if set(pd.to_datetime(source.event_timestamp).dt.strftime("%Y-%m-%d")) != {"2025-12-31"}:
        raise ValueError("This named historical contract requires the documented 2025-12-31 snapshot")
    entities = source[["sku", "event_timestamp"]].copy()
    entities["event_timestamp"] = entities["event_timestamp"] + pd.Timedelta(hours=23, minutes=59, seconds=59)
    service = store.get_feature_service("aurora_replenishment_features")
    retrieval = store.get_historical_features(entity_df=entities, features=service)
    rows = retrieval.to_df()
    expected = {"AS-%03d" % i for i in range(1, 9)}
    if len(rows) != 8 or set(rows.sku) != expected or rows.isna().any().any():
        raise RuntimeError("The point-in-time contract must contain eight complete product rows")
    destination = Path("/data/registry/datasets/aurora_contract_2025_12_31.parquet")
    destination.parent.mkdir(exist_ok=True)
    saved = store.create_saved_dataset(
        from_=retrieval,
        name="aurora_replenishment_contract_2025_12_31",
        storage=SavedDatasetFileStorage(path=str(destination)),
        tags={"purpose": "Historical point-in-time feature-contract validation; no training labels",
              "as_of": "2025-12-31", "company": "Aurora Supply", "data": "synthetic-CC0"},
        feature_service=service,
        allow_overwrite=True,
    )
    restored = saved.to_df()
    assert len(restored) == 8
    print(json.dumps({"dataset": saved.name, "rows": len(restored), "columns": list(restored.columns),
                      "purpose": "historical feature-contract validation, not a labeled training dataset",
                      "storage": str(destination), "retrieval_verified": True}))


if __name__ == "__main__":
    main()
