# Aurora Workbench notebooks

Open **Projects → AI Showroom → Workbenches → Aurora Supply — Data Science Lab**, then open Jupyter. The repository normally lives at `/opt/app-root/src/rhoai-showroom` on the Workbench's persistent volume.

## Prepare the inference kernel

In the **Workbench terminal**, run:

```bash
cd /opt/app-root/src
bash rhoai-showroom/notebooks/setup-inference-kernel.sh
```

The script creates the separate persistent environment `/opt/app-root/src/.venvs/aurora-inference` and registers **Aurora Inference Demo**. It leaves the Workbench's base Python environment unchanged and does not start inference. It expects the standard Workbench home `/opt/app-root/src`, the rehearsed Python 3.12 version, a writable workspace PVC, and outbound access to the official PyPI, PyTorch CPU, and Hugging Face download services. An existing inference environment must also use Python 3.12; the script does not replace it automatically. Allow several minutes and sufficient free PVC space for CPU PyTorch and its dependencies.

The direct dependency versions match the rehearsed environment: GuideLLM 0.7.4, CPU PyTorch 2.13.0, Transformers 5.10.1, Datasets 4.4.1, Pydantic 2.12.5, HTTPX 0.28.1, NumPy 2.3.5, Matplotlib 3.11.0, ipykernel 7.3.0, nbformat 5.10.4, nbclient 0.11.0, Requests 2.34.2, and pandas 2.3.3. The script contains the exact pins and runs `pip check`. Transitive dependencies are resolved by pip; this is not a fully locked offline environment. Explicit official indexes avoid a stale default mirror. No private package-index credentials are inherited.

Only five public tokenizer/configuration files are downloaded for `Qwen/Qwen3-4B-Instruct-2507` revision `cdbee75f17c01a7cc42f958dc650907174af0554`. Every file must match its fixed SHA256 before installation. No model weights are downloaded. The verified files and `showroom-provenance.json` persist at `/opt/app-root/src/.cache/aurora-qwen-tokenizer`; notebook loading is offline with `trust_remote_code=False`.

Rerunning setup skips package downloads when every direct pin already matches and skips tokenizer downloads when all five hashes match. It rechecks dependencies and the persistent kernel registration. Setup logs stay private under `/opt/app-root/src/.showroom-setup/`. Do not publish those logs without review.

## Run the customer test drive

Select **Aurora Inference Demo** from the kernel picker before using the inference or MaaS notebooks:

| Notebook | What you do | What you observe |
|---|---|---|
| `07-qwen-live-traffic.ipynb` | Send an Aurora question, then deliberately start bounded manual traffic | Actual responses, per-request status/timing, and the existing native OpenShift AI charts |
| `08-qwen-guidellm.ipynb` | Run the short GuideLLM cell once | Real GuideLLM results, achieved throughput, latency, streaming TTFT when observed, and sanitized JSON/CSV/HTML reports on the PVC |

| `09-maas-api.ipynb` | Enter the approved MaaS endpoint/model and a masked API key | Discovery, one real response, status, latency, provider usage, and an optional disabled-by-default quota exercise |

The GuideLLM default requests at most three completions at 0.1 requests/second, concurrency one, with 64 output tokens. Its independent watchdog covers startup and execution. An interrupted or failed run remains visible in its status file. No unattended load is started by setup or left after a run returns.

Both notebooks start with explicit `BASE_URL`, `MODEL_ID`, and `AUTH_MODE` settings. The prepared `service_account` mode reads the Workbench's rotating credential in memory and restricts it to the exact private Gateway and matching model path. Existing routing and RBAC authorize only the prepared Qwen model; changing a name does not grant access. For another HTTPS OpenAI-compatible endpoint, use `api_key` mode and enter an endpoint-bound key through the masked prompt. Redirects and environment proxies are disabled, and TLS verification remains enabled. The model discovery preflight must list the exact selected model before generation starts.

GuideLLM also requires a matching tokenizer. Notebook 08 exposes `TOKENIZER_ID`, an immutable `TOKENIZER_REVISION`, and the explicit `TOKENIZER_FOR_MODEL` binding. Its default uses the verified Qwen preset. For another model, deliberately run the tokenizer preparation cell with the correct public Hugging Face ID and revision; it downloads only allowlisted tokenizer files, not weights or Python code. A changed model with the stale Qwen binding is refused. This association is supplied by the operator: the models API does not attest the remote weights or tokenizer. Use notebook 07's manual client when a frontier model has no known compatible public tokenizer.

The private Qwen Gateway must already be deployed with the narrowly scoped Workbench access policy. Setup does not create Kubernetes permissions, credentials, models, GPUs, or cloud resources. Never display or save `showroom_workbench.connection()` because its returned dictionary contains the live credential. Saved GuideLLM reports redact the target endpoint and identify the model and tokenizer without claiming that the remote model revision was verified.

Use **Observe & monitor → Dashboard**, rechecking **Project = ai-showroom** and **Model = aurora-qwen-4b** on each LLM tab. The private Qwen route is separate from the Llama `showroom-load` MaaS subscription. See the [native dashboard guide](https://weslleyrosalem.com/rhoai-showroom/operations/native-dashboards/) for chart definitions, scrape-window limits, and unavailable native inter-token latency. A short shared-system run demonstrates measurement; it does not establish capacity or prove a routing/cache speedup.

The earlier notebooks cover demand forecasting, RAG, Ray, evaluation, AutoRAG, and Feature Store. Follow each notebook's own kernel and dependency instructions; installing the inference kernel does not validate every science notebook under that kernel.
