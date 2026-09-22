# Aurora Supply: one connected story

Aurora Supply is a fictional office equipment distributor. Its catalog, inventory, policies, demand history, and evaluation cases are synthetic and versioned in this repository.

The customer scenario is concrete: select products, check availability, understand the applicable policy, and prepare a replenishment proposal. The proposal never creates an order or payment.

## Follow a question

| Step | Component | Evidence to show |
|---|---|---|
| Ask a question | Playground or Aurora application | Prompt, model, and selected subscription |
| Retrieve the relevant policy | RAG | Document IDs and retrieved excerpts |
| Check catalog and inventory | MCP Gateway and Aurora Tools | Actual tool calls and dataset values |
| Check the forecast | Model trained with Ray | Version, horizon, test metrics, and MLflow run |
| Generate an explanation | Local or external model through MaaS | Response, usage, and provider identity |
| Apply controls | AuthPolicy, quota, and NeMo | Positive/negative tests, status, and observable reason |
| Investigate the result | MLflow and metrics | A new Aurora application trace or current time series with source and time range |
| Improve the experience | Prompt, data, or manifest in Git | Diff, Argo CD sync, repeated test, and rollback |

The validated application trace path uses MLflow. Tempo has persistent storage and a working authenticated query API, but the six-hour acceptance search found no traces. Aurora workload integration with Tempo remains a follow-on exercise. Native Playground tool and citation panels are a separate inspection path.

Tools return structured data. The language model is not the source of truth for inventory, quotas, prices, or forecasts. Tests compare these values with the synthetic source artifacts.

## Names and contracts

| Name | Purpose |
|---|---|
| `rhoai-showroom` | Public repository and guide |
| `ai-showroom` | Primary project shown in the UI |
| `ai-showroom-bench` | Benchmarks requiring separate scheduling |
| `aurora-tools` | Read-only MCP tools and proposal calculations |
| `showroom-mcp` | MCP gateway and extension |
| `aurora-rag` | Retrieval, tools, LLM, and tracing application |
| `aurora-lab` | Data science Workbench |
| `showroom-s3` | S3-compatible demonstration data and artifact storage |
| `mlflow` | Shared platform-managed MLflow instance |
| `showroom-visitors` | Read access and authorized test drives |
| `showroom-data-scientists` | Project work and lab execution |
| `showroom-platform-admins` | Showroom project administration |

Operators and shared platform services stay in their own namespaces. MLflow is a cluster singleton in this version; the experience does not create an arbitrary server per project.

## Capacity profiles

The core uses CPUs for tools, retrieval, control services, experiments, and small training jobs. Inference can reuse an existing MaaS endpoint. GPU profiles add models and serving experiments.

This installation has a ceiling of **16 physical GPUs, including existing pools and temporary upgrade capacity**. MIG slices and time-slicing replicas do not increase physical GPU counts. The [capacity preflight](../labs/hardware.md) must pass before enabling a profile.

L40S supports the inference and tensor parallelism demonstrations. MIG requires compatible hardware such as A100 or H100 and its own validated profile. The labs distinguish MIG from time-slicing and measure efficiency instead of inferring it from GPU count.

## Three conversations about the same environment

- **Security:** “How do I limit what an agent can access or do, and investigate a decision?”
- **Platform:** “How do I publish, share, scale, and operate models as services?”
- **Data science:** “How do I test a hypothesis, train, evaluate, and turn the result into a useful experience?”

Keep the same business question when changing journeys. Show how the scientist's forecast reaches a tool, how the platform serves inference, and how security controls protect the flow. Application traces currently use a shared backend service account; do not present them as end-user attribution without implementing that mapping.
