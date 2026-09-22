# MCP tools, access control, and lifecycle

MCP Gateway and Lifecycle are Technology Preview in OpenShift AI 3.5. Aurora is demonstration code built with the official Python SDK. Its tools read synthetic inventory and prepare proposals; they cannot execute commands, open arbitrary URLs, purchase products, or change stock.

## Connected architecture

| Component | Responsibility |
|---|---|
| `aurora-tools:8000/mcp` | Private read-only backend: `list_products`, `get_stock`, `get_replenishment_recommendation` |
| `showroom-mcp` Gateway | MCP routing, OpenShift token authentication, explicit identity allowlist, NeMo IPP |
| `MCPServerRegistration/aurora-tools` | Discovers three tools with the `aurora_` prefix |
| `showroom-mcp-istio:8080/mcp` | Stable internal endpoint used by RAG |
| `MCPServer/aurora-tools-lifecycle` | Separate lifecycle test drive managed by the operator |
| Aurora catalog source | Discoverable metadata and deployment prerequisites |

The Gateway permits `aiadmin`, exactly the three `showroom-*` groups declared in the foundation, and the named visitor, engineer, and `aurora-science` service accounts. An arbitrary group sharing the prefix is not allowed. The backend, broker, private listener, and NeMo adapter are protected by NetworkPolicy.

## Configure the authenticated gateway

Build the backend using the [application instructions](https://github.com/weslleyrosalem/rhoai-showroom/blob/main/apps/aurora-tools/README.md), then apply the MCP and integrated guardrails overlays. Configure the TokenReview audience against the expected cluster:

```sh
python apps/aurora-tools/configure_gateway.py \
  --expected-server "$(oc whoami --show-server)" --apply
```

For automation, supply an independently recorded expected API URL rather than accepting the current context. The helper probes TokenReview using the current token only in memory and merges the audience field without replacing other policy rules. The committed placeholder fails closed. Argo must preserve the cluster-specific audience through its configured `ignoreDifferences` rule.

On the tested ROSA installation, the correct audience is the API's OIDC issuer audience; `https://kubernetes.default.svc` is insufficient. The gateway also needs verified TLS to Authorino's authorization service; `auth-tls.yaml` configures the service CA and exact service identity.

## Test the protocol and authorization

```sh
oc port-forward -n ai-showroom service/showroom-mcp-istio 33080:8080
```

In another terminal:

```sh
python apps/aurora-tools/smoke_mcp.py --url http://127.0.0.1:33080/mcp
```

The [protocol helper](https://github.com/weslleyrosalem/rhoai-showroom/blob/main/apps/aurora-tools/smoke_mcp.py) initializes a real session, discovers tools, and calls all three. Expected names are `aurora_list_products`, `aurora_get_stock`, and `aurora_get_replenishment_recommendation`, plus Gateway discovery helpers. It rejects non-TLS remote URLs and redirects and never prints tokens.

The acceptance matrix requires anonymous initialization 401, a valid unlisted service account 403, and an allowed identity 200. A permitted stock query must return data; a synthetic email or `DEMO_SECRET_AURORA` in an argument must be blocked by NeMo. A checker outage must fail closed. Also test that an unrelated pod cannot reach private backend ports.

The internal SDK sequence passed. The pinned IPP stack currently has a public-route edge case: a sequence including `list_products` can cause a later body to be parsed as concatenated JSON and return 400. Keep public protocol acceptance open until the full SDK sequence is stable; a successful single HTTP call is insufficient. Public exposure is a separate overlay and must retain authentication throughout testing.

## Catalog and lifecycle test drive

The shared catalog source is merged independently from Argo, preserving other administrators' entries:

```sh
python -m pip install PyYAML==6.0.2
python apps/aurora-tools/configure_catalog.py \
  --expected-server "$(oc whoami --show-server)" --apply
oc apply -k gitops/components/mcp/lifecycle
oc get mcpserver aurora-tools-lifecycle -n ai-showroom
```

Open **AI hub → MCP servers**, search for **Aurora Supply**, inspect the three read-only tools, and compare the image and prerequisite data with Git. The catalog administrative interface is Developer Preview; lifecycle deployment is Technology Preview. See [lifecycle enablement](https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html/working_with_the_mcp_catalog/enabling-mcp-lifecycle-management).

The prepared `MCPServer` has completed an operator MCP handshake and reached Ready. Lifecycle management alone does not provide Gateway authentication. In the installed alpha API, the operator creates an ingress policy allowing its service port from all sources; ordinary NetworkPolicies are additive, so an extra deny policy cannot override it. Isolation must be resolved before offering this replica as a protected shared endpoint. It has no public Route and is not the core RAG backend. Use an administrator port-forward for inspection while the isolation gate is open.

## Version-specific operational notes

- Gateway 0.7.1 requires an explicit namespace in `targetRef` at reconciliation time.
- The registration HTTPRoute attaches to the extension's listener as well as the private listener. The initialization hairpin uses port 8080 and passes through MCP processing.
- SDK host validation must accept `aurora-tools.mcp.internal` with and without a port.
- After initial registration, the broker may require a rollout restart to reload the projected configuration; verify discovery rather than assuming Ready means loaded.
- VirtualServer is optional discovery organization, not an authorization boundary. Version 0.7.1 writes its configuration to a hardcoded `mcp-system` location; this isolated deployment keeps it outside the default Kustomization rather than leaving GitOps degraded.
- This Gateway version can log session JWTs at INFO. Never publish raw pod logs; restrict access and review log retention before extending the demo beyond synthetic data.

The source of truth for the observed controller behavior is [Gateway 0.7.1](https://github.com/Kuadrant/mcp-gateway/tree/v0.7.1). Revalidate these workarounds before upgrading.
