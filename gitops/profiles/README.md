# Profiles and cloud capacity plans

Kustomizations deploy application/platform objects, not AWS/ROSA machinepools. `capacity.json` is a preflight plan consumed by `scripts/capacity.py`.

| Profile | Purpose |
|---|---|
| `core` | Profiles, groups, and MaaS definitions. Its default Qwen reference needs a deployed backend. |
| `existing-cluster` | Core with references to `maas-how-to/redhataillama-31-8b-instruct`; preserves that model and `subplus`. |
| `interactive` | Platform plus Qwen4B; needs one free, labeled L40S. |
| `active-l40s-11` | Current existing Llama plus Qwen4B on a new single-GPU pool; physical maximum 11 including surge. |
| `active-l40s-9` | Historical four-GPU-node alternative, superseded for the reference cluster. |
| `full-l40s-13` | Alternative Qwen4B plus two Qwen32B/TP4 replicas; nominally one preserved GPU plus three four-L40S nodes. |
| `mig-9` / `mig-13` | Alternative A100 cloud plans and a disabled hardware profile. No automatic repartitioning. |
| `mig-h100-single` | Planned one-H100 option, preserving the current single MIG strategy. Includes a disabled profile, not the optional model workload or node labels. |

Install the foundation first; these profiles do not create `ai-showroom`. Benchmark components create `ai-showroom-bench`, protected against automatic Argo pruning. Gateway, MaaS, GPU Operator, storage, registry credentials, and RHOAI operators are prerequisites.

The fixed ceiling is **16 physical GPUs**, including existing, pending, and desired machines plus upgrade surge. Full13 plus one four-GPU upgrade node reaches 17 and must be blocked. Alternative profiles never imply that existing pools have disappeared.

## Reference cluster plan

`active-l40s-11` keeps showroom subscriptions on the existing Llama and exposes Qwen4B only through the private native-auth benchmark Gateway, without a MaaS subscription. `aiml-node` has 1–3 one-GPU nodes and surge 1. `showroom-l40s1` has 1–2 one-GPU nodes and surge 1. Optional `showroom-l40s4` has 0–1 four-GPU nodes and surge 0. The combined maximum including surge is 11. The optional pending Qwen32B workload was removed; its manifests remain for a future verified run.

The proposed H100 option adds maximum 1 plus surge 1 to this plan, reaching 13. It remains unprovisioned and untested. Only observed cloud settings can establish the actual bound. No automated ROSA/OCM polling is allowed in the reference environment.

Do not automatically synchronize GPU workloads. Run the guard against fresh ROSA/OCM inventory, review capacity, and apply deliberately. Full and A100 MIG are alternative plans, not additive expansions. Free Qwen4B before allocating both new L40S nodes to Qwen32B replicas. Read the [hardware](../../docs/labs/hardware.md) and [benchmark](../../docs/labs/benchmark.md) labs before changing capacity.
