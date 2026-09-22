# Native AutoML for demand forecasting

This lab uses the operator-managed `autogluon-timeseries-training-pipeline`, version 3.5.1. It is a separate native AutoML experiment; the transparent ridge/seasonal baseline in the Ray lab is not labeled AutoML.

The same synthetic `demand.csv` contains SKU, date, units, promotion, price, and lead time. The native run uses `sku` as series ID, `date` as timestamp, `units` as target, a seven-day prediction horizon, one selected model, and the `speed` preset.

Upload the dataset from the configured workbench, then submit from an authenticated terminal:

```bash
python3 scripts/science.py native-submit --pipeline automl
python3 scripts/science.py native-status --run-id <run-id>
```

The reusable parameters are in `notebooks/native-automl-parameters.json`. The launcher discovers the pipeline and version instead of copying cluster-specific IDs. Do not force a generic `pipeline-runner` account: RHOAI uses its DSPA-specific allowed account by default.

The training step requests 4 CPUs and 16 GiB, plus workflow overhead. Ensure a worker has that much free allocatable capacity. A Pending pod is not an AutoML result.

Acceptance: completed native run, ranked leaderboard, measured holdout metrics, and actual model artifacts. Compare the selected forecast with the Ray baseline before changing the MCP model source.

[Upstream AutoGluon pipeline source](https://github.com/red-hat-data-services/pipelines-components/tree/main/pipelines/training/automl/autogluon_timeseries_training_pipeline). Installed 3.5.1 parameter schemas take precedence over newer upstream examples.
