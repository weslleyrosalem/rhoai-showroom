# Fontes e versões

Pesquisa e validação iniciadas em **22/09/2026 UTC**. Foram consultadas fontes primárias e os schemas reais do cluster. O alvo é OpenShift AI **3.5.1**, OpenShift **4.22.14**, RHCL **1.4.3**, MCP Gateway Operator **0.7.1** e GitOps **1.21.4**; um novo cluster precisa revalidar sua combinação.

## Plataforma e release

- [RHOAI3.5: novidades e melhorias](https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html/release_notes/new-features-and-enhancements_relnotes)
- [Technology Preview](https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html/release_notes/technology-preview-features_relnotes)
- [Developer Preview](https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html/release_notes/developer-preview-features_relnotes)
- [Problemas conhecidos](https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html/release_notes/known-issues_relnotes)
- [Helm e GitOps para instalar RHOAI](https://developers.redhat.com/articles/2026/08/26/automating-red-hat-openshift-ai-installations-with-helm-and-gitops)
- [OpenShift GitOps1.21: aplicações Argo CD](https://docs.redhat.com/en/documentation/red_hat_openshift_gitops/1.21/html-single/argo_cd_applications/index)

## Segurança, MCP e ciência

- [MCP Gateway prerequisites3.5](https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html/working_with_the_mcp_catalog/assembly-mcp-gateway-operator-prerequisites_mcp-gateway-operator)
- [MCP Lifecycle](https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html/working_with_the_mcp_catalog/enabling-mcp-lifecycle-management)
- [NeMo e MCP Guardrails](https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html/enabling_ai_safety_with_guardrails/enabling-ai-safety-with-nemo-guardrails_nemo-guardrails)
- [Instalar MLflow](https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html/working_with_mlflow/installing-mlflow_mlflow)
- [EvalHub](https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html/evaluating_ai_systems/evaluating-llms-with-evalhub_evaluate)
- [Playground](https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html/experimenting_with_models_in_the_gen_ai_playground/playground-overview_rhoai-user)
- [NVIDIA OpenShell Kubernetes](https://docs.nvidia.com/openshell/kubernetes/setup)

## Hardware e modelos

- [AWS G6e/L40S](https://aws.amazon.com/ec2/instance-types/g6e/)
- [NVIDIA MIG: GPUs compatíveis](https://docs.nvidia.com/datacenter/tesla/mig-user-guide/supported-gpus.html)
- [vLLM automatic prefix caching](https://docs.vllm.ai/en/latest/features/automatic_prefix_caching/)
- [Qwen3-4B-Instruct-2507](https://huggingface.co/Qwen/Qwen3-4B-Instruct-2507)
- [Qwen2.5-32B-Instruct](https://huggingface.co/Qwen/Qwen2.5-32B-Instruct)

Os modelos e runtimes usam revisions/digests no `gitops/components/models/models.lock.json`; cada Containerfile registra sua imagem base. As dependências de documentação estão fixadas em `requirements-docs.txt`. Os links de cada laboratório complementam esta bibliografia.
