# Distributed CPU training with Ray

Run from an authenticated terminal at the repository root:

```bash
python3 scripts/science.py ray-submit
oc get rayjobs,rayclusters,pods -n ai-showroom
```

The launcher binds the generated RHOAI OAuth service account to the namespace's MLflow data role. The operator replaces the requested pod service account, so applying the RayJob alone is insufficient for MLflow writes. The RoleBinding belongs to the RayJob and is removed with it.

Two actors train four SKU models each on two different worker pods. The head advertises zero training CPUs. The head requests 4 GiB and allows 6 GiB because Ray dashboard processes exceeded a 3 GiB limit during validation. Each worker requests 1 CPU and 2 GiB.

Acceptance requires `status.jobStatus=SUCCEEDED`, two different worker names in the result, eight model records, and the MLflow/S3 artifact. A Kubernetes submitter pod showing Completed is **not** proof that the Ray application succeeded.

To deliberately rerun the demo after inspecting the previous result:

```bash
oc delete rayjob aurora-demand-train -n ai-showroom
python3 scripts/science.py ray-submit
```

Completed jobs shut down their cluster after the configured grace period. GitOps manages the reusable service components; the presenter triggers training runs explicitly. See the [official Ray memory guidance](https://docs.ray.io/en/latest/ray-core/scheduling/ray-oom-prevention.html).
