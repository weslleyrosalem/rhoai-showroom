# Profiles and cloud capacity plans

Kustomizations deploy application/platform objects, not AWS/ROSA machinepools. `capacity.json` is a preflight plan consumed by `scripts/capacity.py`.

- `core`: profiles, groups and MaaS definitions. The default Qwen reference requires a deployed backend before use.
- `existing-cluster`: core with model references patched to the existing `maas-how-to/redhataillama-31-8b-instruct`. No mutations to that model or `subplus`.
- `interactive`: platform plus new Qwen4B, requires one free labeled L40S.
- `full-l40s-13`: Qwen4B plus two Qwen32B/TP4 replicas; cloud plan one preserved GPU plus3×4L40S.
- `mig-9` / `mig-13`: alternative cloud plans and a disabled MIG hardware profile; they do not repartition devices or install GPU Operator configuration automatically.

These directories do not create `ai-showroom`; install the common foundation first. `ai-showroom-bench` is created by the benchmark model component and is protected against automatic Argo prune. The gateway, MaaS stack, GPU Operator, CSI, cluster pull secret and RHOAI operators are prerequisites.

The fixed ceiling is16 physical GPUs, including existing/pending/desired pool machines and upgrade surge. Full13 with one extra4GPU upgrade node is17 and must be blocked. Profiles do not imply other pools have disappeared: cloud inventory retains them until their actual scale-down and maxima are verified.

Do not apply Full and MIG simultaneously. Read [hardware](../../docs/labs/hardware.md) and [benchmark](../../docs/labs/benchmark.md) before changing capacity.

## Plano implantado neste cluster

`active-l40s-9` mantém as subscriptions do showroom apontando para o Llama existente e adiciona Qwen4B/TP1 e uma réplica Qwen32B/TP4 com subscriptions próprias. Pool `aiml-node` 1–3 ×1GPU, surge1; `showroom-l40s4` 0–2 ×4GPU, surge1. Limite global incluindo surge:16. O nome9 corresponde a uma GPU preservada + oito novas, não ao máximo autoscalável total.

Não sincronize automaticamente os manifests GPU. Execute o guard com inventário ROSA/OCM atual, revise o custo/capacidade e só então aplique. `full-l40s-13` e MIG são alternativas, não expansões acumuláveis do plano ativo. Para duas réplicas Qwen32B no plano ativo, libere Qwen4B primeiro.
