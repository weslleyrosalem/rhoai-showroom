# NeMoClaw and OpenShell

**Status: blocked for the existing Kubernetes gateway in the pinned release.** OpenShell has passed its separate private runtime checks; NeMoClaw onboarding and an agent turn have not been completed.

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

## Version compatibility under review

The upstream NeMoClaw tag `v0.0.127` resolves to commit `37ca4cb4220265c2a12b9d9b8a120d0d23a338dd`. Its blueprint requires OpenShell `0.0.116` as both its minimum and maximum version, matching this showroom's OpenShell deployment work. It pins the OpenClaw sandbox image to `sha256:b3d832b596ab6b7184a9dcb4ae93337ca32851a4f93b00765cc12de26baa3a9a` and includes a vLLM-compatible inference profile. This is a compatibility finding, not a completed NeMoClaw run. [Pinned upstream blueprint](https://github.com/NVIDIA/NemoClaw/blob/37ca4cb4220265c2a12b9d9b8a120d0d23a338dd/nemoclaw-blueprint/blueprint.yaml).

## Verified integration limit

The pinned NeMoClaw release offers an experimental external-target path for configuration planning and a public health request. NVIDIA explicitly excludes Kubernetes and machine authentication from that path; it cannot manage sandbox lifecycle or policies. The showroom uses an existing Kubernetes gateway with required authentication, so this path does not satisfy the deployment contract. [Pinned external-target documentation](https://github.com/NVIDIA/NemoClaw/blob/37ca4cb4220265c2a12b9d9b8a120d0d23a338dd/docs/about/how-it-works.mdx#inspect-an-external-openshell-gateway).

The blueprint runner rejects `apply` when `openshell_target` is present. Its corresponding test verifies that rejection occurs before a subprocess or run-state change. This is a source-verified limit; the upstream test was inspected, not executed in this showroom. [Pinned runner](https://github.com/NVIDIA/NemoClaw/blob/37ca4cb4220265c2a12b9d9b8a120d0d23a338dd/nemoclaw/src/blueprint/runner.ts#L1715), [upstream rejection test](https://github.com/NVIDIA/NemoClaw/blob/37ca4cb4220265c2a12b9d9b8a120d0d23a338dd/nemoclaw/src/blueprint/runner-external-target.test.ts#L230).

No NeMoClaw sandbox was created, no agent trace was produced, and no additional GPU capacity was requested. Deploying the pinned OpenClaw image alone would not demonstrate NeMoClaw onboarding or lifecycle management. Revisit this lab when the official workflow supports authenticated external Kubernetes gateways, then rerun the acceptance gate above. For today's runtime-security demonstration, use the separately validated [OpenShell walkthrough](red-teaming.md).
