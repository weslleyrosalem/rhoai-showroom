# Compare two live inference paths

Open the **Aurora live inference comparison** Route supplied by your presenter and sign in through OpenShift. The application runs inside the cluster and reuses the two existing Qwen vLLM replicas. It does not depend on the presenter's workstation or notebook controller.

1. Keep the supplied Aurora system prompt and user message for the first run. Review the output-token limit, initially 64.
2. Select **Run comparison**. Both paths receive identical messages and generation parameters: **vLLM + round-robin** explicitly alternates the baseline backend; **vLLM + llm-d** uses the private Gateway and endpoint picker.
3. Inspect each actual response, status, streaming TTFT, total time, and provider token usage. A missing streaming measurement remains unavailable. The paths execute sequentially; the page shows which ran first and alternates that order on subsequent comparisons.
4. Select **Repeat last pair** to reuse the exact previous inputs. This is a deliberate second observation, not an automatic load loop. **Stop** requests cancellation; an engine may finish work it already accepted.
5. Open the [native dashboards](../operations/native-dashboards.md), filter project `ai-showroom` and model `aurora-qwen-4b`, and choose a range containing the displayed timestamps. These charts include other callers and collection delay.

Reuse the system prompt to discuss prefix reuse. Both paths share the same caches, GPUs, live traffic, and model configuration. The second path can benefit from the first path's work. Their authentication and routing overhead differ. A smaller time in one sample is an observation, not a guarantee or an isolated scheduler speedup. No cross-node KV transfer is demonstrated.

The application knows which backend it chose for round-robin. It does not infer the llm-d-selected pod or a per-call cache-hit rate from aggregated counters. Historical measurements in the [llm-d workshop](ahead-llmd.md) remain separate evidence.

Installation, access boundaries, and cleanup are described in the [optional comparison profile](https://github.com/weslleyrosalem/rhoai-showroom/tree/main/gitops/components/experience/compare). Keep private Route hostnames and credentials out of public copies.


## Observed live check — September 22, 2026

The authenticated browser completed both paths at **14:32 UTC**, using the concise Aurora defaults and a 64-token ceiling. Both returned the same brief answer: stock 45, proposal 346, and human approval required. Each reported **332 input tokens and 26 output tokens**, with a normal stop.

| Path | Observed streaming TTFT | Total time |
|---|---:|---:|
| vLLM + explicit round-robin | 37.7 ms | 0.34 s |
| vLLM + llm-d | 62.2 ms | 0.36 s |

These values are rounded as displayed by the application. The baseline was faster in this sample; no configuration was changed to force a preferred performance result. Two earlier short in-Pod pairs also completed, alternating both execution order and the explicit baseline backend. Anonymous Route requests, including a forged identity header, redirected to login.

The first draft's verbose answer instruction reached the 64- and 128-token limits. The UI correctly marked those responses as token-limited. The default question and answer instruction were then shortened, retaining the context and conservative limits, and the actual browser returned complete brief responses. Arbitrary user prompts may still exceed the output budget; inspect the finish reason.
