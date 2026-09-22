# MaaS: a 30-minute customer test drive

**Story:** Aurora Supply application teams consume a shared model through individually governed subscriptions. Platform operators own the model and policy; users receive an API endpoint and a scoped key.

## Presenter sequence

| Time | Screen or action | Observable result |
|---|---|---|
| 0–5 min | OpenShift AI model catalog and deployed models | Distinguish a discoverable catalog entry, a candidate registry record, and an actually Ready deployed endpoint. |
| 5–10 min | MaaS models, subscriptions, and API keys | Inspect `showroom-standard`, `showroom-test-drive`, and the separate `showroom-load` class. Never project a raw key. |
| 10–15 min | Aurora Supply or the Llama path in Playground | A valid standard credential receives a model response. The sustained benchmark uses a separate subscription and credential. |
| 15–22 min | A bounded quota rehearsal | Anonymous access fails. A valid test-drive request succeeds; exhausting its 100-token/minute allowance returns 429. The standard subscription still succeeds. Wait for the quota window before repeating. |
| 22–27 min | Groups and model access | Show platform administrators, data scientists, and visitors as separate groups. Group creation does not create an identity or log in a customer. |
| 27–30 min | GitOps and audit evidence | Inspect the owned subscription manifests, the key expiration annotation, and recorded response statuses. Explain how the same controls can be recreated. |

## Read-only checks

```bash
oc get maassubscription -n models-as-a-service
oc get authpolicy -n maas-how-to
oc get groups showroom-platform-admins showroom-data-scientists showroom-visitors
oc get secret showroom-guidellm-key -n ai-showroom \
  -o jsonpath='{.metadata.annotations.showroom\.openshift\.ai/expires-at}{"\n"}'
```

Never use `oc get secret -o yaml`, decode a Secret on a shared terminal, paste a key into slides, or display browser network headers during the demo. Use the [MaaS lab](../labs/maas.md) for guarded credential provisioning and the current subscription model reference. The installed existing-cluster overlay reuses the existing Llama endpoint; the fresh-cluster base points at the showroom Qwen model.

The native Qwen tool-and-knowledge Playground is a separate path using the current user’s Kubernetes authorization. It does not consume a MaaS key or the `showroom-standard` subscription; use Llama or Aurora Supply for this MaaS quota demonstration.

## What was tested

The initial rehearsal observed anonymous **401**, standard **200**, first test-drive **200**, exhausted test-drive **429**, standard control **200**, and test-drive **200** after the quota window. This demonstrates per-subscription governance for the tested keys. It does not establish a universal latency or throughput guarantee.

The current standard quota is 200,000 tokens/hour. The deliberately small test-drive quota is 100 tokens/minute. The sustained GuideLLM class has 1,500,000 tokens/hour and an independently expiring credential. Confirm the live values before presenting because policies can change through GitOps.

## Customer interaction

Let the customer choose a model from the curated catalog, inspect its pinned source and license, and register a candidate version. Then use the already Ready endpoint for a safe replenishment recommendation. If they issue their own key, use their actual authorized identity and subscription; do not add visitors to an administrative group merely to make the test drive work.

A key gives access to the subscription associated with its issuance. Quota behavior depends on measured token usage and policy propagation. Avoid repeated rapid 429 tests immediately before an interactive customer request. The protected GuideLLM window runs September 22 from 8:00 to 11:00 a.m. New York time; see the [load guide](sustained-load.md).

## Extend the governance test drive

The [AHEAD MaaS workshop](../labs/ahead-maas.md) provides an isolated tenant, explicit model-access matrix, group and individual subscription priorities, OIDC identities, and repeatable quota exercises. Its three CPU simulators demonstrate policy behavior; use the Aurora Llama path for real GPU inference. The external Anthropic example uses separate default-tenant governance and requires a private provider credential.
