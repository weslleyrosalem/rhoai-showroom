# Model components

These components are opt-in workloads, not proof of performance. `models.lock.json` records model revisions, licenses and the runtime digest observed in OpenShift AI3.5.1. No live GPU startup validation was performed while authoring them.

| Directory | Topology | Namespace | New GPU reservation |
|---|---|---|---:|
|qwen-4b|One vLLM instance, TP1|ai-showroom|1|
|qwen-32b-tp4|One complete model, TP4|ai-showroom-bench|4|
|qwen-32b-multinode|Two complete model replicas, TP4 each, separate hosts|ai-showroom-bench|8|
|qwen-72b-opt-in|Two Qwen72B replicas, TP4 each, separate hosts|ai-showroom-bench|8|

The two32B directories own the same service name and are **alternatives**, never two Applications managing it.72B is an alternative workload after removing/scaling down the32B benchmark, not an addition to all existing GPU work. It uses the Qwen-specific license, not Apache2. The full profile enables4B+32B replicas only.

Before apply:

```bash
python3 gitops/components/models/preflight.py --model qwen-4b \
  --profile interactive --inventory /private/rosa-inventory.json \
  --expected-server "$EXPECTED_OPENSHIFT_SERVER"
oc apply --dry-run=server -k gitops/components/models/qwen-4b
```

The preflight checks the fixed16-card global cloud ceiling, ready labeled L40S placement and allocated GPU requests. It returns `PASS_CAPACITY_ONLY`, never Ready. It does not provision nodes, validate network transport, guarantee CPU/RAM, or test an image pull.

Model URI revisions use `hf://owner/model:revision`, as parsed by KServe storage. Verify the installed storage initializer before first download; older documentation may show another URI notation. No remote Python code is enabled. Qwen4B explicitly enables Hermes tool parsing, which must pass a tool-call smoke test before connecting an agent. Runtime and scheduler presets still need the installed3.5.1 controllers.

Every model uses `maas-default-gateway` in `openshift-ingress`. The installation must configure it, TLS, identity, MaaS and route namespace permissions. Do not make the gateway accept every namespace to fix a Pending route. On a different installation, patch the gateway reference to the approved gateway.

Acceptance: exact SHA loaded; image pulled; service and MaaSModelRef Ready;200 for authorized calls;401/403 for unauthorized access; successful bounded inference; correct GPU/node placement; EPP traffic for cache-aware claims. Store results privately and publish only sanitized measurements.

PP2×TP4, prefill/decode and hierarchical KV offloading are distinct future experiments. They are not silently represented by the two-replica deployment. P/D needs validated RDMA; hierarchical offloading is Developer Preview.
