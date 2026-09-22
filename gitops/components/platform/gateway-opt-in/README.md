# Shared MaaS gateway restriction — reviewed opt-in

The reference gateway was observed with `allowedRoutes.namespaces.from: All`. RHOAI3.5 known issue RHOAIENG-80360 describes route hijacking risk. This directory is intentionally absent from Kustomize bases and profiles; it does not change a shared gateway automatically.

Before using the JSON patch:

1. Read the gateway's live listeners and every HTTPRoute parentRef. Confirm the intended listener is still index0 and named `https`; the patch has a test for that name and preserves hostname, TLS and ports.
2. Inventory every legitimate route namespace. In the inspected installation, MaaS routes came from `maas-how-to` and `redhat-ai-gateway-infra`. Add the new `ai-showroom` and `ai-showroom-bench` only when their routes are intended to attach. Do not copy this list without a fresh inventory.
3. Label the approved namespaces `showroom.openshift.ai/maas-gateway-access=true` through their owning configuration. Namespace labels must be controlled by trusted administrators; untrusted users should not be able to label arbitrary namespaces into this allowlist.
4. Save the original allowedRoutes and resourceVersion privately. Add an optimistic-concurrency test against the fresh resourceVersion to the patch before execution, and inspect the diff. If there is a race, refresh; never force it.
5. Apply the reviewed JSON Patch to the intended gateway. Do not use this file as a merge patch: listener arrays must not be replaced wholesale.
6. Verify existing MaaS API, Llama, Claude, new models, route Accepted/ResolvedRefs and negative attach tests. Roll back the allowedRoutes field if an expected namespace was omitted, then repair the reviewed allowlist.

No operation above was performed by this module. The patch is a starting artifact for a concrete maintenance change, not an installation shortcut.

Source: [Known issues3.5](https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html/release_notes/known-issues_relnotes).
