# Optional same-GPU engine rehearsal

This component is excluded from Argo overlays. It uses a single existing L40S worker for a temporary Transformers reference / vLLM comparison. The helper temporarily scales the owned two-replica Qwen deployment to one, retains the other Ready replica, and restores two afterward. Run it in a maintenance window, never during a customer session or another benchmark.

The manifest pins the Qwen revision, storage initializer, and vLLM image. It has no public Service or Route, no service-account token or RBAC, non-root restricted containers, a one-hour Pod deadline, and ingress denied. HTTPS egress is needed by the initializer to download the public pinned weights. Both engines bind only to loopback. An authenticated `oc port-forward` is the measurement path.

Set `SHOWROOM_SERVER` and `SHOWROOM_USER` independently from the approved environment record. From the repository root:

```bash
python3 scripts/engine_benchmark.py \
  --expected-server "$SHOWROOM_SERVER" --expected-user "$SHOWROOM_USER" \
  --output-dir /private/path/unique-engine-rehearsal
```

PLAN performs read-only Kubernetes inspection. Review it, then add `--apply` only for the maintenance window. Python requires PyYAML, and the caller needs permission to inspect nodes and manage the named workload resources. The helper refuses a model managed by Argo, a different pin, pre-existing benchmark resources, or fewer than two Ready replicas on separate approved single-GPU workers. Coordinate a maintenance overlay if GitOps manages the deployment.

The benchmark Pod is pinned to the existing released hostname, so it cannot use a newly provisioned worker. No ROSA, OCM, or AWS API is called, and no pool/autoscaler settings are changed. The observed physical GPU ceiling is 16; this reuse operation adds zero physical capacity and does not replace the separate pool-plus-surge capacity guard.

Each engine receives 12 measured requests at concurrency 1, then 12 at concurrency 2; each run has two warmups, a 64-token output cap, a 60-second request timeout, and a five-minute measurement bound. Transformers is a serialized batch-one reference. vLLM uses continuous batching, with prefix caching disabled. The same Pod, L40S, model, image, BF16, tokenizer/template, 4-CPU limit, and 32Gi memory limit are retained. Run order is fixed; repeat with a separately reviewed reversed-order experiment before drawing broader performance conclusions.

Results and logs are written to an exclusive directory outside the repository with mode 0700. The helper never overwrites earlier evidence. Review `cleanup.json` immediately: the helper requests deletion only for resources it created and restores two Ready Qwen replicas. SIGTERM requests controlled cleanup, and uncertain API responses are reconciled against the original model UID. A local process killed forcibly without cleanup can leave Qwen at one replica; the Pod deadline ends the temporary workload but does not restore the model. Recovery is to inspect the exact owned resources, delete that benchmark Pod, and restore `ai-showroom/aurora-qwen-4b` to two replicas after checking current intent.

The September 22 measurements were executed with the private predecessor of this orchestration. This generalized helper has passed its identity/capacity PLAN and guard tests; its APPLY path has not been rerun, to avoid disrupting the scheduled presentation. See the benchmark lab for raw measured results and their limits.
