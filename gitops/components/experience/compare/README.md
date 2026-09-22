# Live inference comparison

This optional profile adds a small CPU application and an authenticated OpenShift Route. It reuses the two existing `ai-showroom/aurora-qwen-4b` vLLM replicas. It does not change the model, scheduler, GPUs, notebooks, or sustained GuideLLM Job.

The user submits one system prompt and one message. The server sends the same model, messages, sampling settings, and output-token limit through explicit round-robin and through the private llm-d Gateway. Paths execute sequentially and the first path alternates. Every click is one bounded comparison, not an automatic benchmark. The browser displays actual streamed content and measured first-content and total times.

## Prerequisites

- The two Qwen backends, private `showroom-inference` Gateway, and matching Qwen serving certificate already exist.
- The namespace contains the injected `showroom-service-ca` ConfigMap.
- An administrator has independently verified the cluster and identity. Apply only to the intended showroom.
- The application image is built from the reviewed source in `apps/aurora-compare/`.

## Install

1. Review and apply this Kustomize profile. It is deliberately outside the core overlay. Supply a private overlay for `aurora-compare-settings.data.PUBLIC_ORIGIN` with the exact admitted Route's `https://` origin. The checked-in placeholder refuses actual requests.
2. Create the `aurora-compare-cookie` Secret with a randomly generated 32-byte, base64-encoded `cookie-secret` value. Generate it in memory or a private file outside Git; never pass it as a literal command-line argument or commit it.
3. Build the `aurora-compare` BuildConfig from the reviewed repository revision. For a staged local rehearsal, `oc start-build aurora-compare --from-archive=<reviewed-source.tar.gz> -n ai-showroom` uses a binary source archive containing only this application's files at their repository-relative paths.
4. Wait for the image and Deployment to become Ready. Obtain the Route with `oc get route aurora-compare -n ai-showroom`. Open it and authenticate through OpenShift. A user must already have `get` access to the exact `ai-showroom/aurora-compare` Service; this profile does not add a user entitlement.
5. Verify an anonymous request redirects to login, then run one short pair from the authenticated page. Repeat once to inspect explicit baseline alternation. Keep the default output limit initially.

The Route terminates with re-encryption at the OpenShift OAuth proxy. The application listens only on Pod loopback. Its projected service-account identity can get only the named Qwen Endpoints and model resource. Native inference uses that shared application identity; it does not impersonate the browser user. The baseline uses verified backend HTTPS with only the model's public CA mounted. No service-account token is sent to a baseline backend. NetworkPolicy allows only this application's pods to enter the existing baseline/Gateway paths. The API and OAuth egress port allowances are not a destination-specific egress firewall.

## Interpretation and cleanup

Both paths use vLLM. The baseline bypasses Gateway authentication and scheduling, so latency differences include different overhead. Caches are shared and are not cleared. A sequential second path may reuse work from the first. Other users and workloads remain active. Repeating a prefix explores these effects but cannot isolate a causal llm-d benefit or prove cross-node KV transfer.

Only the baseline's explicitly selected replica alias is known to the app. No selected llm-d replica or per-request cache-hit claim is inferred. Use native dashboards with their own time window and shared-model scope. Successful transport is not model-quality approval.

Stop disconnects the client and requests bounded server cancellation. A serving engine can finish a request already accepted. This profile starts no background inference. Remove only the resources in this optional profile and its dedicated cookie/TLS Secrets when retiring the app; do not remove the shared Qwen certificate, model, or gateway.
