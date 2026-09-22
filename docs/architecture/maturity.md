# Maturity and limitations

Product maturity and test results are separate dimensions. This table identifies documented 3.5 capabilities. The [validation record](../operations/validation.md) describes what actually ran in the showroom.

| Capability | Classification | Important boundary |
|---|---|---|
| Core MaaS, quotas, keys, and groups | GA | Keys expire and reflect consumer access |
| Core llm-d/vLLM | Product components; extensions have separate classifications | Capacity depends on runtime configuration and hardware |
| vLLM through MaaS, WVA, gateway discovery | Technology Preview | Verify the version and actual request path |
| Hierarchical KV cache, LoRA/latency routing | Developer Preview | Local prefix-cache reuse does not demonstrate tiering |
| MCP Gateway/Lifecycle | Technology Preview | OCP 4.22+, RHCL, authentication, authorization, compatible versions |
| MCP catalog administration through YAML in the UI | Developer Preview | A catalog entry is not a running server |
| Base NeMo Guardrails | GA since 3.4 | This example uses deterministic rules rather than an LLM classifier |
| NeMo with MCP IPP | Technology Preview | Plugins, validated TLS, and actual enforcement tests are required |
| MLflow | Integration left TP in 3.4 | SQLite and a single replica are lab choices |
| Inline Playground tracing | Technology Preview | MLflow application traces and Tempo inference traces are different flows |
| Saved Playground agents | Developer Preview | Requires a working configuration and clear maturity labeling |
| EvalHub MCP and UI comparisons | Technology Preview | Verify the backend and UI independently |
| OpenShell | Developer Preview in RHOAI 3.5; upstream Helm chart is experimental | Private runtime tested: subject authorization, filesystem/process/network controls, verified MaaS inference; unlimited PID cgroup remains a limitation |
| MIG | NVIDIA infrastructure feature | Unsupported on L40S; requires compatible A100/H100 hardware |
| External frontier models | Separate provider integration and contract | No local GPU, but provider credentials and budget are required |

See [Sources and versions](sources.md). A `v1alpha1` API suffix does not determine commercial support status on its own.

## Lab decisions

- Inventory, demand, documents, and test identities are synthetic. The application recommends and calculates; it does not place orders.
- Basic RAG uses TF-IDF and cites retrieved documents. Embeddings, pgvector, and AutoRAG are separate labs.
- S3, MLflow, and PostgreSQL persist data but do not provide high availability. Namespace quotas and RBAC are not a complete isolation boundary for hostile workloads.
- Engine benchmarks hold model, precision, and hardware constant. Scaling and routing experiments answer different questions. Regressions are valid results.
- MCP VirtualServer filtering affects discovery, not authorization. Test access to the actual call path.
