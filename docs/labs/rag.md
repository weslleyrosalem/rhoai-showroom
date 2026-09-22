# RAG with an auditable decision

The Aurora application retrieves the versioned documents in `data/documents` with lexical TF-IDF, calls inventory tools through MCP Gateway, generates an answer through MaaS, checks input/output with NeMo Guardrails, and records an MLflow trace. The browser never receives a MaaS key.

Open the authenticated Aurora test drive and ask:

> Should I replenish AS-001? Check stock and the forecast, then explain the policy and required approval.

Check the cited document IDs, both MCP tool names, the historical forecast origin, and the approval role. Numeric business decisions should come from tool fields; a generated explanation is still subject to evaluation.

For an internal test from the workbench, POST `{"question":"What is the return deadline?"}` to `http://aurora-rag:8080/ask`. For local access, use `oc port-forward -n ai-showroom svc/aurora-rag 8080:8080`.

Acceptance: a real model response, existing source IDs, successful input/output checks, and a retrievable MLflow trace. Any upstream failure returns an error; the application does not generate a fake response.

For semantic embeddings and a vector database, use [native AutoRAG](autorag.md).
