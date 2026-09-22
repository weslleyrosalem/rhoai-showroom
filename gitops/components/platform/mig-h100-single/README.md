# Dedicated H100 MIG, single strategy

This opt-in hardware profile is disabled. It does not patch ClusterPolicy, create a machinepool, configure device geometry, or change the existing Llama.

The proposed pool `showroom-h100-mig` uses `p5.4xlarge`: one H100 with 80GB HBM3. Require a fresh `mig-h100-single` capacity PASS before creating capacity. The current active-l40s-11 plan plus one H100 and its surge totals 13 physical GPUs. This does not establish cloud availability or authorize a new pool; require the cloud owner's bounded verification before changing capacity.

Use a new, empty H100 node with a dedicated `showroom.openshift.ai/mig=true:NoSchedule` taint and `showroom.openshift.ai/mig-pool=true` label. Confirm `mig.capable=true`. GPU Operator already uses `single`, so a homogeneous `all-1g.10gb` configuration does not require changing the global strategy. Inspect the node's generated MIG configuration, then apply geometry only to that node through an authorized maintenance step.

Require `mig.config.state=success`, `mig.strategy=single`, and seven allocatable `nvidia.com/gpu` devices before enabling this hardware profile. In this strategy a GPU resource represents a slice on that selected node. The selectors prevent confusing it with a whole L40S.

The optional `models/qwen-06b-mig-h100` component requests two slices. To demonstrate isolation, record distinct assigned MIG UUIDs, CUDA-visible memory, successful inference, and unchanged Llama health. The physical guard counts the H100 as one card even when GFD reports seven devices. See the [hardware lab](../../../../docs/labs/hardware.md) for sources and acceptance.
