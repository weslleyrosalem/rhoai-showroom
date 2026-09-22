# Contract for the optional gateway enforcement integration

This folder does not install IPP. Apply only after the prerequisites below are actually deployed. Source inspected at `opendatahub-io/ai-gateway-payload-processing` commit `07727563b63153c410434a20b62f3ebc5f24ed01` on 2026-09-22; select a tested compatible image digest before deploying. Do not silently replace the existing MaaS payload processor.

[Official IPP NeMo example](https://github.com/opendatahub-io/ai-gateway-payload-processing/blob/07727563b63153c410434a20b62f3ebc5f24ed01/examples/nemo/README.md) documents these plugin flags (replace the endpoint with the actual authenticated or private TLS endpoint of the showroom NeMo instance):

```text
--plugin
nemo-request-guard:nemo-input:{"nemoURL":"https://showroom-rails.ai-showroom.svc:8443/v1/guardrail/checks","timeoutSeconds":10}
--plugin
nemo-response-guard:nemo-output:{"nemoURL":"https://showroom-rails.ai-showroom.svc:8443/v1/guardrail/checks","timeoutSeconds":10}
```

The sample URL above is a contract, not evidence that port8443 exists. Discover the service ports/certificates produced by TrustyAI, validate the trust chain, and configure authentication before use. This upstream plugin schema has URL/timeout and no bearer-token option; it cannot automatically call a protected OAuth Route simply because an application can. A private TLS service/proxy compatible with the plugin and restricted by NetworkPolicy, or a supported token-forwarding integration, must be validated. Do not disable the existing public NeMo authentication as a workaround.

Required Envoy settings: filter named `envoy.filters.http.ext_proc.bbr`, correct insertion after gateway authentication, `response_body_mode: FULL_DUPLEX_STREAMED` and `response_header_mode: SEND`. The official chart must be installed in the namespace of the target Gateway. Set explicit processing timeouts and verify fail-closed behavior. A policy applied to a different Gateway does not protect this showroom.

NeMo returns `success`, `blocked`, `error` or `modified`. This IPP example maps `blocked` to403 and `error` to503. **It currently forwards the original content for `modified`**; do not claim that masking/redaction is effective through this plugin. The showroom config therefore blocks patterns rather than claiming redaction.

The integration is ready only when both `status.mcpGateway.mcpGatewayFound` and `status.bbrPlugin.bbrPluginFound` are true, `mcp-sse-strip` exists, a legitimate MCP call succeeds, a matching string in MCP arguments is blocked before backend execution, and a NeMo outage fails closed. Test real payloads and response paths; a created CR is insufficient.
