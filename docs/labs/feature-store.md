# Reuse Aurora demand features with the native Feature Store

**Business question:** Can the training team and the replenishment assistant use the same feature definitions?

Open **Develop & train → Feature store**, select the `aurora_supply` project, and inspect the `sku` entity, `aurora_inventory` feature view, and `aurora_replenishment_features` feature service. The feature view combines the final seven days of synthetic demand, the inventory fixture, and the forecast produced by the measured Ray run. The source data is historical, dated December 31, 2025; it is not today's warehouse inventory.

The native `FeatureStore/aurora-features` uses Feast 0.65.0 from the installed OpenShift AI operator, Kubernetes authorization, and separate persistent registry and online-store volumes. The native UI presents the reusable definitions. The workbench notebook performs the real online feature lookup.

## Test drive

1. Open `notebooks/06-feature-store.ipynb` in `aurora-lab`.
2. Run the query for `AS-001` and `AS-002`, then change a SKU to another product in `data/products.json`.
3. Compare the result with the catalog and Ray forecast. `AS-001` has stock **45**, units sold in the final seven days **129**, and forecast for the next seven days **130.26**. `AS-002` has **120**, **56**, and **54.75**, respectively.
4. Run the anonymous request test. It must return **401**. The workbench service account has read access through `aurora-feast-reader`; it has no feature-write permission.
5. Explain the promotion decision: centralizing features prevents separate teams from quietly implementing different inventory or demand calculations. It does not establish that the forecast is accurate or current.

## Bootstrap and refresh

The GitOps component creates the native feature store and role bindings. After its two containers are Ready, materialize the historical snapshot once:

```bash
oc exec -n ai-showroom deploy/feast-aurora-features -c online -- \
  python /feast-data/aurora_supply/data/feast/materialize.py
```

The operator runs `feast apply` on initialization. Materialization is an explicit data operation, not an invented readiness condition. It writes the actual eight-product snapshot to the persistent SQLite online store. Updating features requires reviewing the public definitions, applying them, and materializing the corresponding time range. The demo does not run an unbounded refresh job.

The workbench uses the injected service CA and its own short-lived service-account token. It never prints or stores that token. Read-only users can inspect and query features; only the separately bound writer identity can change definitions or materialize data.

## Evidence and limits

Runtime acceptance on September 22, 2026: native resource Ready, materialization successful, authenticated query **200** with the values above, anonymous query **401**. Dashboard presentation is verified separately in the showroom screen checklist. Persistence uses one replica and SQLite for a compact showroom; this is not a production high-availability design. The 730-day feature-view TTL keeps the explicitly historical dataset queryable during the demonstration.

Sources: [Red Hat OpenShift AI Technology Preview features](https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html/release_notes/technology-preview-features_relnotes), [official Feast operator](https://github.com/feast-dev/feast/tree/master/infra/feast-operator), [native API reference](https://github.com/feast-dev/feast/blob/master/infra/feast-operator/docs/api/markdown/ref.md).

## Historical dataset and connected workbench

The native **Saved datasets** tab contains `aurora_replenishment_contract_2025_12_31`. It is a real point-in-time join for all eight SKUs at the end of December 31, 2025, associated with `aurora_replenishment_features`. The saved Parquet data is retained on the registry PVC and was read back successfully. Its five features contain no missing values. This is a feature-contract validation dataset, **not a labeled model-training dataset**; no target labels or training accuracy are invented.

Select the dataset to review its event-time boundaries and feature references. Then open **Connected workbenches → Aurora Supply — Data Science Lab** and run Notebook 06. The `opendatahub.io/feast-config: aurora_supply` annotation and `opendatahub.io/feast-integration: true` label register that actual, tested connection for native discovery. The project may also show Feast's internal dummy entity; it is not a ninth Aurora product.

The saved-dataset API is experimental in the installed Feast release. The repeatable preparation script validates eight complete rows before retaining the result and overwrites only this specifically named synthetic snapshot on subsequent runs.

Observed native UI limitation: the generated saved-dataset snippet contains unquoted feature references, and the generated feature-view snippet omits the `timedelta` import. Those snippets are not executable as shown. Use the checked-in definitions and preparation script for a repeatable test drive; the actual dataset details and feature references are valid.
