# Data scientist and ML engineer journey

The business question is consistent throughout the showroom: **Should Aurora Supply replenish AS-001, and who must approve it?** Every dataset is synthetic and redistributable under CC0. Historical demand covers 2025; a forecast is never described as today's sales.

## A 20-minute demonstration

| Time | Action | Evidence |
|---|---|---|
| 0–3 min | Open the Aurora workbench and inspect products and demand | 8 SKUs, 2,920 daily observations, recorded seed and checksum |
| 3–7 min | Run the demand notebook | Chronological holdout, candidate versus baseline, measured MAE |
| 7–10 min | Open MLflow | Parent run, one child per SKU, model version and artifact |
| 10–16 min | Ask the assistant about AS-001 | Cited policies, governed MCP calls, forecast, human approval |
| 16–20 min | Inspect the MLflow trace and evaluation result | Retrieval/tool/inference spans and measured security result |

## A 45-minute workshop

Add the [Ray lab](../labs/ray.md), [native AutoML lab](../labs/automl.md), and [native AutoRAG lab](../labs/autorag.md). Compare the transparent lexical baseline with semantic search through OGX and pgvector. Review the generated leaderboard before deploying a selected model or RAG pattern.

Start expensive training and optimization before the presentation. Their execution time and capacity needs are visible in the pipeline UI; pending or failed runs must never be presented as completed.

## How the pieces connect

Synthetic demand → two Ray worker pods → measured quality gate → MLflow and S3 model artifact → read-only MCP replenishment tool → RAG assistant → MaaS LLM → input/output guardrails → MLflow trace → EvalHub evaluation.

The lightweight application uses **lexical TF-IDF**. The separate native AutoRAG path uses real sentence-transformer embeddings and pgvector. Ray demonstrates independent per-SKU training tasks, not distributed gradient training.

## Customer exercises

1. Change a synthetic inventory level in Git and review its deployment.
2. Change the prompt and inspect sources, tools, and the trace.
3. Compare a failed candidate with the accepted baseline.
4. Submit a new native pipeline run and inspect its resource requirements.
5. Explain why a one-probe Garak result cannot certify a model as safe.

Use the live validation report as the source of truth. Technology Preview and Developer Preview features keep their documented support status even when a demonstration succeeds.
