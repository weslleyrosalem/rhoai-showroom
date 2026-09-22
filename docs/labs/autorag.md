# Native AutoRAG with OGX and pgvector

The showroom provides its own OGX server, PostgreSQL with pgvector, and a CPU embedding model: [paraphrase-multilingual-MiniLM-L12-v2](https://huggingface.co/sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2), Apache-2.0, 384 dimensions. The model is an external ecosystem asset, not a claim of Red Hat model certification.

The same Aurora policies and 12 ground-truth questions are uploaded to `aurora-data`. A dedicated `aurora-ogx-connection` Secret supplies `OGX_CLIENT_BASE_URL` and `OGX_CLIENT_API_KEY` for the internal OGX connection. The native 3.5.1 pipeline uses OGX; newer upstream MaaS-direct examples have a different contract.

```bash
python3 scripts/science.py native-submit --pipeline autorag
python3 scripts/science.py native-status --run-id <run-id>
```

The launcher resolves the current generation model from the showroom MaaS Secret. `notebooks/native-autorag-parameters.json` requests four patterns, `answer_correctness`, and the `speed` preset. Document IDs in the ground truth match the Markdown filenames.

Open **Develop & train → AutoRAG**, select **ai-showroom**, and open the completed optimization. The native results page displays the four-pattern leaderboard and generated indexing/inference notebook actions. Use the project Playground to compare model behavior. The lexical Aurora application remains a separately labeled baseline; adding OGX does not silently turn that application's TF-IDF into vector retrieval.

Acceptance: completed optimization, ranked patterns and real metrics, followed by indexing/deployment of a chosen pattern and a semantic retrieval test. Model registration or an OGX Ready condition alone does not prove AutoRAG optimization succeeded.

[Official pipeline source](https://github.com/red-hat-data-services/pipelines-components/tree/main/pipelines/training/autorag/documents_rag_optimization_pipeline).

## Versioned inputs and preserved results

`science.py upload` also writes documents and evaluation questions under a content-addressed `corpus/<hash>/` prefix. `native-submit` resolves that same prefix, preventing pipeline caching from reusing stale policies or ground truth after edits. Upload before submitting whenever the documents or questions change.

The initial optimization completed with real pgvector retrieval and saved 24 artifacts, including a pattern, per-question results, and generated indexing/inference notebooks. It started before the English-only requirement and is retained as historical validation; the published lab uses the subsequent English corpus.

After a successful run, use the configured workbench to preserve its measured results and test real semantic retrieval plus generation:

```bash
python scripts/science.py native-export --pipeline autorag --run-id <run-id>
python scripts/science.py native-infer --run-id <run-id> --question "What is the return deadline?"
```

The helper selects the highest measured optimization score, queries OGX `vector-io/query`, and sends the retrieved context to its `chat/completions` API. These are real embedding and pgvector operations. The optional `--use-responses` exercises the generated Responses API template; it returned an upstream incomplete-stream HTTP 500 in this cluster, so it is not the default acceptance path. Review all quality metrics before promotion. `optimization_max_rag_patterns=4` is an upper bound; the optimization can stop after fewer patterns.

## Measured English result

Run `cd14a959-02cf-428c-8bcb-9ac6a660b16c` succeeded on September 22, 2026, using content prefix `corpus/d7897df084530cf0`, 12 English questions, four patterns, and 36 S3 artifacts. Pattern3 led on answer correctness. The native dashboard showed the same four patterns and scores:

| Metric | Mean | Reported interval |
|---|---:|---|
| Answer correctness | 0.8129 | 0.6691–0.9188 |
| Faithfulness | 0.6228 | 0.5567–0.7327 |
| Context correctness | 0.8333 | 0.5833–0.9583 |
| Answer relevance | 0.6875 | 0.5833–0.8125 |

These measured scores leave substantial room for improvement. The same local LLM acts as generation model and relevance judge; that is a limitation, not independent verification. Twelve synthetic questions are a demonstration benchmark, not a production acceptance set. An earlier English attempt failed when the showroom MaaS token quota was exhausted; after a showroom-only quota increase, this bounded retry completed.

An earlier English run, `55d8089e-fff9-475e-93fc-6580126c734d`, scored 0.7747 on answer correctness and is retained as historical evidence. The table above reports the later run, not an average across attempts.

OGX registry metadata, uploaded files, and SQL/KV state use a dedicated 5 GiB PVC at `/opt/app-root/src/.ogx/distributions/rh`; pgvector has its own 5 GiB PVC. Both are required to retain a working pattern through a server restart. This image migrates the legacy `.llama` directory to `.ogx`; keeping database paths under `.llama` left them outside the mounted volume. The source now consistently uses `.ogx`. The operator uses Recreate for this single-replica stateful workload. An existing emptyDir deployment may need one operator-managed recreation when migrating to PVC because this operator version cannot merge the two volume types.

The OGX endpoint is internal and isolated by `aurora-ogx-private`. Only the showroom workbench, pipeline workflow pods, assistant, native AutoRAG service, and actual dashboard proxy may use port 8321. Unauthenticated test pods in the showroom and platform namespaces were denied, while the real dashboard proxy succeeded. This internal connection uses a placeholder API key; it is not an authentication boundary.

## Dashboard setup and result access

Bootstrap enables the native Technology Preview switches `automl: true` and `autorag: true` in `OdhDashboardConfig`. Missing switches default to false. These are real native pages, not the custom assistant UI. See the [official dashboard options](https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html/managing_resources/customizing-the-dashboard).

The native UI validates S3 endpoints. The internal connection uses the complete service hostname `showroom-s3.ai-showroom.svc.cluster.local`; a short `.svc` hostname is rejected for HTTP. A narrow egress policy permits only the native AutoML/AutoRAG services to reach this showroom S3 endpoint on port 8333.

## Durable semantic test drive

Native indexing run `6d4aa9a3-4439-41c1-ae8e-a59cde47c799` rebuilt the selected Pattern3 on the corrected persistent store: four documents, four chunks, zero failed documents. The resulting vector store is `vs_875b7763-c954-4c4a-aa1f-e55d2d33e682`. Semantic retrieval and generation passed both before and after an OGX-only restart, returning three relevant chunks and the 30-calendar-day return deadline with `returns-policy.md` cited.

In the configured workbench, open `05-native-autorag.ipynb` or run:

```bash
python scripts/science.py native-infer \
  --run-id cd14a959-02cf-428c-8bcb-9ac6a660b16c \
  --vector-store-id vs_875b7763-c954-4c4a-aa1f-e55d2d33e682 \
  --question "What is the return deadline?"
```

On a new cluster, run the selected pattern's generated indexing notebook or `documents-indexing-pipeline` with its saved indexing parameters. To create a fresh store, omit `vector_store_id`; then use the new ID from `indexing_report.settings.vector_store_binding`. The optimization's original store ID is historical after reindexing. Keep the original measured pattern and new index binding together; do not rewrite historical quality scores.
