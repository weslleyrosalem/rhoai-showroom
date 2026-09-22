# Project plan and operating model

The showroom serves one purpose: help a customer understand an AI platform by using it. Aurora Supply connects a replenishment question to documents, inventory tools, trained forecasts, model serving, access controls, and recorded evidence.

## Presentation priorities

| Session | Customer question | Required evidence |
|---|---|---|
| Inference, 8:00 a.m. Eastern | What changes when inference becomes a shared platform service? | A responsive endpoint, actual load history, vLLM prefix-cache counters, and an accurate explanation of llm-d's role |
| MaaS, 10:00 a.m. Eastern | How can teams consume models with controlled access and budgets? | A scoped key, successful request, enforced quota, recovery, and usage metrics |
| Follow-on exploration | Can we build, evaluate, and operate an application here? | The connected Aurora test drive, science runs, traces, and security checks |

The September 22, 2026 sessions use America/New_York time. The requested sustained GuideLLM run ends September 23, 2026 at 11:59 a.m. Eastern, or 15:59 UTC. Its configuration must reduce contention during the live sessions and stop automatically even when the assistant is disconnected.

## Delivery order

1. **Rehearse the available platform.** Confirm the existing model and capture real measurements. Separate local prefix reuse from distributed KV transfer; show only the benefits supported by this run's evidence.
2. **Collect useful load history.** Run bounded GuideLLM traffic with durable output, a dedicated consumer identity, sufficient credential lifetime, and an absolute deadline.
3. **Make one bounded capacity attempt.** Request capacity through Red Hat ROSA/OCM and monitor registered nodes through OpenShift. If it does not become available, retain the single-GPU presentation path and document which comparisons remain unavailable.
4. **Converge and clean up.** Reconcile the validated GitOps configuration, remove identified transient probes and failed experiments, and keep successful artifacts for inspection.
5. **Review the customer experience.** Follow each presentation script, test the scoped visitor flow, challenge security assumptions, fix failures, and inspect the published guide on desktop and mobile.

The maximum allocation remains 16 physical GPUs, including every pool's maximum and upgrade surge. Four-GPU nodes, multi-node comparisons, and MIG remain optional capabilities until the required hardware and runtime tests pass. L40S does not provide MIG.

## Workstreams and ownership

| Workstream | Scope | Handoff evidence |
|---|---|---|
| Platform and inference | vLLM, llm-d, cache, GuideLLM, MaaS, catalog, registry | Exact workload, versions, metrics, endpoints, quota tests, reproducible run commands |
| Data science and application | Ray, AutoML, AutoRAG, RAG, Workbench, MLflow, EvalHub | Run IDs, durable artifacts, quality results, traces, browser acceptance |
| Security and agents | MCP, NeMo, TrustyAI, OpenShell, NeMoClaw | Allowed and denied requests, identity boundaries, isolation tests, honest maturity |
| Integration and publication | Shared capacity, GitOps, design, documentation, release | Converged resources, checked links, usable runbooks, sanitized validation record |

Agents work on distinct files and maintain private checkpoints. One integration owner publishes and changes shared cloud capacity. Independent reviews focus on claims, failure paths, and actual customer interactions.

## Continuity and evidence

The project uses three layers of memory: a short private working-memory index, detailed private project and agent checkpoints, and this public plan with the [validation record](validation.md). Checkpoints include timestamps, decisions, evidence locations, next actions, and recovery commands. Automatic context compaction can occur; resumption depends on these files rather than conversation recall.

The repository's `AGENTS.md` and `.agents/skills/showroom-operations/SKILL.md` capture the repeatable workflow. Private access details and raw evidence stay outside Git. Existing user feedback about language, visual style, deadlines, capacity, API use, and cleanup is reflected here. Simulated customer reviews are labeled as reviews, never represented as feedback from an actual customer.

## Release criteria

The presentation path must work end to end, including access, one meaningful interaction, an observable result, and a recovery path. Optional features can remain documented experiments. A failed security evaluation remains visible as a failed result. A provisioned resource is not called a validated scenario, and a successful demo is not a production certification.
