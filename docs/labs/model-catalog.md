# Lab — a curated Qwen catalog

Aurora Supply offers a small, understandable selection. **Aurora Supply · Qwen curated** includes Qwen3-0.6B, Qwen3-4B-Instruct-2507, and Qwen3-32B. These cover small-model smoke tests, the assistant, and the scaling experiment.

The catalog is shared across the cluster. Configuration resides in `rhoai-model-registries/model-catalog-sources`. This repository owns one source entry; it does not replace another team's ConfigMap.

## Curate through the dashboard

Under Settings → Model resources and operations → Model catalog settings, add a Hugging Face source for organization `Qwen`. Enter the three model names above **without** `Qwen/` in the inclusion field. Preview the results and wait for Connected. The 3.5 documentation limits this source to public, non-gated models and requires Hugging Face connectivity. Importing a model does not make it Red Hat validated or supported. [Add a source](https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html/manage_and_govern_model_catalog_sources/add-model-catalog-source_manage-govern-model-catalog-sources), [limitations](https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html/manage_and_govern_model_catalog_sources/manage-model-catalog-sources-in-dashboard_manage-govern-model-catalog-sources).

## Reproduce the configuration

The helper requires Python and PyYAML. Its default mode only reads and proposes changes:

```bash
python3 gitops/components/platform/catalog/merge_catalog.py \
  --expected-server "$EXPECTED_OPENSHIFT_SERVER"
```

Check the model names and preserved source count. `--apply` merges only `showroom-qwen`. A `resourceVersion` test prevents overwriting a concurrent dashboard or controller update:

```bash
python3 gitops/components/platform/catalog/merge_catalog.py \
  --expected-server "$EXPECTED_OPENSHIFT_SERVER" --apply
```

The same configuration returns UNCHANGED on a subsequent run. On conflict, read fresh state and review again. Do not restart the catalog or replace its default sources to resolve a conflict. Integrate this controlled merge into installation; two Argo Applications must not own the entire shared ConfigMap.

## Match models to hardware

| Model | Approximate BF16 weights | Initial hardware | License |
|---|---:|---|---|
| Qwen3-0.6B | 1.4GiB | GPU smoke test; optional H100 MIG lab; CPU runtime remains unvalidated | Apache2 |
| Qwen3-4B-Instruct-2507 | 7.5GiB | One L40S,8192-token context | Apache2 |
| Qwen3-32B | 61GiB | Four L40S, TP4 | Apache2 |
| Qwen2.5-72B-Instruct, separate opt-in | 135.4GiB | TP4; two replicas require eight GPUs | Qwen-specific license |

These numbers cover **weights only**. Runtime, activations, KV cache, and concurrency require additional memory. The default configuration does not enable `trust_remote_code`. Qwen72B is outside the curated catalog and the full profile; its license is not Apache2. [Qwen4B](https://huggingface.co/Qwen/Qwen3-4B-Instruct-2507), [Qwen32B](https://huggingface.co/Qwen/Qwen3-32B), [Qwen72B](https://huggingface.co/Qwen/Qwen2.5-72B-Instruct).

`gitops/components/models/models.lock.json` records model revisions and the runtime digest. The runtime came from the installed RHOAI 3.5.1 preset. Model weights are public; the Red Hat image requires valid registry entitlement in the cluster pull secret. Schema acceptance does not prove download, startup, or tool-calling quality.

## Acceptance

The source must be Connected and show exactly the three curated models, correct licenses, and preserved existing sources. The reference installation's catalog API has reported this source as `available` with those three models and all three default sources retained.

A selected deployment must load the pinned revision, become Ready, and respond through its intended access path. The reference Qwen4B uses the private native-auth path documented in the [inference guide](../demos/inference.md), and is deliberately absent from MaaS discovery. Llama provides the shared MaaS application endpoint. The Qwen registry entry remains a candidate: successful serving does not approve safety or quality. Before connecting an agent, require a valid `tool_call` matching the intended schema. The optional CPU version of Qwen0.6B remains blocked until a CPU runtime is validated on actual hardware.
