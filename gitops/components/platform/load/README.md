# Opt-in sustained GuideLLM load

This component is excluded from normal overlays. It creates a dedicated MaaS subscription, CPU-only Job, retained results PVC, ServiceAccount without an API token, and a deny-ingress NetworkPolicy. Review the exact model, dates, StorageClass, quota, and resource limits before use. No cloud APIs are called.

GuideLLM v0.7.4 image: `ghcr.io/vllm-project/guidellm@sha256:15372f9f3f407366495470706b7a07f64addcce5d134a49cab64149b44ab1233` (verified Linux AMD64 manifest).

Use the [sustained load runbook](https://weslleyrosalem.github.io/rhoai-showroom/demos/sustained-load/) and guarded `scripts/guidellm_load.py`. The launcher defaults to PLAN, requires an explicitly reviewed cluster/user, verifies key lifetime, and preserves existing results. It cannot issue a key or silently replace a completed Job. Load initially stays capped at 0.1 requests/second until an operator reviews the measured pilot. The public Job's absolute dates describe the scheduled September 22–23, 2026 run; expired dates are rejected by the launcher.

The runtime verifies HTTPS, disables redirects, routes backend validation to authenticated `/v1/models`, uses the proven standard MaaS path without a model-selection header, and stores the API key only in the child environment. NetworkPolicy permits DNS in openshift-dns (including the OpenShift 5353 target port) and outbound HTTPS; it exposes no ingress. The load pod has no Kubernetes API permissions or mounted service-account token. Results are private on the retained PVC.

The shared Gateway accepted isolated explicit-header EPP requests, but repeated GuideLLM qualification returned empty streaming responses. Failed reports are retained. This long run demonstrates real MaaS/vLLM traffic; the dedicated private Qwen Gateway demonstrates actual endpoint-picker processing. HTTP/1.1 is explicit after a prior HTTP/2 connection error.
