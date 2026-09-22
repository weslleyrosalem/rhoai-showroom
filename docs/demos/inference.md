# Inference, routing, and cache: 30-minute demonstration

**Audience:** platform engineers and technical decision makers. **Story:** Aurora Supply answers inventory questions through a governed model endpoint while the platform measures serving behavior.

The working MaaS endpoint uses the existing Llama 3.1 8B on one L40S. Qwen3-4B-Instruct-2507 also served successfully on a new L40S through a dedicated private Gateway, with real endpoint-picker request counters. The September 22 rehearsal verified two Ready Qwen backends on distinct L40S hosts, anonymous rejection, and two authorized responses with usage and picker-counter increases. Verify current readiness immediately before presenting. Tensor parallelism and larger topologies require separate Ready capacity and successful inference; Pending pods are a capacity discussion, not a completed demo.

## Presenter sequence

| Time | Show | Explain and verify |
|---|---|---|
| 0–4 min | OpenShift AI → Models → deployed Llama; workload details | One model endpoint, one existing L40S, actual vLLM runtime image. Inspect replica and GPU requests. |
| 4–8 min | Aurora Supply application and playground | Ask for a replenishment review. The response is a recommendation, and the application uses a MaaS credential. |
| 8–13 min | Model metrics and the sustained GuideLLM workload | Real benchmark traffic produces prompt/output tokens, requests, latency, and GPU activity. GuideLLM has its own quota and a visible automatic stop. Synthetic prompts generate real inference; they are not a representative customer workload. |
| 13–20 min | Controlled repeated-prefix rehearsal | Explain local prefix reuse, run one first-use/repeated pair, then compare cache-counter deltas and client timing. Keep identical prompts and output limits within each pair. |
| 20–25 min | Private Qwen Gateway, LLMInferenceService, InferencePool, and endpoint picker metrics | Send an authenticated request through the dedicated Qwen listener and show the picker counter increase. Show queue, cache utilization, prefix, and LRU scorers. Compare backend placement only if both replicas are Ready on distinct nodes. |
| 25–30 min | Measured engine comparison and hardware profiles | Show the same-L40S Transformers reference versus vLLM results in the benchmark lab. Explain serialized versus continuous batching, then distinguish measured TP1 results from the unmeasured TP4 and eight-GPU plans. |

## Live checks

```bash
oc get llminferenceservice -n maas-how-to
oc get pods -n maas-how-to -o wide
oc get inferencepool -n maas-how-to
oc get httproute -n maas-how-to
oc get nodes -L node.kubernetes.io/instance-type,nvidia.com/gpu.product
oc logs -n ai-showroom job/showroom-guidellm-20260922 --tail=8
```

For the repeated-prefix experiment, run from the repository root with explicit identity guards and a new output path:

```bash
python3 scripts/cache_rehearsal.py \
  --expected-server "$SHOWROOM_SERVER" \
  --expected-user "$SHOWROOM_USER" \
  --pairs 1 --max-tokens 32 \
  --output /tmp/aurora-cache-rehearsal-new.json
```

Set `SHOWROOM_SERVER` and `SHOWROOM_USER` from the independently approved environment record, then compare them with `oc whoami --show-server` and `oc whoami`. Do not derive the expected values from the current context; that would defeat the guard. Use a unique output filename; the helper refuses to overwrite earlier evidence. It reads the existing owned Secret in memory, uses verified TLS, performs no restart or cache flush, and measures first-use versus repeated prompts. The prefix includes a fresh nonce; first-use is not a claim that every engine cache is cold.

## Recorded rehearsal and interpretation

The September 22 rehearsal completed six successful requests. The final repeated prompt generated **1,840 local prefix-cache hit tokens from 1,853 query tokens** in its isolated counter window. Five earlier windows overlapped science traffic and must not be used as an isolated comparison. The runtime reported prefix caching enabled. External prefix-cache counter deltas were zero.

Client-observed SSE first-token arrival nearly matched total response arrival, suggesting buffering along the gateway path. Show those values as **client-observed timing**, not engine TTFT. Use vLLM histograms for engine behavior. Do not calculate a headline speedup from six shared-instance requests.

The native LLM Traffic dashboard discovers projects from actual `kserve_vllm:num_requests_running` series. In this installation, collectors expose the model project as `exported_namespace`, while the collecting namespace is `redhat-ods-monitoring`. Both Qwen backends and the private Gateway were successfully scraped after scoped monitoring ingress was applied. Refresh the project selector after new target discovery; do not invent namespace labels to populate a graph.

Useful Prometheus metrics include `vllm:prefix_cache_hits_total`, `vllm:prefix_cache_queries_total`, `vllm:kv_cache_usage_perc`, `vllm:num_requests_running`, `vllm:num_requests_waiting`, request latency, and token counters. GPU utilization comes from the installed NVIDIA/DCGM integration; verify the metric and labels available in this cluster.

## Claims to keep precise

- **Local prefix cache:** demonstrated by the measured token-counter delta.
- **llm-d request processing:** demonstrated on the private Qwen listener with two successful authenticated responses and a matching picker-counter increase. The counter also counted the rejected anonymous request, so it is not itself a successful-inference count. A shared MaaS request without an explicit model header bypassed EPP during testing. Adding `X-Gateway-Model-Name` with the exact same publisher model ID as the JSON body returned a complete 200 response and increased the Llama picker counter. However, repeated GuideLLM streaming with that header later failed with empty response payloads under both HTTP/2 and HTTP/1.1. The sustained runner and cache rehearsal therefore use the working standard MaaS path without the header. Do not attribute their traffic to successful EPP processing.
- **KV disaggregation or transfer:** not demonstrated by a local prefix hit. Show only after a configured connector and transfer counters prove it.
- **vLLM versus Transformers:** a separate controlled single-repetition comparison used the same L40S, Qwen revision, BF16, image, resources, prompts, and output cap with prefix caching disabled. vLLM output throughput was 2.58× the serialized batch-one reference at concurrency 1 and 4.53× at concurrency 2. All 48 measured requests succeeded. Show the [raw results and limitations](../labs/benchmark.md#measured-rehearsal-september-22-2026); this is not a claim about every optimized Transformers stack or an llm-d routing benefit.
- **Multiple replicas versus llm-d:** reserve equal GPU capacity and use the same workload. Compare achieved throughput, errors, latency distributions, and cache behavior, including warmup and routing evidence.

If additional GPUs remain unavailable, complete the working single-GPU sequence and show the capacity guard blocking the larger topology. Do not poll ROSA or OCM during the demo; monitor node and workload readiness with `oc` only.

Continue with the [MaaS demonstration](maas.md) and [sustained load guide](sustained-load.md). The [benchmark lab](../labs/benchmark.md) describes controlled comparisons.

## Repeatable native inference check

Run the bounded helper from the repository root. It verifies the independently supplied cluster and identity, allocates private loopback ports, checks anonymous rejection, and sends two authorized Aurora policy requests. It saves usage, latency, readiness, and endpoint-picker deltas without tokens or response text:

```bash
python3 scripts/inference_probe.py \
  --expected-server "$SHOWROOM_SERVER" \
  --expected-user "$SHOWROOM_USER" \
  --require-backends 2 --measure-placement \
  --output /tmp/aurora-native-inference-new.json
```

Use `--require-backends 1` for the single-node rehearsal. A two-node result requires two Ready backends on distinct nodes. The optional placement measurement sends eight additional requests with concurrency two, then records per-backend request and cache counter deltas. During the September 22 rehearsal, all eight succeeded; the picker counted eight and the two backends handled two and six requests. Local prefix hits increased by 16 and 1,136 tokens. These observations establish actual serving on both hosts; they do not compare routing algorithms, prove a speedup, or demonstrate cross-node KV transfer.

## Private Qwen access

Use an operator-authorized port-forward; the Gateway has no public endpoint and its NetworkPolicy admits only the specifically selected native Playground OGX pods on TCP8080; other inference clients remain denied. Exact RHOAI collectors can separately scrape Gateway TCP15020. The raw Qwen TCP8000 backend accepts only its Gateway, endpoint picker, and those collectors, preventing direct application access around the Gateway authorization check. The OGX hop is same-namespace HTTP, while browser ingress and operator port-forward use TLS separately. The native KServe AuthPolicy still requires a valid Kubernetes identity with model access. Do not use the MaaS API key for this separate native-auth path.

```bash
oc port-forward -n ai-showroom service/showroom-inference-maas-gateway-class \
  28080:8080 --address 127.0.0.1
```

The inference path is `http://127.0.0.1:28080/ai-showroom/aurora-qwen-4b/v1/chat/completions`; the served model is `aurora-qwen-4b`. Supply the current `oc` token in memory through the benchmark helper's environment, never in a displayed command or saved report. See the [benchmark lab](../labs/benchmark.md). The private model is intentionally absent from MaaS discovery. Its native deployment and registry candidate remain visible in OpenShift AI.

## Shared MaaS route and picker

The demonstrated client-side routing requirement is `X-Gateway-Model-Name: <the exact model ID in the JSON body>`. With the Llama publisher ID, the unmodified `/v1/chat/completions` endpoint returned a complete response with usage and increased `llm_d_epp_request_total`; a streaming check returned 32 content chunks and usage. The otherwise identical request without that header succeeded but did not increment EPP. The header selects the route; MaaS still validates the key, model access, subscription, and quota.

Do not use the tested publisher-prefixed path as an interchangeable substitute: it returned 403 under the installed MaaS policy. The namespace-prefixed Llama path returned an empty 200 response. The one-off header result did not qualify the path for sustained traffic: later repeated GuideLLM streaming returned mostly empty responses. The sustained demonstration uses the working standard endpoint without that header; the separate private Qwen listener provides the llm-d request-path demonstration. These are observed integration behaviors, not universal behavior for every RHOAI installation.

## Extend the test drive

The [AHEAD llm-d workshop](../labs/ahead-llmd.md) walks through the existing two-backend deployment, an explicit round-robin observation, and the authenticated prefix-scoring path. The short rehearsal completed 48/48 requests and recorded routing and cache counters. Use its exact limitations when interpreting latency; the measurement does not isolate a causal routing speedup.
