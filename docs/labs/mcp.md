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

The Gateway permits `aiadmin`, exactly the three `showroom-*` groups declared in the foundation, and the named visitor, engineer, `aurora-science`, and `aurora-lab` service accounts. An arbitrary group sharing the prefix is not allowed. The backend, broker, private listener, and NeMo adapter are protected by NetworkPolicy.

## Configure the authenticated gateway

Build the backend using the [application instructions](https://github.com/weslleyrosalem/rhoai-showroom/blob/main/apps/aurora-tools/README.md), then apply the MCP and integrated guardrails overlays. Set `SHOWROOM_SERVER` to the intended cluster API address from an independently checked installation record, then configure the TokenReview audience:

```sh
python apps/aurora-tools/configure_gateway.py \
  --expected-server "$SHOWROOM_SERVER" --apply
```

Keep the independently recorded expected API URL for interactive and automated runs. The helper probes TokenReview using the current token only in memory and merges the audience field without replacing other policy rules. The committed placeholder fails closed. Argo must preserve the cluster-specific audience through its configured `ignoreDifferences` rule.

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

The internal and public SDK sequences passed, along with the full 14-case authentication/input matrix, a synthetic output block, and a checker-outage test. The overlay buffers the MCP router request before downstream IPP processing; this resolved duplicated body delivery in the pinned stack. Keep that version-specific merge when reproducing this configuration. Public exposure remains a separate overlay so a new cluster must pass the same gates before publication.

## Native Playground MCP assets

The AI Hub catalog and the Playground MCP asset list are separate configuration surfaces. The Playground reads `gen-ai-aa-mcp-servers` in `redhat-ods-applications`. Each data key contains JSON with `url` and `description`; credentials do not belong in this ConfigMap. See the [Playground prerequisites](https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html/experimenting_with_models_in_the_gen_ai_playground/playground-prerequisites_rhoai-user).

After the authenticated public Gateway passes its tests, merge the Aurora entry:

```sh
python apps/aurora-tools/configure_playground.py \
  --expected-server "$SHOWROOM_SERVER" --apply
```

The helper discovers the local TLS Route, preserves other administrators' entries, checks ownership of its own key, and uses the resource version to reject concurrent overwrites. It stores no token or cluster hostname in Git. Reload **Gen AI studio → AI asset endpoints → MCP servers** or the Playground MCP selector and find **Aurora-Supply-Showroom**. A displayed server still requires a permitted OpenShift bearer credential when connecting; listing an asset does not bypass Gateway authorization. Verify tool discovery and a real tool call before claiming the native Playground path passed.

## Catalog and lifecycle test drive

The shared catalog source is merged independently from Argo, preserving other administrators' entries:

```sh
python -m pip install PyYAML==6.0.2
python apps/aurora-tools/configure_catalog.py \
  --expected-server "$SHOWROOM_SERVER" --apply
oc apply -k gitops/components/mcp/lifecycle-isolation
oc apply -k gitops/components/mcp/lifecycle
oc get mcpserver aurora-tools-lifecycle -n ai-showroom
```

Open **AI hub → MCP servers**, search for **Aurora Supply**, inspect the three read-only tools, and compare the image and prerequisite data with Git. The catalog administrative interface is Developer Preview; lifecycle deployment is Technology Preview. See [lifecycle enablement](https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html/working_with_the_mcp_catalog/enabling-mcp-lifecycle-management).

The catalog API returned the Aurora card after the ConfigMap projection reloaded. The prepared `MCPServer` has completed an operator MCP handshake and reached Ready. Lifecycle management alone does not provide Gateway authentication. In the installed alpha API, the operator creates an ingress policy allowing its service port from all sources; ordinary NetworkPolicies are additive, so an extra deny policy cannot override it. The separate cluster-scoped `AdminNetworkPolicy/showroom-mcp-lifecycle-isolation` therefore selects only the lifecycle test-drive pods in `ai-showroom`, permits the lifecycle operator handshake, and denies other pod ingress and all egress. Its priority must be checked against any existing administrator policies on a new cluster. Positive operator handshake and negative visitor/other-namespace connection tests passed. It has no public Route and is not the core RAG backend. Use an administrator port-forward for inspection.

For the interactive **Deploy MCP server** dialog, replace the generated YAML with the [reviewed catalog test-drive manifest](https://github.com/weslleyrosalem/rhoai-showroom/blob/main/gitops/components/mcp/catalog/testdrive.yaml). It uses the distinct name `aurora-tools-testdrive`, a matching MCP host allowlist, the canonical data ConfigMap, and `spec.extraLabels.showroom.aurora/component: lifecycle-test-drive`. Keep that label so the administrator policy selects the generated pods. Bare generated YAML does not establish this security boundary. After the exercise, remove only this explicitly created test-drive server; keep `aurora-tools-lifecycle` for the prepared demonstration.

## Version-specific operational notes

- Gateway 0.7.1 requires an explicit namespace in `targetRef` at reconciliation time.
- The registration HTTPRoute attaches to the extension's listener as well as the private listener. The initialization hairpin uses port 8080 and passes through MCP processing.
- SDK host validation must accept `aurora-tools.mcp.internal` with and without a port.
- After initial registration, the broker may require a rollout restart to reload the projected configuration; verify discovery rather than assuming Ready means loaded.
- VirtualServer is optional discovery organization, not an authorization boundary. Version 0.7.1 writes its configuration to a hardcoded `mcp-system` location; this isolated deployment keeps it outside the default Kustomization rather than leaving GitOps degraded.
- This Gateway version can log session JWTs at INFO. Never publish raw pod logs; restrict access and review log retention before extending the demo beyond synthetic data.

The source of truth for the observed controller behavior is [Gateway 0.7.1](https://github.com/Kuadrant/mcp-gateway/tree/v0.7.1). Revalidate these workarounds before upgrading.
