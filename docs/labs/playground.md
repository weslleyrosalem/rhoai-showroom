# Native Playground: policies and governed inventory tools

**Business question:** What does Aurora Supply's policy allow, and what replenishment proposal can an assistant justify with real tools?

Open **Gen AI studio → Playground**, select **ai-showroom**, and compare the two configured models. Llama demonstrates plain model chat through the explicit `showroom-standard` MaaS subscription. Select **Aurora Qwen — tools and policy knowledge** (`aurora-qwen-4b`) for knowledge retrieval and tool calling: that pinned Qwen runtime enables automatic tool choice with the Hermes parser.

This is the actual OpenShift AI Playground. The separate Aurora web app provides its own guided business experience and remains a clearly identified application.

## Policy test drive

1. Select Qwen and start a fresh conversation.
2. Upload `data/playground/aurora-returns-policy.txt` as a knowledge source. The native uploader accepts TXT, PDF, or CSV, so the repository includes an exact TXT copy of the policy.
3. Ask: **According to Aurora Supply policy, what is the return deadline? Cite the policy file.**
4. Inspect the file-search operation and the returned source chunk. The expected answer is **30 calendar days after receipt**. The assistant must not authorize a refund or invent an exception.
5. Change the question to an unsupported fact, such as the refund bank-account number. The policy contains no such information; a confident invented number is a failed result, even if the request completed.

The native upload uses the actual IBM Granite 125M English embedding model with 768 dimensions and pgvector. The previously validated AutoRAG index uses MiniLM with 384 dimensions and remains separate. Its optimization score does not automatically apply to this Qwen/Granite combination.

## MCP test drive

1. Connect **Aurora Supply** from the MCP asset list using your own short-lived OpenShift token or the administrator-issued, scoped showroom visitor token in the native connection dialog. Do not paste tokens into chat, source files, or the ConfigMap. The current release uses an explicit MCP connection token; it does not automatically reuse the dashboard login for this connection.
2. Inspect and enable the read-only stock and replenishment tools.
3. Ask: **Use the Aurora tools to check stock and the replenishment recommendation for AS-001. State the proposed quantity, total, and approver. Do not create an order.**
4. Inspect the stock tool response, then ask **Call aurora_get_replenishment_recommendation for AS-001 and show the calculation and approval role.** Inspect that tool response in the new turn. The current UI may display only one tool-response panel when a turn calls multiple tools. The current historical fixture returns **346 units**, **14,532 demo currency units**, and **operations manager** approval. The result must say that no order was created.
5. Change the SKU and inspect how the grounded tool result changes. Explain why caller authorization, model behavior, and human approval are separate controls.

The gateway validates the actual caller and applies the existing MCP/NeMo controls. The default OGX service account is not granted tool access. Native Qwen serving also performs TokenReview and model-specific authorization; its placeholder provider credential cannot authorize a request.

## Connection and measured evidence

Qwen remains private: no public inference Route is added. A NetworkPolicy admits only the selected OGX pod to its internal Gateway on port 8080. That namespace-local hop uses HTTP; native KServe authentication and authorization remain mandatory. The original Llama model and its sustained load are unchanged.

On September 22, 2026, real user-authenticated `/v1/responses` calls completed with **file_search_call + message** in 5.35 seconds and **mcp_list_tools + two mcp_call items + message** in 2.03 seconds. These are individual acceptance timings, not performance benchmarks. The policy response contained the correct deadline and a raw document identifier; inspect the actual source chunk if the UI does not render a clickable citation.

The original Llama runtime returns a specific vLLM 400 for automatic tool choice because its parser flags are absent. The upstream streaming path exposed that as OGX 500. Selecting the tested Qwen model resolves this capability mismatch without restarting the original model. Plain Llama Responses generation remains valid.

Sources: [IBM Granite embedding model](https://huggingface.co/ibm-granite/granite-embedding-125m-english), [official OpenShift AI dashboard source](https://github.com/opendatahub-io/odh-dashboard/tree/main/packages/gen-ai).

## Native browser acceptance

The actual dashboard test drive passed on September 22, 2026: Qwen chat; TXT upload and retrieval; a clickable citation with the exact 30-day policy chunk; refusal to invent an absent bank-account number; and authenticated stock/replenishment tool use with the scoped `showroom-visitor` identity. The tool panels showed stock 45, forecast 130.26, target stock 391, proposal 346, total 14,532, `operations_manager`, the recorded MLflow run, and `order_created: false`. The forecast origin is December 31, 2025.

Before the exercise, set the Prompt tab to explain that all business data is synthetic and historical, answers require sources or tools, missing evidence must be acknowledged, and purchase execution requires human approval. Keep the model display's individual response timings separate from GuideLLM benchmark measurements.
