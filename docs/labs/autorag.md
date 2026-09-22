# Native AutoRAG with OGX and pgvector

The showroom provides its own OGX server, PostgreSQL with pgvector, and a CPU embedding model: [paraphrase-multilingual-MiniLM-L12-v2](https://huggingface.co/sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2), Apache-2.0, 384 dimensions. The model is an external ecosystem asset, not a claim of Red Hat model certification.

The same Aurora policies and 12 ground-truth questions are uploaded to `aurora-data`. A dedicated `aurora-ogx-connection` Secret supplies `OGX_CLIENT_BASE_URL` and `OGX_CLIENT_API_KEY` for the internal OGX connection. The native 3.5.1 pipeline uses OGX; newer upstream MaaS-direct examples have a different contract.

```bash
python3 scripts/science.py native-submit --pipeline autorag
python3 scripts/science.py native-status --run-id <run-id>
```

The launcher resolves the current generation model from the showroom MaaS Secret. `notebooks/native-autorag-parameters.json` requests four patterns, `answer_correctness`, and the `speed` preset. Document IDs in the ground truth match the Markdown filenames.

Use the project Playground to compare the model and retrieval behavior. The lexical Aurora application remains a separately labeled baseline; adding OGX does not silently turn that application's TF-IDF into vector retrieval.

Acceptance: completed optimization, ranked patterns and real metrics, followed by indexing/deployment of a chosen pattern and a semantic retrieval test. Model registration or an OGX Ready condition alone does not prove AutoRAG optimization succeeded.

[Official pipeline source](https://github.com/red-hat-data-services/pipelines-components/tree/main/pipelines/training/autorag/documents_rag_optimization_pipeline).
