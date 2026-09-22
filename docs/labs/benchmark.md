# Lab — inference engine and routing efficiency

This lab measures a synthetic Aurora Supply replenishment task. Scripts contain no fabricated performance results. Failures, missing usage, and incompatible configurations are explicit in the output.

## Ask separate questions

| Comparison | Keep constant | Allowed difference |
|---|---|---|
| Transformers versus vLLM | Qwen4B revision, tokenizer/template, BF16, one L40S, resources, prompts, output cap, load | Engine and its batching implementation |
| vLLM plus round-robin versus vLLM plus llm-d/EPP | Two TP4 replicas, the same eight GPUs and nodes, vLLM digest, cache configuration, model, load | Routing |
| TP1 versus TP4; four versus eight GPUs | An explicitly defined model and workload | Scale; report tokens/second and tokens/second/GPU separately |

The engine comparison does not prove an llm-d benefit. Two TP4 replicas represent horizontal scaling, not a single model split across nodes. PCIe/Ethernet overhead can offset scaling gains; measured results decide.

## Measured rehearsal: September 22, 2026

The following **single-repetition** results used the same physical L40S and the same temporary Pod for both engines. Qwen3-4B-Instruct-2507 weights, BF16 precision, image, tokenizer/template, 4-CPU limit, 32Gi memory limit, prompts, seed, warmup, and output cap were held constant. Prefix caching was disabled. Each row contains 12 measured requests plus two separate warmups, with a maximum of 64 output tokens per request. All rows completed 12/12 requests successfully and returned 766 total output tokens. The measurements used a localhost port-forward to the engine, excluding the MaaS and llm-d gateway path.

| Engine | Client concurrency | Output tokens/s | Latency p50 / p95 | Client TTFT p50 |
|---|---:|---:|---:|---:|
| Transformers, serialized batch-one reference | 1 | 26.01 | 2,453 / 2,478 ms | 184 ms |
| vLLM, continuous batching | 1 | 67.18 | 944 / 995 ms | 177 ms |
| Transformers, serialized batch-one reference | 2 | 27.47 | 4,629 / 4,725 ms | 2,358 ms |
| vLLM, continuous batching | 2 | 124.51 | 1,007 / 1,125 ms | 192 ms |

In this workload, vLLM delivered **2.58×** the reference output throughput at concurrency 1 and **4.53×** at concurrency 2. The second comparison deliberately illustrates the queueing cost of a serialized reference. It does not represent every Transformers optimization, prove an llm-d routing advantage, or establish a universal performance multiplier. The run order was Transformers first, then vLLM; repetitions and alternating order remain required before a performance recommendation or approval.

The [sanitized raw measurements](../results/engine-ab-20260922.json) include individual request timing, immutable image/model pins, workload/template hashes, errors, usage, and comparison output. No response text is included, so generation quality has not been evaluated by this benchmark. The native registry now attaches this immutable evidence as `MEASURED_REFERENCE_ONLY`; the lifecycle remains `candidate` and safety remains `NOT_RUN`. This one rehearsal has not granted performance approval or completed repeated-run acceptance criteria. The original Llama and its GuideLLM traffic remained active. One Qwen replica continued serving; the temporary benchmark resources were removed and the second Qwen replica was restored afterward.

For a scheduled maintenance window, the [optional engine rehearsal helper](https://github.com/weslleyrosalem/rhoai-showroom/tree/main/gitops/components/platform/engine-benchmark) provides a guarded PLAN and temporary reuse of one existing Qwen GPU, with automatic restoration and cleanup reporting. Its generalized APPLY path has not been rerun after the measured private predecessor; the source documents that validation boundary. It creates no cloud capacity. Keep the live demonstration on the restored two-replica endpoint.

## Required metadata

Create a private JSON file from the workload actually running:

```json
{
  "engine": "vllm",
  "model_revision": "cdbee75f17c01a7cc42f958dc650907174af0554",
  "tokenizer_revision": "cdbee75f17c01a7cc42f958dc650907174af0554",
  "dtype": "bfloat16",
  "gpu_product": "NVIDIA-L40S",
  "gpu_count": 1,
  "node_count": 1,
  "max_model_len": 8192,
  "chat_template_sha256": "ACTUAL_SHA256_OF_THE_EFFECTIVE_TEMPLATE",
  "cache_mode": "off",
  "tensor_parallel": 1,
  "pipeline_parallel": 1,
  "data_parallel": 1,
  "image_digest": "REGISTRY/IMAGE@sha256:ACTUAL_DIGEST",
  "scheduling": "one GPU; endpoint continuous batching"
}
```

The script requires immutable pins and consistent metadata, but cannot attest that the server matches user-supplied values. Verify the image, arguments, GPU placement, and template on the workload. Passing a metadata parser does not validate invented metadata.

Disable prefix caching on both sides for the engine comparison. For routing, use the same cache settings on the same vLLM backends. Keep these experiments separate.

## Measurement client

The client uses Python's standard library. HTTPS requires a valid certificate; HTTP is allowed only on localhost for port-forwarding. Read the API key from `SHOWROOM_API_KEY`, never a command-line argument or result file.

```bash
python3 scripts/benchmark.py run \
  --base-url "$BENCHMARK_BASE_URL" --model aurora-qwen-4b \
  --metadata /private/directory/vllm-metadata.json \
  --requests 30 --concurrency 4 --max-tokens 128 --warmup 5 \
  --prefix-mode repeated-prefix \
  --output /private/directory/vllm-run-1.json
```

The workload contains Aurora policies and the eight versioned products (`AS-001` through `AS-008`), with a frozen historical demand scenario and a 21-day coverage policy. `repeated-prefix` preserves the prefix; `distinct-prefix` changes an identifier at its beginning. Character lengths are controlled; actual token counts come from endpoint usage. Output includes timestamps, HTTP status, latency, TTFT, approximate TPOT, usage, and prompt hashes. It excludes responses and credentials.

TTFT measures the first nonempty SSE text/reasoning content received by the client, not internal engine latency. TPOT divides elapsed time after that content by output tokens minus one. Since SSE can combine tokens, this is an approximation.

Hard limits: 200 measured requests, 16 concurrent requests, 256 output tokens/request, 600 seconds for the measurement stage, 120 seconds/request, and 10 separate warmup requests. Responses are additionally limited to 4MiB total and 64KiB per SSE line; chunked reads enforce the request deadline even if a server never finishes a line. Calls already running may finish after the stage deadline. Start small to confirm the endpoint and subscription.

## Executable Transformers baseline

The optional `serve-transformers` command requires PyTorch, Transformers, FastAPI, and Uvicorn in a validated GPU image. The measurement client installs nothing. Run this baseline on the dedicated GPU in a separate stage:

```bash
python3 scripts/benchmark.py serve-transformers \
  --model-path /mnt/models \
  --revision cdbee75f17c01a7cc42f958dc650907174af0554 \
  --served-model aurora-qwen-4b --host 127.0.0.1 --port 8000
```

Weights in `/mnt/models` must match the recorded revision. The baseline uses BF16, `trust_remote_code=False`, deterministic generation, and **serialized batch size 1**. It is an explicit reference for single-request latency and concurrency effects, not a representation of every Transformers optimization. Document and validate any static-batching baseline separately.

The streamer emits decoded token increments to avoid TextIteratorStreamer's word buffering. Do not expose a public Route. A non-localhost bind requires `SHOWROOM_BENCHMARK_KEY`; preserve NetworkPolicy and secure transport.

## Compare and repeat

Repeat each configuration three times and alternate the order. Interpret percentiles with sample size in mind. Missing usage produces `null` throughput, not character-based token estimates. The comparator rejects differences in model, precision, template, GPU count, topology, cache, workload, or warmup.

```bash
python3 scripts/benchmark.py compare \
  /private/directory/transformers-run-1.json \
  /private/directory/vllm-run-1.json --kind engine \
  --output /private/directory/engine-comparison.json
```

For round-robin/EPP, use `--kind routing`; the vLLM image digest must also match. Use the same backend pool in separate stages and verify actual backend selection. Do not create two additional eight-GPU pools simultaneously. The script measures existing endpoints; it does not configure a load balancer or rewrite routes.

The current `active-l40s-11` plan demonstrates Qwen4B on single-GPU hosts and keeps the original Llama running. Qwen32B/TP4 was removed from the live cluster after capacity did not become Ready. An eight-GPU routing comparison requires a separately verified alternative pool plan and actual Ready TP4 replicas; it has not been measured.

## Cache and Endpoint Picker evidence

Use long shared input with new suffixes. Compare per-pod cache counters and TTFT against distinct-prefix controls. One GPU demonstrates local cache reuse. Two replicas with actual EPP traffic are required for a routing claim. Discover metric names from the installed runtime; an empty graph is not evidence of zero activity.

Check known issue INFERENG-6962: shared wildcard listeners can bypass Endpoint Picker. Confirm authorized routes and EPP traffic. Hierarchical KV offloading is Developer Preview; prefill/decode disaggregation requires validated network/RDMA support and is not enabled by this benchmark. [vLLM prefix caching](https://docs.vllm.ai/en/latest/features/automatic_prefix_caching/), [vLLM benchmark CLI](https://docs.vllm.ai/en/v0.23.0/cli/bench/serve/), [RHOAI known issues](https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html/release_notes/known-issues_relnotes).

## Acceptance

Require raw results, verified metadata, three repetitions, explained errors, and cache/EPP counters for related claims. Report absolute and per-GPU throughput, p50/p95/p99 latency, failures, and sampled output quality. Do not turn this small workload into a universal speedup claim. Local HTTP/SSE test fixtures validate client instrumentation only and must never be presented as model performance.
