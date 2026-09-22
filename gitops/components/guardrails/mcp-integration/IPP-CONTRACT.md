# MCP → IPP → NeMo integration contract

This overlay deploys the IPP plugins, a private HTTPS authentication adapter, NetworkPolicies, and the TrustyAI Gateway reference. It does not change the existing MaaS processor. All resources are limited to `ai-showroom`; NeMo keeps its authenticated public Route.

```
MCP client → TLS Route → Gateway [MCP routing, Authorino, IPP, SSE stripping]
                                            ↓ gRPC9004, NetworkPolicy
                                      showroom-mcp-ipp
                                            ↓ verified HTTPS9443
                                    showroom-rails-private
                                            ↓ verified HTTPS443 + projected SA token
                                     managed showroom-rails
```

The adapter is showroom integration code, not a Red Hat product feature. Its service has an OpenShift serving certificate, no Route, and an ingress policy permitting only the IPP pod. It accepts only POST `/v1/guardrail/checks`, selects a fixed upstream and fixed `showroom-safety` configuration, rejects redirects, and reads the rotating SA token for each call. Its SA can only `get services` in this namespace. The RHOAI3.5 RBAC proxy's observed SubjectAccessReview omits the service name, so a Role restricted by `resourceNames` returns403; no Secret, write, list or watch rights are granted.

The Gateway→IPP gRPC hop is plaintext inside the cluster and isolated by NetworkPolicy. The pinned IPP has only automatic self-signed secure serving, not a serving-cert-file flag. This demo deliberately does not disable TLS certificate verification to accommodate that mode. Do not describe the deployment as end-to-end mTLS. IPP→adapter and adapter→NeMo both verify certificate trust and hostname.

## Version-specific compatibility

The pinned RHOAI3.5 IPP digest is `sha256:83091d245d7ae9275ba27db0aed50bfc0b80b78b6ef28b77db7f62c175b14fe2`, observed in the installed platform. Its plugin expects `passed`, while the managed `/v1/guardrail/checks` endpoint returns `success`. This mismatch was reproduced as500 on a legitimate tool call. Upstream fixed the mismatch in [commit d32e434 / PR434](https://github.com/opendatahub-io/ai-gateway-payload-processing/commit/d32e434009ae5b1a3077945ec9d620a9f49dc532). The adapter explicitly translates only `success`→`passed` for this pinned image; `blocked` stays blocked, all unknown/error/modified outcomes fail closed. Revalidate and remove that translation when adopting an image containing the upstream fix.

The current [official NeMo plugin example](https://github.com/opendatahub-io/ai-gateway-payload-processing/blob/07727563b63153c410434a20b62f3ebc5f24ed01/examples/nemo/README.md) defines `nemoURL` and `timeoutSeconds` only. It provides no bearer-token injection field. The private adapter closes this gap without disabling authentication on NeMo. Never send a real user token to an arbitrary plugin URL.

## Envoy contract

The filter name must be `envoy.filters.http.ext_proc.bbr`. Real active Envoy configuration must show Authorino's `envoy.filters.http.wasm` before that filter, then `mcp-sse-strip`'s Lua filter before the router. The IPP filter sets both body directions to `FULL_DUPLEX_STREAMED`, headers/trailers to `SEND`, and `failure_mode_allow:false`. Envoy rejects FULL_DUPLEX_STREAMED with trailer mode SKIP, keeping an older active listener; therefore a created EnvoyFilter and CR Ready status do not prove enforcement.

The preceding MCP router filter is merged to use `BUFFERED` request bodies. With its original `STREAMED` request mode, the pinned two-processor chain intermittently delivered duplicate JSON to IPP and failed with HTTP400. Buffering that router stage resolved full internal/public SDK sequences while retaining downstream input/output enforcement. This is distinct from IPP itself, which still requires FULL_DUPLEX_STREAMED.

The TrustyAI CR Gateway reference causes creation of `mcp-sse-strip`. Applying the base while this overlay is active removes the reference; Argo must own this complete overlay to prevent competing configuration. It must not self-heal the base over the integration.

## Acceptance gates

- Active listener includes authentication, IPP and SSE filters in the verified order.
- `mcpGatewayFound` and `bbrPluginFound` are true, with current spec still containing the Gateway reference.
- Anonymous initialization401, valid but unlisted SA403, listed identities200.
- Valid stock tool call200; synthetic email or `DEMO_SECRET_AURORA` in tool arguments403 before tool execution.
- A genuinely unavailable bridge/checker fails closed; wait for termination, since existing keep-alive connections may finish while a pod drains.
- A dedicated output challenge returned403 when a permitted stock request received a backend response containing a synthetic email. The original fixture was restored immediately. Repeat this gate after upgrades; merely configuring the response plugin is insufficient.
- No pod without the allowed network labels reaches backend, broker, private listener or adapter.

Use only synthetic challenges and record status/result metadata, never tokens or full request logs. The MCP Gateway itself can log session JWTs at INFO in this version; do not publish raw pod logs, and configure log handling/retention before a production use case.
