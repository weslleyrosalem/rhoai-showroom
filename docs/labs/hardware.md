# Lab — capacity, topology, and MIG

The showroom has a fixed ceiling of **16 physical GPUs total**, including existing pools, pending machines, and upgrade overlap. Kubernetes quotas, MIG devices, and time-slicing replicas count logical resources; they do not replace infrastructure accounting.

## Active plan: active-l40s-9

The ROSA plan preserves `aiml-node` and adds `showroom-l40s4`. The preset name describes one preserved GPU plus up to eight new GPUs; the full ceiling also includes autoscaling on the existing pool.

| Pool | Instance type | Minimum / maximum nodes | GPUs/node | Surge nodes | Physical maximum including surge |
|---|---|---|---|---|---|
| aiml-node | g6e.4xlarge | 1 / 3 | 1 | 1 | 4 |
| showroom-l40s4 | g6e.12xlarge | 1 / 2 | 4 | 1 | 12 |
| workers | m8i.2xlarge | 1 / 4 | 0 | No GPU impact | 0 |

**3 + 8 + 1 + 4 = 16 physical GPUs**, with at most 11 outside upgrade overlap. Recalculate before increasing a maximum or adding a GPU pool. The new pool requires IMDSv2, `showroom.openshift.ai/gpu-pool=true`, `nvidia.com/gpu.product=NVIDIA-L40S`, and the taint `nvidia.com/gpu=true:NoSchedule`.

The minimum was raised from 0 to 1 for initial warmup because the autoscaler recognized the pool but did not initiate scale-from-zero. Returning to 0 is an explicit cloud operation after verifying that behavior; this guide does not assume it happened.

The first stage runs Qwen4B/TP1 and one Qwen32B/TP4 replica while preserving Llama. Before comparing two Qwen32B replicas on two four-GPU nodes, stop Qwen4B. GPU workloads remain outside default automatic Argo synchronization until the capacity guard passes.

## Alternative plans

| Profile | Nominal infrastructure including one existing GPU | Constraint |
|---|---|---|
| Core | One existing L40S | CPU workloads and shared inference |
| Interactive | Existing GPU + one L40S = 2 | A separate plan; do not automatically add it to the active pools |
| Full L40S13 | Existing GPU + three four-L40S nodes = 13 | Does not fit the active pool maxima and surge policies |
| MIG9 | Existing GPU + eight A100 GPUs = 9 | Alternative after removing/reducing incompatible pools |
| MIG13 | Existing GPU + eight A100 + four L40S = 13 | Also requires an upgrade-overlap review |
| MIG H100 single | Active pools plus one H100 | Planned option below; requires a verified change to the new L40S pool's surge policy |

These plans are not additive. Full13 plus one four-GPU surge node reaches 17. An eight-GPU A100 node with one surge node plus the existing L40S also exceeds 16. Do not invent a zero-surge value to make a plan pass.

AWS documents four L40S GPUs in `g6e.12xlarge`, eight A100 GPUs in `p4d.24xlarge`, and one H100 with 80GB HBM3 in `p5.4xlarge`. Region, ROSA offerings, account quotas, capacity, and pricing require independent verification. P5.4xlarge does not support GPUDirect RDMA. [G6e](https://aws.amazon.com/ec2/instance-types/g6e/), [P4](https://aws.amazon.com/ec2/instance-types/p4/), [P5](https://aws.amazon.com/ec2/instance-types/p5/).

## Physical capacity preflight

`scripts/capacity.py` is read-only. Without a complete, fresh cloud inventory it returns **BLOCKED**: `oc get nodes` cannot see every pending machine, autoscaling maximum, or HCP upgrade surge.

Private inventory format — illustrative values, not evidence:

```json
{
  "schema_version": 1,
  "complete": true,
  "cluster_server": "https://api.YOURCLUSTER:6443",
  "observed_at": "ACTUAL_QUERY_TIME_IN_UTC",
  "count_semantics": "exact",
  "pools": [
    {
      "id": "ACTUAL_POOL_ID",
      "instance_type": "g6e.4xlarge",
      "current_nodes": 1,
      "desired_nodes": 1,
      "max_nodes": 1,
      "upgrade_surge_nodes": 0,
      "node_names": ["ACTUAL_NODE_NAME"]
    }
  ]
}
```

Include CPU pools with `gpus_per_node: 0`. Unknown GPU types require a verified mapping, not a CPU declaration. Unmapped AWS g*/p* GPU families are rejected even before their device plugin publishes GPU labels. Set `complete: true` only after inspecting every cloud API page or OCM pool. If current/desired counts are unavailable, use `count_semantics: "upper-bound"` and conservatively set them to verified pool maxima. Record the source and actual observation time; never refresh a timestamp without observing state. Zero surge requires a verified maintenance policy.

```bash
python3 scripts/capacity.py --profile active-l40s-9 \
  --expected-server "$EXPECTED_OPENSHIFT_SERVER" \
  --inventory /private/directory/rosa-inventory.json \
  --output /private/directory/capacity-result.json
```

`cluster_server` must match `--expected-server`. Inventory older than 15 minutes is blocked. PASS confirms only accounting; it does not prove quota, price, availability, or runtime readiness. The script never changes machinepools. ROSA controls node autoscaling; HPA/WVA/Ray govern workload scaling. [ROSA HCP autoscaling](https://docs.redhat.com/en/documentation/red_hat_openshift_service_on_aws/4/epub/cluster_administration/rosa-enable-cluster-autoscale-cli-interactive_after_rosa-cluster-autoscaling).

## Hardware profiles and placement

`showroom-cpu-small` offers CPU/RAM; `showroom-l40s-1` requests one L40S; `showroom-l40s-4` requests four devices for tensor parallelism. L40S profiles require both the product label and `showroom.openshift.ai/gpu-pool=true`, avoiding the preserved GPU node.

Host RAM and VRAM are separate. Creating a hardware profile does not create a node. For scale-from-zero, selectors must also exist on the machinepool template; labels produced only after GPU Feature Discovery starts may prevent the autoscaler from identifying that pool. Confirm Ready nodes, allocatable devices, tolerations, storage, and registry access before presenting deployment options.

`qwen-32b-multinode` runs two complete TP4 model replicas with mandatory placement on different hosts. It does not split one model across nodes. A PP2×TP4 experiment requires separate LeaderWorkerSet, preset, and transport validation.

## Dedicated H100 MIG option

The `mig-h100-single` plan proposes `showroom-h100-mig`, one `p5.4xlarge` node, maximum 1 and surge 1. It requires the **owned** L40S pool to have an observed surge 0/maxUnavailable 1 maintenance policy. The preserved pool remains unchanged. The resulting bound is **3 + 8 + 1 + 1 + 1 = 14**. With the current L40S surge 1, the guard calculates 18 and blocks this addition. A plan file cannot override the live inventory's higher surge value.

The inspected GPU Operator 26.7.0 already has MIG Manager enabled and strategy `single`. Keep that strategy for the first H100 experiment. On a dedicated, empty H100 node, the `all-1g.10gb` configuration creates seven equal slices. Single strategy advertises them as `nvidia.com/gpu`; the hardware profile must identify each request as a slice. Mixed strategy uses resource names such as `nvidia.com/mig-1g.10gb` and needs a separate operator configuration review. [NVIDIA MIG profiles](https://docs.nvidia.com/datacenter/tesla/mig-user-guide/supported-mig-profiles.html), [OpenShift MIG strategies](https://docs.nvidia.com/datacenter/cloud-native/openshift/26.3/mig-ocp.html).

Use only the new H100 node. Require `nvidia.com/mig.capable=true`, `showroom.openshift.ai/mig-pool=true`, and a dedicated `showroom.openshift.ai/mig=true:NoSchedule` taint. The existing Llama must not tolerate that dedicated taint. Confirm no user GPU workloads occupy the node before setting its MIG geometry. MIG Manager can stop GPU components and may require a reboot; do not repartition an occupied node. GPU Operator versions 26.3+ generate supported geometry configurations from detected hardware. [GPU Operator MIG](https://docs.nvidia.com/datacenter/cloud-native/gpu-operator/26.3/gpu-operator-mig.html).

`gitops/components/platform/mig-h100-single` contains a disabled hardware profile. `gitops/components/models/qwen-06b-mig-h100` contains two optional Qwen0.6B replicas, each requesting one slice. Neither changes ClusterPolicy or labels nodes. Before enabling the profile or applying the model, require `mig.config.state=success`, strategy `single`, seven allocatable logical devices, and a fresh physical capacity PASS. Selectors enforce the dedicated H100 pool and geometry.

Acceptance requires two ready workloads with distinct MIG device UUIDs on the same physical H100, successful CUDA execution and inference, observed memory per slice, and continued Llama health. Seven slices count as **one physical GPU** in the guard. A successful apply or a disabled profile is not an executed MIG demonstration.

## A100 alternative

L40S cannot use MIG. The older A100 40GB option in `platform/mig-opt-in` partitions only GPU 0 into seven `1g.5gb` slices, leaving seven GPUs whole. It requires mixed strategy; that geometry does not fit A100 80GB or H100. Its ConfigMap is excluded from Kustomize and its hardware profile is disabled until actual allocation is verified. [Supported GPUs](https://docs.nvidia.com/datacenter/tesla/mig-user-guide/supported-gpus.html).

GFD labels can count MIG instances rather than cards. For verified EC2 types the guard uses physical instance specifications. Time-slicing is temporal sharing and does not provide MIG's memory partitioning.

## Acceptance

Record cloud inventory, before/after counts, topology, and scheduling evidence. New L40S workloads must avoid the preserved node. A two-replica TP4 experiment must show distinct hosts after freeing Qwen4B. Mark MIG demonstrated only after workloads use actual partitions. Never substitute successful YAML application for those results.
