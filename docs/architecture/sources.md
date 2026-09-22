# Sources and versions

Primary-source research and cluster validation started on **September 22, 2026 UTC**. The target is OpenShift AI **3.5.1**, OpenShift **4.22.14**, RHCL **1.4.3**, MCP Gateway Operator **0.7.1**, and GitOps **1.21.4**. Revalidate the combination in each new cluster.

## Platform and release

- [RHOAI 3.5 new features and enhancements](https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html/release_notes/new-features-and-enhancements_relnotes)
- [Technology Preview](https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html/release_notes/technology-preview-features_relnotes)
- [Developer Preview, including OpenShell](https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html/release_notes/developer-preview-features_relnotes)
- [Known issues](https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html/release_notes/known-issues_relnotes)
- [Installing RHOAI with Helm and GitOps](https://developers.redhat.com/articles/2026/08/26/automating-red-hat-openshift-ai-installations-with-helm-and-gitops)
- [OpenShift GitOps 1.21 Argo CD applications](https://docs.redhat.com/en/documentation/red_hat_openshift_gitops/1.21/html-single/argo_cd_applications/index)

## Security, MCP, and data science

- [MCP Gateway prerequisites](https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html/working_with_the_mcp_catalog/assembly-mcp-gateway-operator-prerequisites_mcp-gateway-operator)
- [MCP Lifecycle](https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html/working_with_the_mcp_catalog/enabling-mcp-lifecycle-management)
- [NeMo and MCP guardrails](https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html/enabling_ai_safety_with_guardrails/enabling-ai-safety-with-nemo-guardrails_nemo-guardrails)
- [Installing MLflow](https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html/working_with_mlflow/installing-mlflow_mlflow)
- [EvalHub](https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html/evaluating_ai_systems/evaluating-llms-with-evalhub_evaluate)
- [Playground](https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html/experimenting_with_models_in_the_gen_ai_playground/playground-overview_rhoai-user)
- [NVIDIA OpenShell Kubernetes deployment](https://docs.nvidia.com/openshell/kubernetes/setup)
- [OpenShift OAuth proxy](https://github.com/openshift/oauth-proxy/blob/master/README.md)

## Hardware and models

- [AWS G6e/L40S](https://aws.amazon.com/ec2/instance-types/g6e/)
- [NVIDIA MIG supported GPUs](https://docs.nvidia.com/datacenter/tesla/mig-user-guide/supported-gpus.html)
- [vLLM automatic prefix caching](https://docs.vllm.ai/en/latest/features/automatic_prefix_caching/)
- [Qwen3-4B-Instruct-2507](https://huggingface.co/Qwen/Qwen3-4B-Instruct-2507)
- [Qwen3-32B](https://huggingface.co/Qwen/Qwen3-32B)

Model revisions and runtime digests are pinned in `gitops/components/models/models.lock.json`. Containerfiles pin base images, and `requirements-docs.txt` pins documentation dependencies. Individual labs include additional primary references.

## OpenShell maturity clarification

The [OpenShift AI 3.5 Developer Preview release notes](https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html/release_notes/developer-preview-features_relnotes) explicitly list “Secure agent sandboxing and policy enforcement using OpenShell.” This is a product Developer Preview using upstream artifacts. NVIDIA separately labels its [Kubernetes Helm chart](https://docs.nvidia.com/openshell/kubernetes/setup) experimental. This showroom has tested a private runtime with an explicit subject-authorization proxy and scoped SCC; that evidence does not change its product maturity or imply a complete NeMoClaw integration.

## Guide design and typography

The guide uses local Red Hat Display and Red Hat Text font files from the [official Red Hat Font repository](https://github.com/RedHatOfficial/RedHatFont), with its OFL license retained under `docs/assets/fonts`. Color and hierarchy decisions reference the [Red Hat design system color guidance](https://ux.redhat.com/foundations/color/usage/) and [typography guidance](https://ux.redhat.com/foundations/typography/type-specifics/). The showroom mark is original; this community site does not claim to be an official Red Hat documentation site.
