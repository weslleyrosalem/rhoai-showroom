# Profiles and cloud capacity plans

Kustomizations deploy application/platform objects, not AWS/ROSA machinepools. `capacity.json` is a preflight plan consumed by `scripts/capacity.py`.

| Profile | Purpose |
|---|---|
| `core` | Profiles, groups, and MaaS definitions. Its default Qwen reference needs a deployed backend. |
| `existing-cluster` | Core with references to `maas-how-to/redhataillama-31-8b-instruct`; preserves that model and `subplus`. |
| `interactive` | Platform plus Qwen4B; needs one free, labeled L40S. |
| `active-l40s-9` | Reference cluster's existing Llama plus Qwen4B and a single Qwen32B/TP4 replica. |
| `full-l40s-13` | Alternative Qwen4B plus two Qwen32B/TP4 replicas; nominally one preserved GPU plus three four-L40S nodes. |
| `mig-9` / `mig-13` | Alternative A100 cloud plans and a disabled hardware profile. No automatic repartitioning. |
| `mig-h100-single` | Planned one-H100 option, preserving the current single MIG strategy. Includes a disabled profile, not the optional model workload or node labels. |

Install the foundation first; these profiles do not create `ai-showroom`. Benchmark components create `ai-showroom-bench`, protected against automatic Argo pruning. Gateway, MaaS, GPU Operator, storage, registry credentials, and RHOAI operators are prerequisites.

The fixed ceiling is **16 physical GPUs**, including existing, pending, and desired machines plus upgrade surge. Full13 plus one four-GPU upgrade node reaches 17 and must be blocked. Alternative profiles never imply that existing pools have disappeared.

## Reference cluster plan

`active-l40s-9` keeps showroom subscriptions on the existing Llama and gives new Qwen models their own subscriptions. `aiml-node` has 1–3 one-GPU nodes and surge 1. `showroom-l40s4` has 1–2 four-GPU nodes during warmup and surge 1. The combined bound is 16. The name 9 describes one preserved plus eight new GPUs, not the maximum autoscaled total.

The proposed H100 option needs verified L40S surge 0/maxUnavailable 1 before adding one H100 with surge 1; its bound is 14. Existing surge 1 instead produces 18 and is blocked. Only an observed cloud policy change can reduce the inventory's bound.

Do not automatically synchronize GPU workloads. Run the guard against fresh ROSA/OCM inventory, review capacity, and apply deliberately. Full and A100 MIG are alternative plans, not additive expansions. Free Qwen4B before allocating both new L40S nodes to Qwen32B replicas. Read the [hardware](../../docs/labs/hardware.md) and [benchmark](../../docs/labs/benchmark.md) labs before changing capacity.
