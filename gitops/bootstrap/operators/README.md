# Operator bootstrap plan for a fresh ROSA cluster

This is a **read-only planning scaffold**, not a verified unattended installer. It narrows the gap between a bare ROSA cluster and the showroom's existing-platform prerequisites. Fresh-cluster installation has not been rehearsed.

`operators.lock.json` records 12 exact installed CSV versions observed on OpenShift 4.22.14 with OpenShift AI 3.5.1. It includes the official Red Hat or Certified Operators catalog, channel, target namespace, and OperatorGroup scope. MCP Gateway uses its preview channel. Versions of transitive dependencies are resolved by OLM and require separate review; a `startingCSV` is not an immutable pin for an entire dependency graph.

The planner never changes a cluster. It discovers existing Subscriptions and operator CSVs, preserves existing packages even when their versions differ, and verifies that absent packages' pinned CSVs are still offered by the specified catalog channel. It refuses silent version substitution, incompatible OperatorGroups, or a fresh installation on a different OpenShift minor release without updating the reviewed lock.

```bash
python3 scripts/platform_bootstrap.py \
  --expected-server https://api.YOUR-CLUSTER:443 \
  --expected-user YOUR-ADMIN \
  --verify-pins \
  --output local/operator-plan.json
```

The output contains a per-package action and `create_only_resources`. On the existing showroom all 12 packages are preserved and no create resources are emitted. On a new compatible cluster, the generated resources contain only missing Namespaces, OperatorGroups, and Subscriptions. Each Subscription uses **Manual** InstallPlan approval. The output file is created once; choose a new filename to retain a previous plan.

## Installation gates

1. Check ROSA/OpenShift compatibility, subscriptions, catalog connectivity, cloud IAM, region/AZ instance availability, storage classes, and GPU quotas. Run the separate physical capacity guard before GPU expansion.
2. Inspect the plan and any `BLOCKED` packages. Check existing operators and installation scopes; preserving an existing package is not a claim that its version is healthy or compatible.
3. Review the generated resources, including cluster-wide operator permissions. An administrator can extract `create_only_resources` into a separate file and create the missing resources. **Do not apply the entire plan JSON as Kubernetes desired state.** This scaffold intentionally has no `--apply` mode.
4. Review each resulting OLM InstallPlan, its complete CSV/dependency set, source, and target namespace before manual approval. Approve dependencies in their required order. Do not enable automatic upgrades for a repeatable showroom.
5. Verify all CSVs have reached `Succeeded`. The NFD/GPU operators also need their supported operands and configuration; an installed operator alone does not expose GPUs. Preserve any existing NVIDIA ClusterPolicy and workloads.
6. Create/configure the OpenShift AI DataScienceCluster and initialization resources using the supported installation procedure, then enable the required features and wait for their APIs. The showroom bootstrap helper configures a prepared platform; this operator plan does not create cloud pools, a complete DSC, Gateway/TLS infrastructure, or production storage.
7. Run the showroom preflight, bootstrap credentials outside Git, review the correct Argo overlay, and perform the documented acceptance tests. Runtime readiness must come from live evidence.

## Official Helm alternative

Red Hat publishes a versioned chart at `oci://registry.redhat.io/rhai/rhai-on-openshift-chart`; the 3.5 release is documented as `v3.5`. Use the [official Helm and GitOps installation guide](https://developers.redhat.com/articles/2026/08/26/automating-red-hat-openshift-ai-installations-with-helm-and-gitops) and review rendered output before choosing that route.

During this work, the OCI chart fetch returned HTTP 401 because no Helm registry login was configured. The public `rhoai-3.5` source was inspected at commit `679eaa9941cee7516f3b80f56236714219015538`, but its Chart.yaml still declared version 3.4.0. That source inspection does not verify the released OCI artifact. No chart was installed, no registry credentials were extracted, and no digest is claimed for an artifact that could not be retrieved. Authenticate with an authorized registry account, inspect the actual versioned artifact and its digest, render it, and avoid a blanket install over existing operators.

## Sources

- [OpenShift 4.22 OLM operator installation and manual approval](https://docs.redhat.com/en/documentation/openshift_container_platform/4.22/html/operators/user-tasks)
- [OpenShift AI 3.5 installation](https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html/installing_and_uninstalling_openshift_ai_self-managed/index)
- [Official chart source inspected at a fixed commit](https://github.com/red-hat-data-services/odh-gitops/tree/679eaa9941cee7516f3b80f56236714219015538/charts/rhai-on-openshift-chart)
- [NVIDIA GPU Operator installation on OpenShift](https://docs.nvidia.com/datacenter/cloud-native/openshift/latest/index.html)
