# Validation status

Validation started on **September 22, 2026 UTC**. This record separates actual functional tests, deployed resources, accepted schemas, and optional features. A Ready Deployment does not prove an entire journey works.

| Area | Observed evidence | Status |
|---|---|---|
| Namespace and storage | ai-showroom, quota, RBAC, and S3 storage are available | Deployed |
| MLflow | Available; training/evaluation artifacts exported; real application trace fetched with span data | Integrated persistence passed |
| Tempo | Ready, persistent storage, 168-hour retention | Service ready; workload spans need verification |
| GitOps | Synced/Healthy after native feature integration; cosmetic namespace drift restored within a 32-second observation window | Reconciliation and self-heal passed |
| GuideLLM | Actual pilot: seven successful requests, zero errors; persisted reports; interactive control HTTP200 in 1.102s during load | Sustained run active, deadline September 23 at 15:59 UTC |
| MaaS | Anonymous 401; standard 200; limited subscription 200→429; recovery 200 | Functional test passed |
| NeMo | Valid inputs/outputs allowed; synthetic email/secret/override blocked | Direct checks passed |
| MCP and IPP | Public SDK tools; 14 auth/input cases; unsafe output 403; checker outage 503; private bypass denials | Functional security gates passed |
| MCP catalog and lifecycle | Catalog source visible; native MCPServer handshake; isolated lifecycle protocol and denial tests | Functional gates passed |
| Aurora web app | Authenticated English response, sources, tools, live model, Ray forecast, MLflow trace; synthetic email blocked | Public test drive passed |
| Workbench, DSPA, Playground | Services Running; native pipeline runs submitted | Individual services ready; complete journeys under test |
| Native Trainer | Two CPU workers on distinct hosts; complete job, resource/pod/log tabs inspected; holdout MAE0.82070 vs baseline1.33036 | Distributed training and native Jobs UI passed |
| Feature Store | Feast0.65 Ready; eight-SKU materialization; authenticated200 and anonymous401 | Runtime passed; native UI review in progress |
| Prompt registry | Version1 @baseline and Version2 @demo visible with actual templates | Native version details passed; application runtime prompt remains separate |
| Ray | Succeeded with two distinct workers; eight forecast models published to MLflow and S3 | Distributed training passed |
| GPU models | Two Qwen4B replicas Ready on distinct hosts; 8/8 authorized requests, EPP +8, backend successful counts +2/+6; anonymous401 | Two-node routing and backend use passed; comparative efficiency not measured |
| AutoML | Native module, completed run, full training DAG and model leaderboard visible; Three models compared; SeasonalNaive_FULL signed MAE−0.571, RecursiveTabular_FULL−0.651, WeightedEnsemble_FULL−0.675 | Native three-model results UI passed |
| AutoRAG | Native module enabled; real DAG and four-pattern leaderboard visible; Pattern3 correctness0.8129 | Native results UI passed; real semantic query passed before and after restart |
| EvalHub/Garak | A real quick evaluation completed; one probe, attack_success_rate 1, benchmark pass=false | Completed marker test; meaningful security assessment under review |
| Model onboarding/scoring | Native registry Available; pinned candidate created once; repeated apply stable; authenticated and unauthorized tests passed | Registration passed; candidate safety/performance approval pending |
| OpenShell | Exact-subject authentication, denied alternate identity, network boundaries, agent filesystem restrictions, denied external egress, real MaaS inference | Private administrator-led preview passed the documented gates |
| MIG / NeMoClaw | Prerequisites and pinned deployment options researched | Not yet validated |

The active cloud configuration has a conservative maximum of 11 physical GPUs, including every pool maximum and upgrade surge. The user-authorized hard ceiling is 16. These are allocation bounds, not the number of GPUs running continuously, and optional profiles cannot be combined without recalculating them.

The original Garak quick run used a DAN marker detector with one example. A matched marker is not sufficient evidence of harmful behavior; its result is being replaced by a better documented assessment with retained responses. The UI percentage is the attack-success metric, not a safety score. The aggregate evaluation status and per-benchmark result disagreed; use the per-benchmark result. The complete result JSON was explicitly exported through the MLflow SDK and confirmed in S3. Automatic report delivery is being checked separately from recorded metrics.

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
