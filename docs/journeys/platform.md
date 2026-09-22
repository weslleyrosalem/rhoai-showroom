# Platform journey — operating Aurora Supply

Aurora Supply wants its assistant to use policies, inventory, and forecasts without making every team operate infrastructure. The visitor acts as a platform engineer: curate models, offer a governed API, and measure the results.

The reference installation uses OpenShift AI **3.5.1**. The curated catalog and MaaS controls have passed real tests: three Qwen models are available; missing credentials return 401; authorized requests return 200; the short quota produces 429 and recovers after its window. GPU benchmarks, MIG, and large models have separate acceptance gates. Check the [validation record](../operations/validation.md) before presenting them.

## Three visit formats

| Duration | Story | Visitor interaction |
|---|---|---|
| 20 minutes | Choose → consume → limit → observe | Filter the catalog, ask a question, and exhaust a test quota |
| 45 minutes | Add efficiency and scaling | Repeat prefixes, compare measured results, and interpret TTFT/throughput |
| Workshop | Reproduce the environment | Change Git configuration, synchronize, run an experiment, and inspect evidence |

## The 20-minute visit

1. **0–3 minutes: show the connected experience.** Open `ai-showroom`. The same Aurora workflow connects RAG policies, MCP inventory, demand forecasts, and an assistant. Explain the project boundary and shared platform services.
2. **3–6 minutes: curate.** Open the Qwen source in Model Catalog. Let the visitor select an included model, read its license, and inspect the hardware profile. A catalog entry does not guarantee available GPUs.
3. **6–10 minutes: take a test drive.** Ask an inventory question in Playground. Show the model, subscription, and metrics. The existing-cluster experience reuses the Llama in `maas-how-to`; the optional new GPU experience uses `aurora-qwen-4b` after runtime acceptance.
4. **10–14 minutes: govern consumption.** Use keys issued explicitly for `showroom-test-drive` and `showroom-standard`. Show 401 without a key, 200 when authorized, 429 after the short quota, the standard subscription still working, and recovery after the window. Keep keys off-screen.
5. **14–18 minutes: operate.** Relate the request to token, latency, and GPU metrics. Distinguish the current request from a previously recorded experiment. Application traces and infrastructure metrics answer different questions.
6. **18–20 minutes: use GitOps.** Show a small diff and the reconciled resource. Explain the catalog's concurrency-protected merge and environment-owned credentials.

## Extend to 45 minutes

- **5 minutes:** select another catalog model and inspect an already warmed deployment.
- **8 minutes:** open measured Transformers/vLLM results with the same GPU, model, precision, and load. Inspect errors, TTFT, and tokens/second.
- **7 minutes:** repeat prefixes across two replicas and confirm actual Endpoint Picker activity. Compare round-robin and llm-d using the same eight GPUs.
- **3 minutes:** distinguish TP4 on one node, two TP4 replicas on separate nodes, and one model partitioned across nodes. The last case requires its own experiment.
- **2 minutes:** explain capacity, autoscaling, and MIG. L40S does not support MIG; H100 and A100 use separate hardware plans.

## Product maturity and laboratory scope

MaaS core, quotas, and keys provide the supported foundation. vLLM through MaaS and WVA are Technology Preview. Hierarchical KV cache offloading is Developer Preview. Show maturity when introducing a feature; a Kubernetes API version does not establish its support status. [Technology Preview](https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html/release_notes/technology-preview-features_relnotes), [Developer Preview](https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html/release_notes/developer-preview-features_relnotes).

## Preparation and acceptance

Complete the [hardware](../labs/hardware.md), [catalog](../labs/model-catalog.md), [MaaS](../labs/maas.md), and [benchmark](../labs/benchmark.md) labs. Have dated results, ready models, and a loaded corpus. Provisioning workers and downloading model weights belong before the customer visit.

The journey passes when requests succeed, negative access tests fail as intended, quotas are observed, existing services remain healthy, and the global **16 physical GPU** ceiling is respected. A module blocked by capacity or dependencies stays outside the live demonstration and remains labeled blocked.
