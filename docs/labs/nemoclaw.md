# NeMoClaw and OpenShell

**Status: integration research; no completed NeMoClaw deployment is claimed.** This is a required showroom extension, with its own acceptance gate.

These components have different jobs:

| Component | Role in the Aurora story |
|---|---|
| NeMo Guardrails | Check selected input/output content and policy rules |
| OpenShell | Constrain the execution environment, filesystem, processes, network, and inference access |
| NeMoClaw | Configure and operate an agent reference stack on top of OpenShell |
| MCP Gateway | Authenticate and govern access to the Aurora tools |
| EvalHub and Garak | Execute evaluations and preserve observable results |
| MLflow | Record experiment and application execution evidence |

NVIDIA describes NeMoClaw as a reference stack with agent onboarding, lifecycle operations, and provider routing built around OpenShell. Its topology is version-dependent; the current documentation distinguishes Docker-based operation from older Kubernetes-backed layouts. Do not assume that the workstation installer is an OpenShift operator. See the [NVIDIA overview](https://docs.nvidia.com/nemoclaw/latest/about/overview.html) and [architecture](https://docs.nvidia.com/nemoclaw/user-guide/deepagents/reference/architecture).

OpenShift AI 3.5 documents **OpenShell as Developer Preview**, using upstream artifacts and an agent-ops deployment guide. This classification does not automatically apply to every NeMoClaw component. See the [3.5 Developer Preview notes](https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html/release_notes/developer-preview-features_relnotes).

## Intended test drive

The agent proposes replenishment for one Aurora SKU. It can reach the approved MCP endpoint and the chosen MaaS inference endpoint. Its runtime credentials, shell access, and network permissions stay separate from the presenter's administrator identity.

Demonstrate one permitted tool request, one blocked outbound destination, and one blocked filesystem action. Inspect the policy decision and the application trace. Change an explicitly approved destination in the sandbox policy, repeat the request, and restore the policy afterward. Content guardrails and runtime isolation must each have their own observable tests.

## Acceptance gate

Record the exact NeMoClaw/OpenShell versions, deployment topology, image digests, service accounts, namespace, and kernel prerequisites. Confirm the sandbox is Ready, the chosen local model responds, tools require authentication, unknown egress is denied, protected filesystem access fails, and failures cannot silently bypass enforcement. A generic Pod with a NetworkPolicy is not evidence of OpenShell enforcement.

The Kubernetes OpenShell chart is documented as experimental and requires the Agent Sandbox controller. Review the [upstream Kubernetes setup](https://docs.nvidia.com/openshell/kubernetes/setup) and the OpenShift-specific Developer Preview guide before selecting a deployment path. Do not install a nested workstation container runtime into the shared cluster as an undocumented shortcut.

Keep this module out of the live presentation until these checks pass. The [security journey](../journeys/security.md) can still show the independently validated MCP and NeMo controls while this extension is completed.
