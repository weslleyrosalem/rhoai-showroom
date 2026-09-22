# EvalHub and Garak

EvalHub is deployed in the platform namespace after MLflow. PostgreSQL credentials stay outside Git. The showroom namespace is labeled as an EvalHub tenant. TrustyAI must use its full RHOAI mode: `mcpGuardrailsMode=false` includes both NeMo and EvalHub; `true` enables only the NeMo controller.

Set `EVALHUB_URL` to the discovered EvalHub Route, and set `MAAS_BASE_URL` and `MAAS_MODEL_ID` from your model connection. The evaluation references `showroom-maas-key`; do not paste an API key into a notebook or request file.

```bash
python3 scripts/science.py eval-submit
python3 scripts/science.py eval-status --job-id <job-id>
```

The installed Garak provider exposes benchmark `quick`. The API request uses `benchmarks[].id`, not `benchmark_id`. The smoke test runs one DAN probe against the local LLM and records measured metrics in MLflow.

## Interpretation and observed release limitations

Lower attack success rate is better. A measured rate of 1.0 means the single probe succeeded; this is a failed security benchmark, not a successful safety certification. Inspect each benchmark's `test.pass`; the observed aggregate pass flag was inconsistent with that benchmark.

The adapter reported HTML/JSONL artifact upload success while its MLflow PUT requests returned HTTP 307 and the S3 prefix was empty. Metrics and EvalHub results were present. Do not claim reports were persisted without checking the artifact store. MLflow with workspaces rejects a client-specified `artifact_location`, so disabling workspace isolation is not used as a workaround.

[EvalHub API source](https://github.com/eval-hub/eval-hub) and [TrustyAI operator](https://github.com/opendatahub-io/trustyai-service-operator).

## Preserve the measured result

Observed job `d0ac37c7-63ab-4335-93bf-b1a67508afdf` completed on September 22, 2026. Its benchmark metrics were recorded in MLflow run `54397cc5023c4427b9c69cacb51ed0fb`. The following workaround persisted and verified the actual EvalHub result JSON:

```bash
python3 scripts/science.py eval-export --job-id <job-id>
```

Run it from the configured workbench with `EVALHUB_URL=https://evalhub.redhat-ods-applications.svc:8443` and `EVALHUB_CA=/etc/service-ca/service-ca.crt`. The artifact is `evaluation/evalhub-result.json`. Original HTML/JSONL reports remain unavailable in this observed run. See [model scores and onboarding gates](model-score.md) for how failed or incomplete evidence affects promotion.
