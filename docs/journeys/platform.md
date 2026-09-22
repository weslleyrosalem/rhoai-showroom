# Platform journey — operating Aurora Supply

Aurora Supply wants its assistant to use policies, inventory, and forecasts without making every team operate infrastructure. The visitor acts as a platform engineer: curate models, offer a governed API, and measure the results.

The reference installation uses OpenShift AI **3.5.1**. The curated catalog and MaaS controls have passed real tests: three Qwen models are discoverable in the curated catalog; missing credentials return 401; authorized requests return 200; the short quota produces 429 and recovers after its window. GPU benchmarks, MIG, and large models have separate acceptance gates. Check the [validation record](../operations/validation.md) before presenting them.

## Three visit formats

| Duration | Story | Visitor interaction |
|---|---|---|
| 20 minutes | Choose → consume → limit → observe | Filter the catalog, ask a question, and exhaust a test quota |
| 45 minutes | Add efficiency and scaling | Repeat prefixes, compare measured results, and interpret TTFT/throughput |
| Workshop | Reproduce the environment | Change Git configuration, synchronize, run an experiment, and inspect evidence |

## The 20-minute visit

1. **0–3 minutes: show the connected experience.** Open `ai-showroom`. The same Aurora workflow connects RAG policies, MCP inventory, demand forecasts, and an assistant. Explain the project boundary and shared platform services.
2. **3–6 minutes: curate.** Open the Qwen source in Model Catalog. Let the visitor select an included model, read its license, and inspect the hardware profile. A catalog entry does not guarantee available GPUs.
3. **6–10 minutes: take a test drive.** Ask an inventory and policy question with Aurora Qwen in native Playground; inspect the read-only tools and cited policy. This path uses the visitor’s authorized Kubernetes identity. Then open Aurora Supply to connect the shared Llama in `maas-how-to` with its MaaS subscription and metrics. The Ready `aurora-qwen-4b` deployment also supplies the private inference rehearsal and is not advertised as a public MaaS endpoint.
4. **10–14 minutes: govern consumption.** Use keys issued explicitly for `showroom-test-drive` and `showroom-standard`. Show 401 without a key, 200 when authorized, 429 after the short quota, the standard subscription still working, and recovery after the window. Keep keys off-screen.
5. **14–18 minutes: operate.** Relate the request to token, latency, and GPU metrics. Distinguish the current request from a previously recorded experiment. Application traces and infrastructure metrics answer different questions.
6. **18–20 minutes: use GitOps.** Show a small diff and the reconciled resource. Explain the catalog's concurrency-protected merge and environment-owned credentials.

## Extend to 45 minutes

- **5 minutes:** inspect Qwen4B's pinned catalog source, native registry candidate, and the Ready private deployment. These are different lifecycle states.
- **8 minutes:** open actual GuideLLM reports from the shared Llama endpoint. Explain successful/error counts, client timing, requested versus achieved rate, and the protected customer window. This is measured traffic, not a Transformers/vLLM comparison.
- **7 minutes:** send a request through the isolated Qwen Gateway and observe the real Endpoint Picker counter increase. Require two Ready backends on distinct hosts before demonstrating placement across replicas. The shared MaaS load uses its working standard path. A matching model header reached Llama EPP in isolated calls but failed repeated streaming qualification, so it is not the sustained demonstration path.
- **3 minutes:** repeat a controlled prefix and inspect local cache hits. Distinguish local prefix reuse from cross-node KV transfer; only the former has recorded evidence.
- **2 minutes:** review the current 11-GPU infrastructure maximum including surge and the user ceiling of 16. Explain autoscaling and the separate H100/A100 MIG plans; no MIG execution claim is made.

The [engine benchmark](../labs/benchmark.md#measured-rehearsal-september-22-2026) now contains a measured same-L40S Qwen4B comparison: vLLM versus a serialized Transformers reference, 12 successful requests per configuration, and explicit single-repetition limits. Show those results as a separate experiment; the sustained Llama traffic does not establish that comparison. An eight-GPU routing comparison remains unmeasured, and larger TP4 topologies remain source examples with explicit capacity gates. Use the [inference](../demos/inference.md) and [MaaS](../demos/maas.md) cue sheets for the currently demonstrated path.

## Connect each screen to a customer decision

| Screen | Aurora Supply decision | Visitor action and interpretation |
|---|---|---|
| Model Catalog | Which model should the assistant team investigate? | Open the curated Qwen source, select 4B, inspect license and revision; compare 32B's memory needs without claiming it is deployed. |
| Model Registry | Has this exact model passed the acceptance process? | Open `Aurora Supply - Qwen3-4B` and its pinned candidate version. Candidate status is intentional; serving success and a catalog listing are not safety approval. Failed or incomplete evaluations must remain visible. |
| Models / deployments | Which endpoint is actually serving this interaction? | Follow the existing Llama for Aurora application traffic, and private Qwen for the isolated inference experiment. Inspect readiness, replica count, and actual requests. |
| Hardware profiles | Where would this workload fit? | Match Qwen4B to one L40S per replica. Treat the four-GPU profile as a prepared option requiring Ready four-GPU capacity; do not launch it during the customer visit. |
| MaaS / API keys | How do platform and visitor consumption differ? | Select the subscription explicitly. Compare the visitor's short quota with the standard application budget and the separately identifiable GuideLLM load. Never display key material. |
| Playground | Can the assistant use current inventory and policy together? | Ask for a replenishment recommendation for `AS-001`; inspect the tool's exact SKU, forecast provenance, and required approval. No purchase is executed. |
| Observability | Is the platform processing real work? | Correlate the request window with successful requests, errors, token counts, GPU utilization, and endpoint-picker/cache counters. Do not equate pod readiness or a counter increase with model quality. |

## Product maturity and laboratory scope

MaaS core, quotas, and keys provide the supported foundation. vLLM through MaaS and WVA are Technology Preview. Hierarchical KV cache offloading is Developer Preview. Show maturity when introducing a feature; a Kubernetes API version does not establish its support status. [Technology Preview](https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html/release_notes/technology-preview-features_relnotes), [Developer Preview](https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html/release_notes/developer-preview-features_relnotes).

## Preparation and acceptance

Complete the [hardware](../labs/hardware.md), [catalog](../labs/model-catalog.md), [MaaS](../labs/maas.md), and [benchmark](../labs/benchmark.md) labs. Have dated results, ready models, and a loaded corpus. Provisioning workers and downloading model weights belong before the customer visit.

The journey passes when requests succeed, negative access tests fail as intended, quotas are observed, existing services remain healthy, and the global **16 physical GPU** ceiling is respected. A module blocked by capacity or dependencies stays outside the live demonstration and remains labeled blocked.
