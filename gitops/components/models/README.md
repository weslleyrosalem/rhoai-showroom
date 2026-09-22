# Model components

These components are opt-in workloads, not proof of performance. `models.lock.json` records model revisions, licenses and the runtime digest observed in OpenShift AI 3.5.1. The private Qwen4B overlay has completed actual startup, authorized inference, and endpoint-picker checks. Larger models and MIG remain unvalidated; see each component and the dated demo guide.

| Directory | Topology | Namespace | New GPU reservation |
|---|---|---|---:|
|qwen-4b|Portable shared-Gateway base, one vLLM instance, TP1|ai-showroom|1|
|qwen-4b-private|Private Gateway, two TP1 replicas on distinct hosts|ai-showroom|2|
|qwen-32b-tp4|One complete model, TP4|ai-showroom-bench|4|
|qwen-32b-multinode|Two complete model replicas, TP4 each, separate hosts|ai-showroom-bench|8|
|qwen-72b-opt-in|Two Qwen72B replicas, TP4 each, separate hosts|ai-showroom-bench|8|
|qwen-06b-mig-h100|Two Qwen0.6B replicas on distinct H100 MIG slices|ai-showroom-bench|2 logical slices, one physical H100|

The two 32B directories own the same service name and are **alternatives**, never two Applications managing it. 72B is an alternative workload after removing/scaling down the 32B benchmark, not an addition to all existing GPU work. It uses the Qwen-specific license, not Apache2. The full profile enables 4B + 32B replicas only.

Before apply:

```bash
python3 gitops/components/models/preflight.py --model qwen-4b \
  --profile interactive --inventory /private/rosa-inventory.json \
  --expected-server "$EXPECTED_OPENSHIFT_SERVER"
oc apply --dry-run=server -k gitops/components/models/qwen-4b
```

The preflight checks the fixed 16-card global cloud ceiling, ready labeled L40S placement and allocated GPU requests. It returns `PASS_CAPACITY_ONLY`, never Ready. It does not provision nodes, validate network transport, guarantee CPU/RAM, or test an image pull.

Model URI revisions use `hf://owner/model:revision`, as parsed by KServe storage. Verify the installed storage initializer before first download; older documentation may show another URI notation. No remote Python code is enabled. Qwen4B explicitly enables Hermes tool parsing, which must pass a tool-call smoke test before connecting an agent. Runtime and scheduler presets still need the installed 3.5.1 controllers.

The public base models use `maas-default-gateway` in `openshift-ingress`. The `qwen-4b-private` overlay uses a dedicated ClusterIP Gateway, native Kubernetes authorization, and operator-authorized port-forwarding; it deliberately removes MaaS discovery and subscription resources. The installation must configure it, TLS, identity, MaaS and route namespace permissions. Do not make the gateway accept every namespace to fix a Pending route. On a different installation, patch the gateway reference to the approved gateway.

Acceptance: exact SHA loaded; image pulled; service Ready; 200 for authorized calls; 401/403 for unauthorized access; successful bounded inference; correct GPU/node placement; EPP traffic for routing claims. Public MaaS deployments also require a Ready MaaSModelRef and usable advertised endpoint. Private Qwen uses the native identity path instead. Store results privately and publish only sanitized measurements.

PP2×TP4, prefill/decode and hierarchical KV offloading are distinct future experiments. They are not silently represented by the two-replica deployment. P/D needs validated RDMA; hierarchical offloading is Developer Preview.

The H100 MIG component is a separate opt-in after the dedicated node has successful `all-1g.10gb` geometry under single strategy. Its two replicas may share one physical host, unlike the TP4 scale-out experiment. Use the `mig-h100-single` capacity plan and the same-named hardware guide; no global GPU Operator change is included.

## Native registry

Use the [native registry onboarding component](registry/README.md) to register the pinned Qwen candidate before deployment and evaluation. Registration does not approve a candidate or allocate GPUs.
