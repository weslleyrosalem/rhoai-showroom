# Native AutoML for demand forecasting

This lab uses the operator-managed `autogluon-timeseries-training-pipeline`, version 3.5.1. It is a separate native AutoML experiment; the transparent ridge/seasonal baseline in the Ray lab is not labeled AutoML.

The same synthetic `demand.csv` contains SKU, date, units, promotion, price, and lead time. The native run uses `sku` as series ID, `date` as timestamp, `units` as target, a seven-day prediction horizon, up to three selected models, and the `speed` preset.

Open **Develop & train → AutoML**, select **ai-showroom**, and inspect the completed Aurora demand run. To start a new experiment, select time series and use the same dataset, SKU/date/units columns, seven-day horizon, and speed preset.

Upload the dataset from the configured workbench, then submit from an authenticated terminal:

```bash
python3 scripts/science.py native-submit --pipeline automl
python3 scripts/science.py native-status --run-id <run-id>
```

The reusable parameters are in `notebooks/native-automl-parameters.json`. The launcher discovers the pipeline and version instead of copying cluster-specific IDs. Do not force a generic `pipeline-runner` account: RHOAI uses its DSPA-specific allowed account by default.

The training step requests 4 CPUs and 16 GiB, plus workflow overhead. Ensure a worker has that much free allocatable capacity. A Pending pod is not an AutoML result.

Acceptance: completed native run, ranked leaderboard, measured holdout metrics, and actual model artifacts. Compare the selected forecast with the Ray baseline before changing the MCP model source.

[Upstream AutoGluon pipeline source](https://github.com/red-hat-data-services/pipelines-components/tree/main/pipelines/training/automl/autogluon_timeseries_training_pipeline). Installed 3.5.1 parameter schemas take precedence over newer upstream examples.

## Observed execution and artifact tracking

Run `8dfa1f96-ef23-48c1-b1fb-6a1dda7d7a78` succeeded on September 22, 2026. It selected `SeasonalNaive_FULL` and saved 23 artifacts, including the predictor, leaderboard, metrics, and generated notebook. The raw AutoGluon MAE score is −0.57142857 because AutoGluon maximizes signed scores; the corresponding error magnitude is 0.57142857 units. This pipeline's split differs from the Ray holdout, so the two numbers do not establish a fair ranking by themselves.

The automatic pipeline integration creates a finished MLflow parent run, but the task-level plugin emitted missing nested run-ID warnings and did not retain child metrics. To retain auditable model results, run this explicit export from the configured workbench after successful completion:

```bash
python scripts/science.py native-export --pipeline automl --run-id <run-id>
```

This records the actual S3 artifact index and metrics in `aurora-native-automl`. Verified export run: `f3509c3cd594443fbdd7524e4b363fc7`. It is an explicit SDK export, not evidence that the automatic plugin is fixed.

## Native dashboard access

Bootstrap sets the native `automl` Technology Preview dashboard switch to `true`. The completed run and full native results page were verified in the browser: the DAG succeeded, one retained model was shown, and `SeasonalNaive_FULL` had a signed MAE score of −0.571. The native results service reads the same S3 model artifacts: it requires the full internal `.svc.cluster.local` hostname and the targeted `showroom-native-ui-s3` egress policy for port 8333. This is independent of the optional automatic MLflow plugin.

The first validation retained only the winner (`top_n=1`). The reusable parameters now retain up to three models (`top_n=3`) under the same native speed preset and resource limits. Comparison run `b11f9d27-7c8c-4950-a4cd-22359bd1ef58` completed successfully and saved 79 artifacts. Its actual retained model results are: The installed pipeline does not expose a model allowlist; the native preset selects the candidates.

| Retained model | MAE error magnitude | Native signed MAE score |
|---|---:|---:|
| SeasonalNaive_FULL | 0.57143 | −0.57143 |
| RecursiveTabular_FULL | 0.65088 | −0.65088 |
| WeightedEnsemble_FULL | 0.67523 | −0.67523 |

The simpler seasonal model wins this synthetic benchmark. Model complexity alone does not establish better performance. Explicit MLflow export `27691fd9b1ee4afc8ef91fcc9d22677c` retains separate metrics for each model and identifies the winner; the original one-model run remains as earlier evidence.

The three-model run also has automatic MLflow parent `200c248538ee44008dcfca616d36c715`, verified as FINISHED with the actual pipeline ID tags. It has zero child runs and zero metrics; use the explicit export for measured results. This distinction prevents claiming the task-level integration is complete.
