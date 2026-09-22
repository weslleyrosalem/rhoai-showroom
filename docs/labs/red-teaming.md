# Security evaluation with EvalHub and Garak

Garak probes model behavior, NeMo enforces configured rails, and MCP Gateway controls tool access. An evaluation score does not certify universal safety. OpenShift AI 3.5 provides evaluation providers through EvalHub; its MCP interface is Technology Preview. See [EvalHub](https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html/evaluating_ai_systems/evaluating-llms-with-evalhub_evaluate) and [EvalHub MCP](https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html/evaluating_ai_systems/evalhub-mcp-server_evaluate).

## Prepare the experiment

Use an authorized synthetic target, an available model endpoint, and a healthy EvalHub database. Discover provider and benchmark IDs from the installed API; do not assume an old example matches the current request schema. Follow the [evaluation lab](evaluation.md) for this showroom's actual runs.

Compare two runs only when model, version, sampling, parameters, and test set match:

| Run | Target | What it measures |
|---|---|---|
| Baseline | Model chat endpoint | Model behavior without application rails |
| Guarded | Validated compatible guarded chat endpoint | Behavior of that integrated path |

NeMo `/v1/guardrail/checks` is not a chat-completions endpoint and is not an OpenAI Garak target. When only independent checks are available, show those checks alongside the baseline and label them separately.

For a live test drive, run a small supported benchmark and state its sample limit. Keep an earlier completed run available with its timestamp, settings, and artifacts. Show the job ID, terminal status, model, probes, sample count, metric direction, duration, and failure categories. A 401, 429, or network failure must not count as a successful safety block.

## OpenShell extension

The [OpenShift AI 3.5 release notes](https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html/release_notes/developer-preview-features_relnotes) list secure agent sandboxing with OpenShell as **Developer Preview**. The preview uses upstream artifacts. Separately, NVIDIA describes its [Kubernetes Helm chart](https://docs.nvidia.com/openshell/kubernetes/setup) as experimental and requires Agent Sandbox controllers/CRDs. These are distinct maturity statements; OpenShell is not generally available.

This showroom has not completed the OpenShell runtime acceptance gates. Keep it out of the ready-to-demo path until a separate `ai-showroom-sandbox` deployment proves compatible non-root execution, narrow privileges, filesystem/process isolation, allowed and denied egress, user authentication, persistence, and cleanup. Do not grant customers pod or Sandbox creation in that isolation namespace.

The proposed exercise lets an agent read one authorized synthetic file while blocking an out-of-policy network destination. Capture real policy decisions; do not label an untested sandbox as secure or deployed. The [OpenShift-aware compute driver](https://docs.nvidia.com/openshell/reference/sandbox-compute-drivers) does not replace testing on the installed ROSA runtime.
