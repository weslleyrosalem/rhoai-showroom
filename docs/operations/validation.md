# Validation status

Validation started on **September 22, 2026 UTC**. This record separates actual functional tests, deployed resources, accepted schemas, and optional features. A Ready Deployment does not prove an entire journey works.

| Area | Observed evidence | Status |
|---|---|---|
| Namespace and storage | ai-showroom, quota, RBAC, and S3 storage are available | Deployed |
| Native observability | All six installed 3.5.1 dashboard tabs opened; actual Qwen/Llama graphs, model row, and filtered showroom-load Usage chart/table inspected | [Native dashboard walkthrough](native-dashboards.md) passed with documented query, time-window, and missing-series limits |
| MLflow | Training/evaluation artifacts exported; current English app traces show retrieval, two actual tools, LLM tokens, and output policy checks | Persisted trace data, native timeline, usage, and two post-fix native tool calls validated; two actual responses await human review |
| Tempo | Ready, 5 GiB persistent storage, 168-hour retention; authenticated query API passed at 07:27 UTC, with no traces in the six-hour search window | Workload integration not demonstrated; the validated Aurora trace path uses MLflow |
| GitOps | At 07:20 UTC: Synced/Healthy at source revision `d806cde`; cosmetic namespace drift restored within a 32-second observation window | Reconciliation and self-heal passed |
| GuideLLM | At 10:44 UTC: 36 persisted reports; latest completed block: 60 successes, 0 errors, 0 incomplete requests; earlier qualification failures remain in the full history | Sustained run active; reduced load September 22, 12:00–15:00 UTC; absolute deadline September 23 at 15:59 UTC |
| MaaS | Anonymous 401; standard 200; limited subscription 200→429; recovery 200 | Functional test passed |
| NeMo | Valid inputs/outputs allowed; synthetic email/secret/override blocked | Direct checks passed |
| MCP and IPP | Public SDK tools; 14 auth/input cases; unsafe output 403; checker outage 503; private bypass denials | Functional security gates passed |
| MCP catalog and lifecycle | Catalog source visible; native MCPServer handshake; isolated lifecycle protocol and denial tests | Functional gates passed |
| Aurora web app | Authenticated English response, sources, tools, live model, Ray forecast, MLflow trace; synthetic email blocked | Functional flow passed; a later factual prose error is preserved in the human-review queue, with the deterministic proposal still correct |
| Workbench inference and MaaS notebooks | September 22, 13:38–13:40 UTC: configurable 07 passed its test and six-request loop; real GuideLLM 08 completed 3/3 with no errors or incomplete requests; MaaS 09 discovery and one chat returned 200 with 156 provider-reported tokens | All three executed in the persistent Aurora Inference Demo kernel. GuideLLM observed 0.802 s mean latency and 40.46 ms client streaming TTFT across three requests; functional observation, not capacity or causal llm-d evidence |
| Workbench and DSPA | Running; actual distributed jobs and native optimization pipeline results inspected | Individual notebook and pipeline paths passed |
| Native Playground | Qwen chat; returns policy with clickable citation; unsupported facts rejected; actual MCP stock and proposal results | Browser test drive passed; temporary scoped MCP credential expires September 22 at 17:57 UTC |
| Native Trainer | Two CPU workers on distinct hosts; complete job, resource/pod/log tabs inspected; holdout MAE0.82070 vs baseline1.33036 | Distributed training and native Jobs UI passed |
| Feature Store | Feast0.65 Ready; eight-SKU materialization; authenticated200 and anonymous401 | Runtime and native overview, lineage, features, historical dataset, and connected Aurora Workbench passed |
| Prompt registry | Version1 @baseline and Version2 @demo visible with actual templates | Native version details passed; application runtime prompt remains separate |
| Ray | Succeeded with two distinct workers; eight forecast models published to MLflow and S3 | Distributed training passed |
| GPU models | Two Qwen4B replicas Ready on distinct hosts; 8/8 authorized requests, EPP +8, backend successful counts +2/+6; anonymous401 | Two-node routing passed; matched same-GPU engine comparison passed (48/48 requests); no causal distributed-routing efficiency claim |
| Private Qwen gateway | At 10:44 UTC: inherited autoscaler aligned with one fixed gateway replica; original serving pod and pod template preserved; anonymous401, two authorized200 responses in 0.484s and 0.417s | Access checks passed after the configuration fix; single CPU gateway is not highly available |
| AutoML | Native module, completed run, full training DAG and model leaderboard visible; Three models compared; SeasonalNaive_FULL signed MAE−0.571, RecursiveTabular_FULL−0.651, WeightedEnsemble_FULL−0.675 | Native three-model results UI passed |
| AutoRAG | Native module enabled; real DAG and four-pattern leaderboard visible; Pattern3 correctness0.8129 | Native results UI passed; real semantic query passed before and after restart |
| EvalHub/Garak | [Matched OWASP pair](../labs/owasp-evaluations.md):33 responses per target;both 42.42% ASR,14 detector hits;benchmark and overall Fail | Complete raw JSONL/HTML downloaded from MLflow and hash-verified;NeMo blocked 0/33 in this broader corpus;four probes, not all ten risks |
| Model onboarding/scoring | Native registry Available; pinned candidate created once; repeated apply stable; authenticated and unauthorized tests passed | Registration and native deployment association passed; bounded performance recorded as MEASURED_REFERENCE_ONLY; quality/safety/performance approval pending |
| OpenShell | Exact-subject authentication, denied alternate identity, network boundaries, agent filesystem restrictions, denied external egress, real MaaS inference | Private administrator-led preview passed the documented gates |
| Predictive TrustyAI | Native Project Settings shows installed; actual OVMS capture; baseline SPD0/DIR1, promotion SPD−0.30/DIR0.6667; demand drift measured | Functional metrics and native SPD/DIR chart history passed |
| MIG / NeMoClaw | Prerequisites and pinned deployment options researched | Not yet validated |

The earlier capacity plan had a conservative maximum of 11 physical GPUs, including pool maxima and upgrade surge. The user is revising capacity through Red Hat OCM; that earlier bound is not a verification of the current pool settings. The authorized hard ceiling remains 16 physical GPUs. Recalculate every pool maximum plus surge before further changes. A registered Ready node must also advertise allocatable GPUs before it counts as available inference capacity.

The private Qwen gateway previously alternated between one and two desired replicas: its local Deployment override conflicted with the inherited autoscaler's minimum. The profile now sets both autoscaler bounds to one through its per-Gateway ConfigMap. This keeps the existing demo topology and does not change GPU capacity or shared gateway defaults. This optional profile was applied separately; the core Argo application's healthy status is not evidence that it reconciles this ConfigMap. See the [private inference profile](https://github.com/weslleyrosalem/rhoai-showroom/tree/main/gitops/components/models/qwen-4b-private) for the reproducible configuration.

The original Garak quick run used a one-example DAN marker detector. A marker alone does not establish harmful behavior. The final [matched OWASP pair](../labs/owasp-evaluations.md) has complete per-response evidence and explicit matching thresholds: lower ASR is better; a zero-hit benchmark gate corresponds to an overall transformed score threshold of 1.0. Both final results fail consistently. The current deterministic NeMo regex rules do not improve the selected 33-response corpus. This is a four-probe subset mapped to the 2025 taxonomy, with separate controls and untested gaps for all ten risks; it is not full OWASP coverage. Report JSONL and HTML were explicitly uploaded through the workspace-aware MLflow SDK, then downloaded and SHA256-verified.

## Journey acceptance criteria

**Security:** authenticated initialize/tools-list/tools-call; anonymous and unauthorized identities denied; allowed and blocked inputs; observable decisions. Direct NeMo checks and MCP IPP enforcement are separate tests. Backend traces currently identify a shared service account, not an individual visitor.

**Platform:** responsive models, enforced quotas, curated catalog, converged Argo state, and measured benchmarks with complete configurations. Multi-node claims require evidence of distinct nodes.

**Data science:** successful Ray job, forecasts for every SKU with baseline/quality gate, published artifacts, RAG retrieval and actual MCP/MaaS calls, MLflow runs/traces, and completed evaluations with results.

## Repeat local checks

```bash
python -m unittest discover -s tests -p 'test_capacity.py'
python -m unittest discover -s tests -p 'test_benchmark.py'
python -m unittest discover -s tests -p 'test_science.py'
python -m unittest discover -s tests -p 'test_bootstrap.py'
python scripts/validate_repo.py
mkdocs build --strict
python scripts/showroom.py status --expected-server "$SHOWROOM_SERVER"
```

MCP tests require their own dependencies, documented in the Aurora Tools README. Sanitize cluster evidence before publishing. Credentials, private hostnames, and customer data do not belong in this public guide.

## Notebook rehearsal and extended presentation window

The three [Workbench notebooks](../labs/workbench.md) have editable endpoint/model settings, explicit authentication boundaries, and bounded requests. The MaaS key was supplied through the real Jupyter password-input channel; no key was written into notebook source or output. Its optional quota exercise remained disabled. The supplied synthetic approval answer identified the required Operations manager; successful transport alone is not a general model-quality verdict. The idempotent kernel setup also passed on the persistent Workbench without downloading packages or starting inference.

For the revised September 22 presentation, the sustained load's persistent rate cap is **0.05 requests/second through at least 12:30 p.m. Eastern**. The original runner retains concurrency 1 until 11:00 a.m. and a ceiling of 2 afterward; only the offered-rate cap was changed, without restarting the Job. The scheduled readiness check restores the prior cap after 12:30 p.m., preserving any later user change. The absolute September 23, 11:59 a.m. Eastern stop remains unchanged.
