# Security journey: accountable operational agents

Aurora Supply needs inventory answers and replenishment proposals without autonomous purchasing. The customer follows one request through documents, models, tools, and policy decisions, then inspects the evidence.

State the maturity boundaries before starting: MCP Gateway/Lifecycle and Playground tracing are Technology Preview; NeMo core is generally available; OpenShell is Developer Preview with a tested private runtime lab. Do not present documented modules as deployed.

## Twenty-minute presentation

| Time | Demonstration | Evidence |
|---|---|---|
| 0–2 | Introduce Aurora Supply and `ai-showroom` | Synthetic data and read-only scope |
| 2–6 | Request stock and a proposal for `AS-001` | Policy citations, forecast provenance, 21-day target, deterministic total and approver; no order |
| 6–9 | Open the new MLflow trace | Actual spans, tool calls, and latency |
| 9–12 | Compare missing, unlisted, and allowed MCP identities | 401, 403, and success |
| 12–15 | Run allowed and blocked NeMo checks | Exact rail and CPU execution |
| 15–18 | Compare the two [OWASP runs](../labs/owasp-evaluations.md) | Same 33 prompts; 42.42% ASR on both paths; explicit failed gates and rule limitations |
| 18–20 | Let the customer change one synthetic input | Reproducible result and explanation |

## Forty-five-minute workshop

| Time | Activity |
|---|---|
| 0–5 | Story, identity, maturity, and deployment status |
| 5–13 | Customer selects a SKU; RAG reads policies and MCP reads inventory |
| 13–19 | Inspect the trace, versioned prompt, forecast, and MLflow run |
| 19–25 | MCP authorization tests; discover the catalog card and managed server |
| 25–31 | NeMo checks and validated integrated blocking; explain open protocol gates |
| 31–36 | Discover an EvalHub provider; inspect the matched OWASP pair and complete raw reports |
| 36–40 | Discuss evaluation blind spots; OpenShell only if its acceptance gates have passed |
| 40–43 | Review a synthetic reorder-point change in Git, synchronize, and revert |
| 43–45 | Customer repeats the shortest test drive independently |

## Suggested prompts

- “Check stock for AS-001 and propose replenishment. Identify the forecast and policy used. Do not create an order.”
- “What is the delivery policy, and which document supports your answer?”
- “What changed between the previous evaluation and this run?”

Use only fictional sensitive text such as `customer@example.invalid` and `DEMO_SECRET_AURORA`. Explain that a paraphrase may evade a regex. This is an observable limitation, not a reason to hide a result.

## Acceptance

The tools return canonical SKUs and model provenance without side effects. The authenticated gateway rejects missing and unlisted identities; private endpoints do not bypass policy. NeMo distinguishes allowed, blocked, and failed checks. A fresh trace and an actual EvalHub run remain inspectable. Public MCP protocol and output-enforcement claims require their complete tests. The optional OpenShell lab demonstrates tested filesystem, process, network, identity, and real MaaS inference controls through its CLI/TUI; its unlimited PID cgroup remains a documented limitation. Existing `maas-how-to` demonstrations remain healthy.
