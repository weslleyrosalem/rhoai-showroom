# Native GPU dashboard integration

`showroom-gpu-utilization` is a showroom-owned PodMonitor in `ai-showroom-monitoring`. It collects **only** `DCGM_FI_DEV_GPU_UTIL` for the two exact demonstration model/namespace patterns: Aurora Qwen in `ai-showroom` and the existing Llama in `maas-how-to`. A model renamed or moved outside those patterns is deliberately excluded until the source is reviewed.

The native LLM Utilization dashboard expects `accelerator_gpu_utilization` with `model_name` and `exported_namespace`. The installed shared collector renamed the NVIDIA metric differently and rejected it because its temporary `__tmp_scale_needed` label is invalid at export. This component supplies the expected real metric through a separate, bounded scrape; it does not edit the shared collector, NVIDIA exporter, existing monitors, or recording rules. DCGM values remain percentages, without fabricated scaling or load.

The collector adds its own resource `k8s_pod_name`, so the native chart legend identifies the GPU exporter Pod. `workload_pod` preserves the actual model backend Pod returned by NVIDIA's Kubernetes allocation mapping. The demonstrated workers have one physical GPU each. The chart is GPU activity attributed through that allocation; it is not per-request GPU accounting or proof of fair-share isolation.

After applying with the correct cluster identity, allow collector target discovery and a scrape interval, refresh the native LLM Utilization project/model selectors, and verify:

```promql
avg by (k8s_pod_name) (
  accelerator_gpu_utilization{
    exported_namespace="ai-showroom",model_name="aurora-qwen-4b"
  }
)
```

Both Qwen hosts and the original Llama produced real series in the September 22 rehearsal. Zero between requests is valid idle data. View request activity alongside GPU utilization; no additional load is started by this component. The sustained GuideLLM traffic belongs to the Llama/MaaS demonstration.

The target is the existing private DCGM exporter HTTP metrics port 9400. It receives no credential. This standard metrics transport is not claimed to be end-to-end TLS. No inference listener or NetworkPolicy is opened by this component.

Before applying manually, compare `oc whoami --show-server` and `oc whoami` with independently approved `SHOWROOM_SERVER` and `SHOWROOM_USER` values. Render/review the component and use a server dry-run first. The only rollback is deleting PodMonitor `ai-showroom-monitoring/showroom-gpu-utilization`. Do not delete a NVIDIA operator resource or change shared collector configuration.

The optional OVMS resource-limit compatibility rule lives separately in `gitops/bootstrap/monitoring-compatibility.yaml` because it must evaluate where the cluster's kube-state-metrics series exist. Use `scripts/configure_monitoring_compatibility.py` with independent identity guards and an exclusive private backup. It creates only `openshift-monitoring/showroom-ovms-resource-limit-compatibility`; existing rules remain unchanged. Its expression is restricted to the Aurora allocation model in `ai-showroom-monitoring`, summing actual container CPU/memory limits into the legacy metric name expected by the native dashboard.

```bash
python3 scripts/configure_monitoring_compatibility.py \
  --expected-server "$SHOWROOM_SERVER" --expected-user "$SHOWROOM_USER"
```

Review PLAN, then repeat with `--apply --backup /private/path/new-ovms-metrics-backup.json`. It uses server dry-run, exclusive mode-0600 backups, resourceVersion/UID tests for owned updates, and refuses a foreign rule. Cluster monitoring administration is required for the initial create; GitOps should receive only the permissions needed for this exact owned rule after bootstrap. To roll back, delete only that named rule.

The model controller owns `aurora-allocation-metrics-dashboard` and overwrites its data on reconciliation. We preserve that controller boundary. Its installed latency queries use microseconds while the title says milliseconds, and the end-to-end query omits namespace. Interpret those native latency values as microseconds for this exact named model; this compatibility rule does not rename or rescale them. Use correctly scoped, explicit-unit queries for exported analysis.

Source verified: [ODH model-controller 3.5 metrics reconciler](https://github.com/opendatahub-io/odh-model-controller/blob/75d7963733041438f6e85f1c024e817558306d31/internal/controller/serving/reconcilers/kserve_metrics_dashboard_reconciler.go) and [runtime metric templates](https://github.com/opendatahub-io/odh-model-controller/blob/75d7963733041438f6e85f1c024e817558306d31/internal/controller/constants/runtime-metrics.go). Reassess the compatibility resources after a platform upgrade.
