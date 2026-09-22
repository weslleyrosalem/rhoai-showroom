# Model scores and onboarding gates

A model score is meaningful only with its task, dataset, metric direction, sample size, model version, and evaluation configuration. The showroom keeps forecasting, answer quality, tool correctness, security, and serving performance as separate decisions.

## Read the measured scorecard

| Check | Measured evidence | Interpretation |
|---|---|---|
| Native AutoML | AutoGluon `SeasonalNaive_FULL`, MAE 0.57143; raw signed score −0.57143 | Lower MAE is better. This is the pipeline's evaluation split; it is not directly comparable with the Ray 28-day holdout. |
| Ray demand models | Eight accepted per-SKU forecasts; two actual worker pods | Candidates that lose to the training-only seasonal baseline fall back to that baseline. The holdout is used for model selection; reserve another period before a production claim. |
| Native AutoRAG | Generated pattern configuration, per-question results, aggregate metrics, and confidence intervals | Review answer correctness, grounding, context quality, and judge bias together. A completed pipeline can still produce weak answers. |
| Garak matched OWASP subset | Same 33 responses per target; baseline and NeMo both 14/33 detector hits, 42.42% ASR;benchmark and overall Fail | No measured improvement from the configured regex rails on this corpus. Read each detector predicate; this is not all ten risks or a count of real compromises. |
| Historical Garak `quick` | One DAN marker match; metric 1.0; benchmark failed | A marker match alone does not prove harmful compliance. The original raw response was not retained; use the new complete evidence pair for presentation. |
| MCP business tools | Deterministic inventory, price, approval role, and read-only behavior | The guided RAG app selects tools in code. Native Qwen tool calls are a separate functional test; neither is a statistical tool-selection benchmark. |

Use the [matched OWASP evaluation](owasp-evaluations.md) for exact final job IDs, MLflow runs, response artifacts, and the complete ten-risk map with explicit gaps. The observed equal ASR does not justify model promotion.

The first Garak evaluation is `d0ac37c7-63ab-4335-93bf-b1a67508afdf`, with MLflow run `54397cc5023c4427b9c69cacb51ed0fb`. The native AutoML run is `8dfa1f96-ef23-48c1-b1fb-6a1dda7d7a78`. These are observed showroom records, not IDs to copy into a new cluster.

## Inspect native EvalHub metadata

From the configured workbench, use the helper with your mounted identity:

```python
import sys
sys.path.insert(0, "scripts")
from science import eval_request
provider = eval_request("/api/v1/evaluations/providers/garak")
provider
```

Set `EVALHUB_URL=https://evalhub.redhat-ods-applications.svc:8443` and `EVALHUB_CA=/etc/service-ca/service-ca.crt`. Provider and benchmark metadata identify supported tasks, primary metrics, direction, and interpretation. Inspect the installed schema before constructing a different benchmark request. [Official EvalHub agent metadata documentation](https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html/evaluating_ai_systems/evalhub-mcp-server_evaluate).

```bash
python3 scripts/science.py eval-submit
python3 scripts/science.py eval-status --job-id <job-id>
python3 scripts/science.py eval-export --job-id <job-id>
```

EvalHub records benchmark thresholds and an overall result. Earlier runs defaulted to an overall threshold of 0.5, so their transformed aggregate passed while the strict benchmark gate failed. The final matched pair explicitly sets the overall threshold to 1.0 and the benchmark threshold to 0.0; both gates consistently fail. The onboarding gate therefore requires every mandatory benchmark to pass and requires a reviewer to resolve inconsistent aggregation. Do not promote this model on the observed score. [Official evaluation and threshold documentation](https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html/evaluating_ai_systems/evalhub-use-the-dashboard-to-evaluate-your-system_evaluate).

## Review before onboarding

1. Record model source, license, immutable revision, hardware requirements, and serving configuration.
2. Run domain quality evaluation against a versioned holdout and document the acceptance threshold before comparing candidates.
3. Evaluate safety on the base model and the guarded application separately; preserve failed examples and per-benchmark results.
4. Verify application behavior, authorization, quotas, latency, and resource use under the intended workload.
5. Attach evaluation artifacts and model identifiers to the approval record. A human approves promotion; an incomplete, failed, or inconsistent mandatory check blocks it.

EvalHub can generate evaluation cards with model, benchmark, result, and environment context when an experiment/export is configured. Verify the saved artifact rather than assuming that card generation guarantees persistence. The showroom exports the actual result JSON through the workspace-aware MLflow SDK because its adapter report uploads encountered HTTP 307. The final pair also preserves the complete raw JSONL and HTML reports through explicit SDK uploads and verifies downloaded hashes. [Official evaluation-card documentation](https://docs.redhat.com/documentation/red_hat_openshift_ai_self-managed/3.5/html/evaluating_ai_systems/evalhub-evaluation-cards_evaluate).

For model-driven tool selection, the 3.5 SDG Hub MCP evaluation workflow measures tool recall, precision, order, parameter matching, and judge dimensions. It requires a separate harness and benchmark adapter; the showroom has not executed it. A compatible local MaaS endpoint can replace the default external teacher/judge, so GPT access is not required. [Official MCP evaluation workflow](https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html/customize_models_for_gen_ai_and_agentic_ai_applications/generate-evaluation-data-for-tool-calling_custom-models).
