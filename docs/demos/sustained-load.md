# Sustained GuideLLM load and retained evidence

The opt-in load generator uses **GuideLLM v0.7.4** to send actual streaming inference requests through a dedicated MaaS subscription. Its prompts are synthetic; the resulting traffic, token counts, errors, and timing are measured. The generator requests no GPU and never restarts the model.

For the September 22–23 rehearsal, the absolute stop is **September 23, 2026, 11:59 a.m. America/New_York / 15:59 UTC**. The protected customer window is **September 22, 8:00–11:00 a.m. New York / 12:00–15:00 UTC**. The runner enforces the absolute deadline even after a restart; Kubernetes also imposes a bounded active deadline.

## Operating limits

| Control | Configuration |
|---|---|
| Normal steps | 0.1 → 0.25 → 0.5 requested requests/second, repeating |
| Pilot cap | 0.1 requests/second until a successful pilot is reviewed |
| Normal concurrency | At most two in-flight requests |
| Customer window | 0.05 requests/second, at most one in flight |
| Payload | 256 synthetic input tokens, at most 128 generated tokens |
| Timeouts | 10-second connect and 30-second read timeout; bounded subprocess duration |
| Failure bound | Five errors end a segment; three failed segments stop the Job |
| MaaS quota | `showroom-load`, 1,500,000 tokens/hour, separate from interactive subscriptions |
| Credential | `ai-showroom/showroom-guidellm-key`; expiration must be after the absolute stop |
| CPU container | 250m CPU / 512Mi requested, 1 CPU / 2Gi limit |
| Results | Retained 5Gi `showroom-guidellm-results` PVC; unique segment directories |

Requested rate is not achieved throughput. Startup, warmup, quota, backend latency, errors, and the concurrency cap can reduce achieved rate. Review the report before presenting a rate or token-throughput claim. The sequence includes startup and short gaps between measured segments; it is not a seamless constant-rate soak test.

## Reproduce the run

The component is deliberately excluded from normal Argo overlays: a Git sync must not start a long load test automatically. Inspect [the opt-in resources](https://github.com/weslleyrosalem/rhoai-showroom/tree/main/gitops/components/platform/load), edit the dates and model reference for the new environment, and verify its StorageClass (`gp3-csi` in the demonstrated cluster).

1. Apply the owned load subscription, ServiceAccount, PVC, and NetworkPolicy after confirming the cluster and identity. This changes only the explicitly named showroom resources.
2. Provision a dedicated key with a lifetime covering the run; no key belongs in Git or a command argument.
3. Stage the exact deployed model's tokenizer files in a private local directory. Copy only `tokenizer.json`, `tokenizer_config.json`, `special_tokens_map.json`, and `config.json`, subject to that model's license. No model weights are needed.
4. Inspect the launch plan, then apply it. A waiting CPU pod can be resumed by repeating the guarded helper; it preserves the PVC, history, and existing Job.

From the repository root, set `SHOWROOM_SERVER` and `SHOWROOM_USER` from the independently approved environment record. Compare the following read-only identity output with those expected values; do not populate the guard variables from the current context:

```bash
oc whoami --show-server
oc whoami
oc apply --server-side --field-manager=rhoai-showroom-load \
  -f gitops/components/platform/load/resources.yaml

python3 gitops/components/platform/credentials/provision_maas.py \
  --expected-server "$SHOWROOM_SERVER" --expected-user "$SHOWROOM_USER" \
  --subscription showroom-load --secret-name showroom-guidellm-key --expires-in 2d \
  --model-id publishers/maas-how-to/models/redhataillama-31-8b-instruct \
  --key-file /private/path/maas-load.json --apply

python3 scripts/guidellm_load.py \
  --expected-server "$SHOWROOM_SERVER" --expected-user "$SHOWROOM_USER" \
  --tokenizer-dir /private/path/llama-tokenizer
```

Add `--apply` to the last command to start the reviewed plan. The helper verifies checksums before the tokenizer-ready marker releases traffic. It uses the authenticated `/v1/models` endpoint for connectivity validation because MaaS does not expose a generic `/health` route. The sustained run uses the working standard MaaS endpoint without an explicit model-selection header. Isolated header-based requests reached Llama’s endpoint picker, but repeated GuideLLM streaming qualification produced empty responses under both HTTP/2 and HTTP/1.1; those failed reports are retained. Consequently this load is evidence of MaaS/vLLM traffic, not successful sustained EPP processing. The separate private Qwen rehearsal demonstrates that request path. The client explicitly uses HTTP/1.1 after a prior HTTP/2 connection-protocol error. TLS validation stays enabled, redirects stay disabled, the API key is supplied through the child environment, and raw key material is redacted from retained output.

After reviewing a successful pilot and confirming the interactive endpoint remains responsive, rerun the same helper with `--apply --max-rate 0.5`. The runner checks the control file between segments; the customer protection window still takes precedence. Use `--max-rate 0.1` to reduce the next segment. The launcher refuses foreign resources, expired deadlines, insufficient key lifetime, and replacement of finished Jobs.

## Observe and export

```bash
oc get job,pvc -n ai-showroom -l app.kubernetes.io/component=guidellm-load
oc get pods -n ai-showroom -l app=showroom-guidellm -o wide
oc logs -n ai-showroom job/showroom-guidellm-20260922 --tail=10
```

The wrapper prints sanitized start/finish records and actual report summaries. Each completed segment retains `benchmarks.json`, `benchmarks.csv`, `benchmarks.html`, and a redacted `console.log`. `/results/history.jsonl` appends across restarts. Export the results directory to a private local location using `oc cp`; if the local WebSocket transport fails, set `KUBECTL_REMOTE_COMMAND_WEBSOCKETS=false` for that copy. Inspect an exported HTML report locally. There is no public unauthenticated results server.

Use the [existing native dashboards](../operations/native-dashboards.md) for the live walkthrough. GuideLLM's retained HTML/JSON files are measurement artifacts for inspection, not a replacement presentation dashboard.

| Native dashboard | Visible selection | Panels tied to the running load |
|---|---|---|
| **Usage** | Subscription `showroom-load`; User **All**; Model `redhataillama-31-8b-instruct`; View by **By subscription** | **Total requests**, **Total rate limited**, **Total tokens**, **Token consumption table**, **Token consumption chart** |
| **LLM Traffic** | Project `maas-how-to`; Model `redhataillama-31-8b-instruct` | **Throughput (req/s)** and **Token throughput (tokens/s)** |
| **LLM Utilization** | Same project and model | **GPU utilization**, **Requests running**, **Requests waiting** |
| **LLM Performance** | Same project and model | **Time to first token (TTFT)**, **E2E request latency**, **KV cache hit rate**, **KV cache usage** |

Recheck visible filters after every tab change: model selections can reset, and URL variables may be stale or unrelated to the current dashboard. Use a shared UTC window, and distinguish the continuous Llama load from intermittent Qwen traffic in `ai-showroom`. Keep `showroom-load` as the native subscription filter; the `X-Showroom-Client: guidellm-sustained` header is client identification, not an installed dashboard filter. Client TTFT across the gateway can include buffering; it is not interchangeable with engine TTFT.

The September 22 qualification completed a 0.25-rps block with 150 successful requests and a 0.5-rps block with 300 successful requests, both with zero reported errors. Each retained one incomplete request at the segment duration boundary. The 0.5-rps block generated 38,400 output tokens with a 2.877-second mean request latency. These are completed segment observations, not guarantees for the remainder of the run.

In the installed native MaaS Usage dashboard, the summary/table uses token-counter increase over the selected dashboard range. The time-series chart uses a fixed rolling two-hour increase. Its final plotted value can therefore differ from the summary when the selected range is not two hours. Neither value is the unprocessed lifetime counter; inspect the query and align windows before comparing them.

Scrapes sample traffic rather than recording every client result. A first nonzero counter sample cannot recover events before that sample, and a short request can finish between running/waiting gauge scrapes. **Usage → Success rate** describes policy counters and can fall back to 100% without denominator data; **LLM Traffic → Error rate** can fall back to zero without an error series. Keep the completed GuideLLM reports, including failures and incomplete requests, as the evidence for exact segment outcomes. Zero on one native chart does not erase a failed client request from the run history.

The installed **LLM Performance → Inter-token latency** query uses a metric name that the current runtime does not emit. Its fallback zero is **unavailable data**, not measured zero latency; use the validated TTFT and E2E panels for this walkthrough. See the [native dashboard limits](../operations/native-dashboards.md#read-the-known-panel-limits-correctly).

## Stop and retain

The absolute deadline ends load without a running laptop or an active chat. To stop early, delete only `job/showroom-guidellm-20260922` in `ai-showroom`; leave the PVC for evidence. Do not delete the original model, shared subscriptions, or an operator. Revoke the dedicated key through the MaaS API/UI after collecting evidence if early termination is required. Keep the PVC until reports have been exported and checked.

Do not add ROSA or OCM polling to the load runner, dashboards, or a monitor. In this environment, the user explicitly prohibits frequent control-plane API requests. Inspect Kubernetes nodes and workloads with `oc` only; cloud operations remain a separate, bounded activity.

Primary sources: [GuideLLM v0.7.4 release](https://github.com/vllm-project/guidellm/releases/tag/v0.7.4), [pinned CLI and profile documentation](https://github.com/vllm-project/guidellm/blob/v0.7.4/README.md), [output and sampling options](https://github.com/vllm-project/guidellm/blob/v0.7.4/docs/guides/outputs.md), and [local tokenizer setup](https://github.com/vllm-project/guidellm/blob/v0.7.4/docs/examples/custom-jsonl-dataset.md).


## Readiness snapshot — September 22, 06:40 UTC

The existing Job was active with no load-container restarts. Its latest completed 10-minute block recorded **60 successful requests, zero errors, and zero incomplete requests** at 0.1 requests/s, with 7,680 output tokens and 2.787-second mean latency. The next block was running at 0.25 requests/s and concurrency two. This is a dated observation, not a promise about future blocks.

The retained history contained 1,394 successful requests, 17 errors, and six incomplete requests, including earlier failed qualification attempts. Keep those failures visible when summarizing the full run. The latest clean block does not make the entire history error-free. The 5Gi results claim remained Bound and mounted, with 19 segment directories and 13 JSON reports available at that check. The protected presentation window and absolute stop time above were verified against the live runner configuration.
