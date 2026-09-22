# Security evaluation with EvalHub and Garak

Garak probes model behavior, NeMo enforces configured rails, and MCP Gateway controls tool access. An evaluation score does not certify universal safety. OpenShift AI 3.5 provides evaluation providers through EvalHub; its MCP interface is Technology Preview. See [EvalHub](https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html/evaluating_ai_systems/evaluating-llms-with-evalhub_evaluate) and [EvalHub MCP](https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html/evaluating_ai_systems/evalhub-mcp-server_evaluate).

## Prepare the experiment

Use an authorized synthetic target, an available model endpoint, and a healthy EvalHub database. Discover provider and benchmark IDs from the installed API; do not assume an old example matches the current request schema. Follow the [matched OWASP lab](owasp-evaluations.md) for the actual 33-response baseline/NeMo pair, precise detector interpretation, and all ten 2025 risks with explicit gaps.

Compare two runs only when model, version, sampling, parameters, and test set match:

| Run | Target | What it measures |
|---|---|---|
| Baseline | Model chat endpoint | Model behavior without application rails |
| Guarded | Validated compatible guarded chat endpoint | Behavior of that integrated path |

NeMo `/v1/guardrail/checks` is not a chat-completions endpoint and is not an OpenAI Garak target. When only independent checks are available, show those checks alongside the baseline and label them separately.

For a live test drive, run a small supported benchmark and state its sample limit. Keep an earlier completed run available with its timestamp, settings, and artifacts. Show the job ID, terminal status, model, probes, sample count, metric direction, duration, and failure categories. A 401, 429, or network failure must not count as a successful safety block.

## OpenShell extension

The [OpenShift AI 3.5 release notes](https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html/release_notes/developer-preview-features_relnotes) list secure agent sandboxing with OpenShell as **Developer Preview**. The preview uses upstream artifacts. Separately, NVIDIA describes its [Kubernetes Helm chart](https://docs.nvidia.com/openshell/kubernetes/setup) as experimental and requires Agent Sandbox controllers/CRDs. These are distinct maturity statements; OpenShell is not generally available.

The private `ai-showroom-sandbox` extension is deployed and passed a real runtime rehearsal. Its administrator-led test drive shows a non-root agent with zero effective capabilities, no-new-privileges, seccomp, and Landlock ABI 6. A write under `/tmp` succeeds; a write under `/var/tmp`, TLS private-key reads, and service-account token reads fail. An unapproved Internet destination returns proxy 403. A request through `https://inference.local` reaches the existing MaaS model and returns HTTP 200 with verified TLS.

The gateway has no public Route. A front proxy requires the exact administrative service-account subject using TokenReview; another valid service account with the same audience, anonymous callers, and forged tokens are denied. Native sandbox identities retain the gateway's signature and same-sandbox checks. Network policies block direct backend access and unrelated pods. Customer showroom roles cannot create pods, Sandbox resources, or port-forwards in this namespace.

Follow the [version-pinned installer, review, and validation commands](https://github.com/weslleyrosalem/rhoai-showroom/blob/main/gitops/components/guardrails/openshell/README.md). Demonstrate with `openshell sandbox exec` and the OpenShell terminal UI; `oc exec` bypasses the agent enforcement path and is not a valid isolation test. Renew the short-lived CLI token before the session. This is a CLI/TUI extension; it does not imply a native OpenShift AI OpenShell tab or a complete NeMoClaw deployment.

The supervisor reports an unlimited runtime PID cgroup. No global node setting was changed, and the lab does not claim complete resource-exhaustion protection or production certification. Re-run the acceptance checks after changing the kernel, chart, image, authentication adapter, or policy. The [OpenShift-aware compute driver](https://docs.nvidia.com/openshell/reference/sandbox-compute-drivers) does not replace that verification.
