# MLflow experiments and traces

The platform singleton runs in `redhat-ods-applications`; the workspace is `ai-showroom`. Workbench and workload identities use namespace-scoped Kubernetes authorization.

Open `notebooks/01-demand.ipynb`. Generate the synthetic dataset, inspect the chronological holdout, and publish the measured result. The model artifact is also uploaded to `s3://aurora-artifacts/models/forecast/latest.json` for the MCP backend.

The internal tracking endpoint is `https://mlflow.redhat-ods-applications.svc:8443/mlflow` with the injected service CA. `AURORA_MLFLOW_TRACKING_URI` selects this internal endpoint when the notebook webhook injects a public dashboard URI. Do not disable TLS verification.

The application sends current English test drives to **aurora-assistant-demo**, described as “Current English showroom test drive.” The original **aurora-assistant** experiment is preserved as a historical setup record; it includes earlier language/formula examples and initialization errors. Use the current experiment for the customer walkthrough. Historical traces are not renamed or deleted.

The application records explicit `CHAIN`, `RETRIEVER`, `TOOL`, `LLM`, and output `GUARDRAIL` spans after input policy checks. Each of the two actual MCP calls has its own tool span with the approved SKU and protocol status; arbitrary tool payloads, authorization headers, and credentials are not captured. It checks generated output before storing that output in any span. Blocked input creates no trace, and an unavailable output guardrail fails closed without recording the generated answer.

The LLM span converts the provider's actual `prompt_tokens`, `completion_tokens`, and `total_tokens` into the standard `mlflow.chat.tokenUsage` attributes `input_tokens`, `output_tokens`, and `total_tokens`. Only nonnegative integer counts with a consistent total are accepted, and the usage attribute appears once to avoid double counting. No prices or cost estimates are fabricated. Missing or invalid provider usage remains unreported. The model name and provider are recorded using the native MLflow attributes. The Overview token and Tool calls panels therefore depend on new real requests, not retroactive edits to historical traces. MLflow workspace artifacts use S3, so this client image includes boto3 and receives credentials from a Kubernetes Secret.

Acceptance: real parent/child runs, measured metrics, a downloadable model artifact, and a trace that can be retrieved after the request completes. An experiment appearing in the UI alone does not prove artifact upload succeeded.

[Official MLflow integration documentation](https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html/working_with_mlflow/installing-and-authenticating-mlflow-sdk_mlflow).

## Verified records

The distributed forecast parent run is `36ff7fb1b995454f9c6ff840ce211520`; its eight child runs and S3 model artifact were verified. Historical setup trace `tr-79086e46512f7aae798803c5c358d0f0` was retrieved with `aurora_replenishment`, `retrieve_tfidf`, `mcp_gateway_tools`, and `maas_inference` spans and saved output. These are real records from the September 22, 2026 validation.

Native pipeline automatic tracking emitted a missing nested run-ID warning. The documented `native-export` helper logs the real S3 artifact index and measured metrics explicitly. EvalHub's `eval-export` helper similarly preserves the actual evaluation result; neither workaround is presented as a fix to the automatic integration.

## Current test drive

Open **MLflow → Experiments → aurora-assistant-demo** after the updated app is deployed. Ask “Should I replenish AS-001? Explain the policy and required approval.” In the resulting trace, inspect the retrieval span, two named tool spans, the LLM usage, and the successful configured policy check. Compare the recorded proposal with the app's deterministic business card. Ask an unsupported policy question to demonstrate uncertainty, then verify that an explicitly blocked input produces no new trace containing that input.

The inventory rule distinguishes target stock from additional quantity: `target_stock = max(reorder_point, ceil(forecast_7d_units * 21 / 7))`; `recommended_quantity = max(0, target_stock - stock)`. The tool calculates these values. The model explains them without recomputing the proposal. No policy check is presented as factual truth verification.
