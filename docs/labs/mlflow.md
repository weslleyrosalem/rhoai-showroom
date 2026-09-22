# MLflow experiments and traces

The platform singleton runs in `redhat-ods-applications`; the workspace is `ai-showroom`. Workbench and workload identities use namespace-scoped Kubernetes authorization.

Open `notebooks/01-demand.ipynb`. Generate the synthetic dataset, inspect the chronological holdout, and publish the measured result. The model artifact is also uploaded to `s3://aurora-artifacts/models/forecast/latest.json` for the MCP backend.

The internal tracking endpoint is `https://mlflow.redhat-ods-applications.svc:8443/mlflow` with the injected service CA. `AURORA_MLFLOW_TRACKING_URI` selects this internal endpoint when the notebook webhook injects a public dashboard URI. Do not disable TLS verification.

The application sends current English test drives to **aurora-assistant-demo**, described as “Current English showroom test drive.” The original **aurora-assistant** experiment is preserved as a historical setup record; it includes earlier language/formula examples and initialization errors. Use the current experiment for the customer walkthrough. Historical traces are not renamed or deleted.

The application records explicit `CHAIN`, `RETRIEVER`, `TOOL`, `LLM`, and output `GUARDRAIL` spans after input policy checks. Each of the two actual MCP calls has its own tool span with the approved SKU and protocol status; arbitrary tool payloads, authorization headers, and credentials are not captured. It checks generated output before storing that output in any span. Blocked input creates no trace, and an unavailable output guardrail fails closed without recording the generated answer.

The LLM span converts the provider's actual `prompt_tokens`, `completion_tokens`, and `total_tokens` into the standard `mlflow.chat.tokenUsage` attributes `input_tokens`, `output_tokens`, and `total_tokens`. Only nonnegative integer counts with a consistent total are accepted, and the usage attribute appears once to avoid double counting. No prices or cost estimates are fabricated. Missing or invalid provider usage remains unreported. The model name and provider are recorded using the native MLflow attributes. The Overview token panel reflects new real requests, not retroactive edits to historical traces. The native Tool calls aggregate was verified after the export correction described below. It covers requests indexed by the corrected path; older trace artifacts remain separate evidence and were not backfilled. MLflow workspace artifacts use S3, so this client image includes boto3 and receives credentials from a Kubernetes Secret.

Acceptance: real parent/child runs, measured metrics, a downloadable model artifact, and a trace that can be retrieved after the request completes. An experiment appearing in the UI alone does not prove artifact upload succeeded.

[Official MLflow integration documentation](https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html/working_with_mlflow/installing-and-authenticating-mlflow-sdk_mlflow).

## Verified records

The distributed forecast parent run is `36ff7fb1b995454f9c6ff840ce211520`; its eight child runs and S3 model artifact were verified. Historical setup trace `tr-79086e46512f7aae798803c5c358d0f0` was retrieved with `aurora_replenishment`, `retrieve_tfidf`, `mcp_gateway_tools`, and `maas_inference` spans and saved output. These are real records from the September 22, 2026 validation.

Native pipeline automatic tracking emitted a missing nested run-ID warning. The documented `native-export` helper logs the real S3 artifact index and measured metrics explicitly. EvalHub's `eval-export` helper similarly preserves the actual evaluation result; neither workaround is presented as a fix to the automatic integration.

## Current test drive

Open **MLflow → Experiments → aurora-assistant-demo**. Ask “Should I replenish AS-001? Explain the policy and required approval.” In the resulting trace, inspect the retrieval span, two named tool spans, the LLM usage, and the successful configured policy check. Compare the recorded proposal with the app's deterministic business card. Ask an unsupported policy question to demonstrate uncertainty, then verify that an explicitly blocked input produces no new trace containing that input.

The inventory rule distinguishes target stock from additional quantity: `target_stock = max(reorder_point, ceil(forecast_7d_units * 21 / 7))`; `recommended_quantity = max(0, target_stock - stock)`. The tool calculates these values. The model explains them without recomputing the proposal. No policy check is presented as factual truth verification.

## Current measured acceptance

Validated on 2026-09-22 06:42 UTC using app source `6888e2f`. Provider-reported usage and persisted trace-level usage matched exactly. These records belong to the current English experiment; historical setup traces were retained.

| Case | Total tokens | Expected result |
|---|---:|---|
| AS-001 | 1,762 | Target 391; proposal 346 units; total 14,532; Operations manager |
| AS-002 | 1,827 | Target 165; proposal 45 units; total 5,625; Operations manager |
| Unsupported bank account | 876 | Unavailable in the sources; no inventory tools |

Proposal totals use demo currency units; token totals are provider-reported usage. Exact persisted records:

- AS-001: `tr-5732c21d448c07449dddaac3945e47b1`; 1,417 input and 345 output tokens.
- AS-002: `tr-1ff4b801d3a9b9daee013f5af3f6da1d`; 1,418 input and 409 output tokens.
- Unsupported question: `tr-c175b6592f0da9011a0cfcc06492092f`; 855 input and 21 output tokens.

Each SKU request persisted seven spans: two `CHAIN`, one `RETRIEVER`, two `TOOL`, one `LLM`, and one `GUARDRAIL`. The non-SKU question persisted four spans without tool calls. Recorded model: `redhataillama-31-8b-instruct`; recorded provider: **OpenShift AI MaaS**. Total measured usage across these three requests was 4,465 tokens. The application recorded no cost.

A synthetic email plus automatic-purchase request returned HTTP 422. The current experiment contained three traces before and three after that request; the blocked input marker was absent from all three persisted traces. This demonstrates the configured policy and trace-capture boundary, not general factual or safety certification.

AS-002 changes the quantity and total, but **does not change the approver**: its total of 5,625 still exceeds the 5,000 threshold. The app's deterministic card and typed trace decision remain the authoritative numeric proposal.

The current inventory policy is revision 1.1 and its source-addressed S3 corpus is `corpus/90f7574ec40ae483`. Earlier AutoRAG run artifacts and corpus prefixes are preserved as historical evaluation evidence; changing the source does not retroactively change those measured results.

## Human review test drive

Open **MLflow → Experiments → aurora-assistant-demo → Review** and select **Aurora — proposal evidence review**. The prepared queue contains two actual English AS-001 traces, with **All (2)**, **Needs review (2)**, and **Completed (0)**. One has the correct approval explanation; the other is the factual-comparison counterexample documented below. The question **Tool evidence and human approval** asks the reviewer to assess the proposal against the tool evidence and human-approval policy.

Choose **Start review**, then **View full trace** before deciding: the queue's response preview is truncated. Inspect the complete answer, stock/forecast tool evidence, deterministic proposal, and policy citations. Select **Pass** or **Fail** based on that evidence, write a rationale, and submit only your own review. A pass should require the supported quantity, correct approval requirement, explicit synthetic/historical limits, and no executed purchase. A fluent answer alone is insufficient.

The prepared state has neither verdict selected, an empty rationale, disabled Submit, and **0 of 2 reviewed (0%)**. No customer feedback or review score was fabricated. The assigned traces are `tr-b212bc59aa6c8c3fa670e460035e7b52` and `tr-bb711365fcde120b0dd4eb5f6302278c`. Both remain pending; no verdict has been submitted.

## Native span export: correction and measured acceptance

The installed MLflow layout serves REST/artifact APIs below `/mlflow`, while native OpenTelemetry ingestion is `/v1/traces` on the same HTTPS service. The app adds a standard HTTP OTLP exporter to the existing provider. It uses a new export copy with MLflow 3.14's SDK attributes decoded, preserving the original trace/span IDs, events, and artifact spans. Nine focused tests passed in the pinned app image, including an actual exporter-protobuf → native-parser round trip for `TOOL`, integer token usage, and unchanged originals. [MLflow 3.14 provider configuration](https://github.com/mlflow/mlflow/blob/v3.14.0/mlflow/tracing/provider.py), [native tool-count query](https://github.com/mlflow/mlflow/blob/v3.14.0/mlflow/server/js/src/experiment-tracking/pages/experiment-overview/hooks/useToolCallStatisticsData.ts).

The exporter verifies the service CA, accepts only the exact same-origin endpoint, rejects redirects, and rereads the projected workload token for every export. Workspace and experiment authorization remain in force; credentials never become span attributes. It initializes once under a lock, creates no second trace tree, and never skips NeMo checks if export fails. The shared MLflow server is unchanged.

**Historical first attempt, before the conversion correction:** `tr-bb711365fcde120b0dd4eb5f6302278c` persisted seven unique artifact spans and 1,881 tokens (1,580 input, 301 output). The native index received seven spans, but double-encoded attributes left the exact `span.type = 'TOOL'` filter and Tool calls panel empty. That partial result is retained as evidence; it is not the current outcome, and its index entries were not rewritten.

**Corrected path, validated 2026-09-22 07:16 UTC:** one authenticated browser request produced `tr-c966e381abfbfeb0d90f5c0dc0ac541f`, seven unique spans, two `TOOL` spans, and **1,823 tokens** (1,414 input, 409 output) recorded once. The exact native tool filter returned one successful stock call and one successful replenishment call. **Overview → Tool calls** showed **2 calls**, **100% success**, **0 failures**, and **101 ms** average latency; tool-usage and latency charts rendered.

The count of two covers **that one request through the corrected export path**, not the complete six-trace history. All six trace-level records totaled **9,950 tokens** (8,098 input, 1,852 output), matching the native Usage panel without duplication. Historical artifact traces and the earlier malformed index remain unchanged. The UI explicitly reported **No cost data available**; its zero-dollar headline does not establish zero monetary cost.

The app now displays the deterministic proposal before the generated explanation and explicitly requires factual review. The final request correctly explained 346 units × 42 = 14,532 demo currency units, Operations manager approval, and no created order. Export conversion fixes observability, not model reasoning: in the preserved earlier `tr-bb711365fcde120b0dd4eb5f6302278c` answer, one sentence incorrectly compared the **346-unit quantity** with the **5,000-currency-unit threshold**, even though its deterministic card was correct. The configured safety check does not verify that arithmetic or factual comparison. Use the two pending review cases to examine this difference; do not erase the counterexample, claim general factual accuracy, or manufacture a passing assessment.
