# Validation status

Validation started on **September 22, 2026 UTC**. This record separates actual functional tests, deployed resources, accepted schemas, and optional features. A Ready Deployment does not prove an entire journey works.

| Area | Observed evidence | Status |
|---|---|---|
| Namespace and storage | ai-showroom, quota, RBAC, and S3 storage are available | Deployed |
| MLflow | Available; migration succeeded; server 3.14.0; experiment metrics recorded | Functional services; integrated flows under test |
| Tempo | Ready, persistent storage, 168-hour retention | Service ready; workload spans need verification |
| GitOps | Operator services Running; application created | Reconciliation paused while validated fixes are consolidated |
| MaaS | Anonymous 401; standard 200; limited subscription 200→429; recovery 200 | Functional test passed |
| NeMo | Valid inputs/outputs allowed; synthetic email/secret/override blocked | Direct checks passed |
| MCP and IPP | Internal SDK calls and allow/deny tests passed; fail-closed behavior verified | Public-route protocol issue and catalog/lifecycle rehearsal in progress |
| Workbench, DSPA, Playground | Services Running; native pipeline runs submitted | Individual services ready; complete journeys under test |
| Ray | Succeeded with two distinct workers; eight forecast models published to MLflow and S3 | Distributed training passed |
| GPU models | Four-L40S node pool configured, at most 2 nodes; first node requested | Node registration, startup, and benchmarks pending |
| AutoML | Native managed pipeline succeeded; selected SeasonalNaive_FULL and published 23 S3 artifacts | Pipeline passed; automatic task tracking investigated separately |
| AutoRAG | First native pipeline succeeded with 24 S3 artifacts; English corpus rerun submitted | Initial execution passed; English quality review pending |
| EvalHub/Garak | A real quick evaluation completed; one probe, attack_success_rate 1, benchmark pass=false | Evaluation executed; safety did not pass this baseline |
| Model onboarding/scoring | Catalog available; candidate registry workflow being rehearsed | Complete promotion gate pending |
| MIG/OpenShell/NeMoClaw | Prerequisites and deployment options researched | Not yet validated |

The active cloud plan has a conservative ceiling of 16 physical GPUs, including existing pool maxima and upgrade surge. This does not mean 16 GPUs run continuously or that every profile can be combined.

The Garak quick run is a small baseline check, not a security certification. The aggregate evaluation status and per-benchmark result disagreed; use the per-benchmark result. The complete result JSON was explicitly exported through the MLflow SDK and confirmed in S3. Automatic report delivery is being checked separately from recorded metrics.

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
