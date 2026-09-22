# Aurora workbench

Open project `ai-showroom`, then workbench **Aurora Supply — Data Science Lab**. It has a persistent 10 GiB workspace, CPU resources, OpenShift authentication, the service CA, and MLflow integration.

The initialization container clones the public repository into `/opt/app-root/src/rhoai-showroom`. It does not overwrite an existing checkout. Use `git pull --ff-only` when you want an updated lab and have no conflicting local edits.

Run notebooks in order:

1. `01-demand.ipynb`: data, measured forecast, MLflow, and S3.
2. `02-rag.ipynb`: retrieval and the real assistant request.
3. `03-ray.ipynb`: inspect and launch distributed CPU training.
4. `04-evaluation.ipynb`: inspect providers and run a measured evaluation.
5. `05-native-autorag.ipynb`: inspect a completed native pattern and run semantic inference.

The notebook controller creates its own service account, `aurora-lab`. Evaluation access is explicitly bound to that account. Administrative setup commands run from the presenter's authenticated terminal, not by granting cluster administration to the notebook.

Acceptance: authenticated access, persisted files after restart, dataset execution, and a real MLflow write.

The base image uses its own Python environment. Re-run each notebook's pinned dependency cell after a workbench restart; the workspace files persist, while packages installed in the container environment do not.

## Run the inference and MaaS notebooks

Open **Projects → AI Showroom → Workbenches → Aurora Supply — Data Science Lab** (`aurora-lab`) and launch JupyterLab. Browse to `/opt/app-root/src/rhoai-showroom/notebooks`, open one notebook, and select **Kernel → Change Kernel → Aurora Inference Demo**. Then choose **Run → Run All Cells**. Run one notebook at a time.

| Notebook | What Run All starts | Bounded test drive |
|---|---|---|
| `07-qwen-live-traffic.ipynb` | One test call, then six requests at concurrency 1, two seconds between starts, and 96 output tokens per request | Edit the configuration cell. Hard caps: 30 requests, 180 seconds, concurrency 2, and 256 output tokens per request. Tables and plots use actual response metrics. |
| `08-qwen-guidellm.ipynb` | A real GuideLLM run requesting at most three completions at 0.1 requests/second, concurrency 1, and 64 output tokens | Inspect its report before changing the optional settings. Caps: 120 seconds of measurement, 180 seconds total, 0.1 requests/second, concurrency 2, and 128 output tokens. The optional cell only defines settings; it does not launch another run. |
| `09-maas-api.ipynb` | Read the authorized model list and send one MaaS request with a masked API key | Configure the HTTPS endpoint and exact model ID. The optional quota probe is disabled by default; when deliberately enabled, it stops on the first 429 or error. |

These three notebooks use the separate persistent environment `/opt/app-root/src/.venvs/aurora-inference`; they do not depend on packages installed into the base kernel. The manual notebook's test call must succeed before its loop starts. **Interrupt kernel** stops active client work; completed, failed, and interrupted outcomes remain distinct. A server may finish a request it already accepted after the client disconnects.

The first cell in 07 and 08 exposes `BASE_URL`, `MODEL_ID`, and `AUTH_MODE`. The Qwen preset uses the Workbench's rotating identity, with no key entry. That token is restricted to the exact private Gateway and named project route; changing a URL does not grant access to another model. For another approved HTTPS endpoint, choose `api_key` and use the masked prompt. Keys are bound to that endpoint, redirects are refused, and TLS verification stays enabled. The preset namespace-local hop is HTTP with Kubernetes authentication and model authorization; browser ingress uses TLS. Notebook 09 demonstrates the separate MaaS subscription/API-key path. Private reports persist outside the Git checkout; never publish credentials or raw private reports, and clear notebook outputs before sharing a copy.

To connect the exercise to the customer story, open **Observe & monitor → Dashboard** and inspect **LLM Traffic**, **LLM Performance**, and **LLM Utilization** with **Project = ai-showroom** and **Model = aurora-qwen-4b**. Recheck those filters after changing tabs and choose a range containing the notebook's UTC timestamps. Look for requests, token activity, queue activity, and GPU use; a short burst can be diluted by the collection interval, and other Qwen clients share these graphs. The manual notebook measures non-streaming client elapsed time, while GuideLLM reports streaming timing only when observed. Neither notebook alone establishes a causal routing or cache speedup. See the [native dashboard guide](../operations/native-dashboards.md).

For a different model in 08, also choose its actual Hugging Face tokenizer ID, immutable revision, and explicit served-model binding. The notebook refuses a stale Qwen binding before sending requests. Its optional preparation cell downloads tokenizer files only. It cannot attest the weights behind a remote endpoint. Start with the prepared Qwen preset when reviewing the demo.

The current Workbench already has the kernel. On another prepared showroom Workbench, use the [setup script and instructions](https://github.com/weslleyrosalem/rhoai-showroom/blob/main/notebooks/README.md). The script uses Python 3.12, keeps dependencies on the PVC, and starts no inference. Native model access requires the separately applied private-Qwen access profile; it is not automatically reconciled by the core Argo overlay.
