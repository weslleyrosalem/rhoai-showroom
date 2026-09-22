# Present with the native dashboards

Open **Observe & monitor → Dashboard** in OpenShift AI **3.5.1**. Use the existing product charts for the live presentation. The installed administrator view has six tabs: **Cluster, Models, LLM Traffic, LLM Utilization, Usage, and LLM Performance**. These names and their queries were checked against this installation on September 22, 2026. [Red Hat observability documentation](https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html/managing_openshift_ai/managing-observability_managing-rhoai).

## Set the context before reading a chart

Start with **Last 6 hours** for the rehearsal history, then use **Last 30 minutes** for an interaction during the session. At 8:00 a.m., use **Last 12 hours** or a custom interval to retain the earliest overnight runs. The time picker defaults to the browser's local timezone; the presentation uses **America/New_York**, while saved benchmark artifacts use UTC. Recheck the visible filters after changing tabs. A bookmark does not restore every selector.

| Experience | Serving project and model | Usage subscription |
|---|---|---|
| Qwen, native Playground, and llm-d rehearsal | `ai-showroom` / `aurora-qwen-4b` | This private route does not use a MaaS subscription |
| Sustained GuideLLM load | `maas-how-to` / `redhataillama-31-8b-instruct` | `showroom-load` |
| Aurora application | `maas-how-to` / `redhataillama-31-8b-instruct` | `showroom-standard` |
| Short quota test drive | `maas-how-to` / `redhataillama-31-8b-instruct` | `showroom-test-drive` |

The load client runs in `ai-showroom`, but its **serving metrics belong to `maas-how-to`**. LLM charts aggregate the selected serving model's traffic; they do not isolate a MaaS subscription. Use **Usage** for that distinction. Clear unrelated selections rather than combining the two workloads accidentally.

## Choose the chart that answers the customer

| Native tab | Panels to show | Customer question |
|---|---|---|
| **Cluster** | System health; Cluster resource overview; Project resource usage | Are nodes Ready, and where are resources being consumed? |
| **Models** | Model deployments; Replica count; P90 E2E request latency; P90 Time to first token (TTFT); Token throughput (tokens/sec) | Which deployment is serving, and how is it behaving? |
| **LLM Traffic** | Error rate; Throughput (req/s); Token throughput (tokens/s) | How much inference work is the service processing? |
| **LLM Utilization** | GPU utilization; Requests running; Requests waiting | Are the replicas busy, idle, or building a queue? |
| **LLM Performance** | Time to first token (TTFT); E2E request latency; KV cache hit rate; KV cache usage | How quickly does generation begin, and what happens to cache reuse? |
| **Usage** | Total tokens; Total requests; Total rate limited; Success rate; Active users; Token consumption chart and table | Who consumed the service, under which subscription and limits? |

In **Models**, use **Project** and **Model deployment**. In the three LLM tabs, use **Project** and **Model**. In **Usage**, use **User**, **Subscription**, **Model**, and **View by**. The administrator's six-tab view is not evidence that a visitor has the same permissions; use the participant's scoped identity for their test drive.

## 8:00 a.m. — traffic, latency, cache, and replicas

1. Open **Models**, select the Qwen project and deployment, and show its row and **Replica count** history. A replica graph does not establish placement on distinct nodes; the deployment and recorded routing test supply that evidence.
2. Open **LLM Traffic** with the same project/model. Relate the throughput and token bursts to the recorded inference rehearsal. Then switch to the Llama project/model to show the continuing load history.
3. Open **LLM Performance**. Read the **P50, P95, and P99** legends, then compare **KV cache hit rate** with **KV cache usage**. A reuse ratio and occupied cache capacity measure different things. Idle periods can have no hit-rate sample because there were no cache queries.
4. Open **LLM Utilization** and compare the replica legends in **Requests running** and **Requests waiting**. Low queue depth is expected when the bounded workload leaves interactive headroom. GPU utilization alone is not an efficiency comparison.
5. Use the [measured benchmark](../labs/benchmark.md#measured-rehearsal-september-22-2026) for the matched Transformers/vLLM result and the [routing rehearsal](../demos/inference.md) for EPP evidence. The native cache chart demonstrates local prefix reuse; it does not prove distributed KV transfer or a causal routing speedup. [Red Hat llm-d monitoring guidance](https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html/deploy_models_using_distributed_inference_with_llm-d/monitoring-llmd-deployments).

Expand **Drill-down** when a technical audience wants the installed PromQL expressions. That section contains query text; it is not an additional live routing chart. GuideLLM reports remain the source for client-side errors and incomplete requests. Client TTFT through a buffered gateway is not interchangeable with engine TTFT.

## 10:00 a.m. — consumption and quota

1. Open **Usage**. Select **Subscription = showroom-load**, **Model = redhataillama-31-8b-instruct**, and **View by = By model**. The growing chart and single consumption-table row make the background workload identifiable.
2. Switch explicitly to **showroom-test-drive** for the [quota exercise](../demos/maas.md). Keep the actual HTTP 200 → 429 → 200 evidence beside the chart; do not substitute an unfiltered total from unrelated subscriptions.
3. Switch to **showroom-standard** to discuss the application's budget. Use the table's **User**, **Subscription**, **Model**, **Tokens**, **Requests**, and **Rate Limited** columns to explain attribution. **View by = By subscription** changes the chart grouping.

Read **Success rate** as the installed limiter's authorized decisions divided by authorized plus rate-limited decisions. The template can also display 100% when its denominator is absent. It does not certify model responses, transport success, or answer quality. Anonymous 401 and forbidden 403 tests need their own HTTP evidence.

The summary and table use the selected dashboard interval; the installed token chart uses a **rolling two-hour increase** at each point. Their values need not match for a six-hour selection. Counters are sampled and `increase()` can extrapolate: events before a series' first scrape may be absent from the displayed increase. Rounded `K`/`M` values are not an exact billing ledger. For multi-model subscriptions, request counts can repeat across model rows; do not sum those rows as unique requests.

## Read the known panel limits correctly

- **Cluster → System health, Deployed models, GPU utilization**, and the resource-overview charts are cluster-wide even when Project is selected. **System health** is the fraction of nodes reporting Ready, not an assessment of every operator or service. Its **Request success rate** does filter the namespace and classifies vLLM completion reasons; it does not measure MaaS authorization. Project CPU and memory breakdowns use cluster capacity as their denominator; the GPU breakdown uses the count of observed accelerator metric series, not provisioned GPU capacity. **Deployed models** counts metric label groups, not Kubernetes model objects or GPU cards. Its datasource does not include every deployed model. Use deployment inventory for those counts.
- The observed **Models → CPU quota utilization** cell was blank. Its query needs an exact CPU ResourceQuota series; missing data does not mean zero usage or unlimited capacity. **Request success rate (requests/sec)** is a throughput chart, despite its name.
- **LLM Performance → Inter-token latency** is not a usable measurement in this installation. Its query expects the absent `kserve_vllm:time_per_output_token_seconds_bucket`; the runtime emits newer latency families. The displayed zero is a fallback. Skip this panel in the live sequence; use the populated TTFT and E2E charts and retained client measurements with their own definitions.
- **LLM Traffic → Error rate** is errors per second from its configured inference error series. A zero line is not proof that every client request succeeded or that no authentication or quota denial occurred. The native latency queries can also fall back to zero when usable observations are absent; zero is not automatically a measured latency.
- **Predictive monitoring** stays in the native model's **Endpoint performance** and **Model bias** tabs. Its OVMS latency template currently labels microsecond values as milliseconds; use the [monitoring lab's interpretation](../labs/model-monitoring.md), including request-versus-row counts. MLflow has its own [Usage and Tool calls panels](../labs/mlflow.md); those are application traces, not the six observability tabs.

If a chart is empty, first check identity, project/model, time interval, and whether the workload emitted the metric. Show a dated saved result when necessary and identify it as historical. Do not create replacement data or change a shared dashboard to hide a missing series.

## Acceptance in this environment

All six native tabs were opened in the browser. The Qwen deployment row and latency/token/cache histories rendered; GPU exporter series and queue series for both Qwen backends rendered. GPU collection began after some earlier benchmark runs, so those runs have no matching native GPU history. Cluster resource charts rendered. Filtering **Usage** to `showroom-load` produced one Llama consumption row and its token chart; the displayed rounded counters included `1M` tokens, `2K` requests, zero rate-limited decisions, and one active user during the review. These are dated observations, not fixed targets for the next session. The panel limitations above remain visible and documented.
