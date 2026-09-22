# AHEAD — isolated MaaS governance workshop

AHEAD lets platform teams demonstrate model access, token budgets and external identity without changing the existing Aurora inference service. Three small CPU simulators make policy outcomes repeatable; a separately registered Anthropic endpoint demonstrates a real external-model call.

Use this workshop for the question **“How do different teams safely consume the same model platform?”** Use the [inference lab](benchmark.md) for measured engine behavior and the [main MaaS test drive](../demos/maas.md) for Aurora's real Llama path. Simulator traffic is not GPU performance evidence.

## What is ready

The September 22, 2026 rehearsal verified the core lab path on OpenShift AI 3.5.1: deployments, API keys, inference, access denials, quota isolation/recovery, OIDC, group and individual tiers, service accounts, corporate access rules, cached JWT verification, external inference and sampled usage metrics. The native **Projects → AHEAD** page showed three Ready deployments.

| Component | Purpose | Location |
|---|---|---|
| `ahead-simulator` | Shared general-purpose policy target | `ahead` |
| `ahead-code-simulator` | Second model in the corporate access matrix | `ahead` |
| `ahead-cloud-simulator` | Simulated cloud-cost policy target | `ahead` |
| `ahead-claude-sonnet` | Real external Anthropic inference | `ahead`, default MaaS gateway |
| `AITenant/ahead` | Dedicated tenant and gateway association | `ai-tenants` |
| AHEAD subscriptions and authorization policies | Dedicated governance | `ai-tenant-ahead` |
| Keycloak realm `ahead` | Separate lab identities and groups | `ahead` |
| `ahead-keycloak-db` | Persistent Keycloak database, 1Gi PVC | `ahead` |

The namespace is lowercase `ahead`; the project display name is **AHEAD**. The operator also creates `ai-tenant-ahead` and per-tenant infrastructure resources. No new GPU, cloud load balancer or machine pool was provisioned. The gateway uses a ClusterIP service behind an OpenShift Route.

**Execution boundaries:** optional global Loki usage logging and Redis persistence for the shared Limitador are deferred because they modify shared services and can affect other demonstrations. Provider/model choices in the source guide are alternatives: this workshop uses CPU simulators and the available Anthropic provider, not every listed GPU model and cloud provider. Multi-tenancy and external identity/model capabilities retain their documented Technology Preview maturity.

[Download the sanitized validation record](../results/ahead-maas/validation.json). Its statuses distinguish verified behavior, deferred changes and known limitations.

## A 30-minute walkthrough

| Time | Action | Expected observation |
|---|---|---|
| 0–4 min | Open **Projects → AHEAD → Overview / Deployments** | Three Ready resources explicitly named CPU, code and cloud **simulators** |
| 4–9 min | Run authentication and quota rehearsal | Anonymous/invalid 401; authenticated 200; free 429; premium still 200; free recovery after its window |
| 9–14 min | Inspect group and individual subscriptions | Carol gets the team tier; Alice and Bob get their named overrides |
| 14–18 min | Compare the two priority-demo users | The larger set of group allowances does not accumulate; the selected priority determines one entitlement |
| 18–23 min | Exercise the three corporate identities | Sales sees one model, Products two, Engineering three; forbidden calls return 403 |
| 23–27 min | Show service-account and OIDC evidence | In-cluster token-based inference, scoped external identities, and JWT validation during an isolated IdP outage |
| 27–30 min | Open the existing MaaS Usage dashboard | Select an `ahead-` subscription and explain actual request/token/quota counters; separate simulator and real-model traffic |

Do not display passwords, API keys, Secret YAML or browser request headers. The scoped OIDC users create keys through the API; native dashboard authentication remains OpenShift OAuth. The existing [Playground](playground.md) and Aurora test drive remain separate customer experiences.

## Preflight and a reproducible smoke test

Download the [standalone Python rehearsal helper](../results/ahead-maas/rehearse.py). It uses the standard library and `oc`, discovers the AHEAD hostname/model, validates HTTPS, refuses redirects, creates only short-lived AHEAD keys, prints no credentials, and revokes its temporary keys. It does not install resources or change subscriptions.

Set `EXPECTED_OPENSHIFT_SERVER` from your approved environment inventory before invoking the helper. Do not derive the expected value blindly from an unverified current context.

```bash
oc whoami
oc get aitenant ahead -n ai-tenants
oc get llminferenceservice,maasmodelref -n ahead
oc get maassubscription,maasauthpolicy -n ai-tenant-ahead
oc get keycloak,keycloakrealmimport,pvc -n ahead

python3 rehearse.py status --expected-server "$EXPECTED_OPENSHIFT_SERVER"
python3 rehearse.py smoke --expected-server "$EXPECTED_OPENSHIFT_SERVER"
python3 rehearse.py quota --recover --expected-server "$EXPECTED_OPENSHIFT_SERVER"
```

The default expected identity is the lab administrator `aiadmin`; override `--expected-user` only for another explicitly authorized identity. A status mismatch makes the helper exit nonzero. `quota --recover` deliberately spends the small free tier and waits 65 seconds before verifying recovery. Keep this separate from a customer's immediate free-tier request. The published helper itself passed its live rehearsal: three free requests consumed 108 simulator tokens, the next returned 429, premium remained 200, free recovered to 200, and both temporary keys were revoked with 200.

| Subscription | Owner | Priority | Budget |
|---|---|---:|---:|
| `ahead-simulator-free` | Lab administrator | 10 | 100 tokens/minute |
| `ahead-simulator-premium` | Lab administrator | 20 | 100,000 tokens/minute |
| `ahead-team-standard` | `ahead-demo-users` | 10 | 200 tokens/minute |
| `ahead-alice-gold` | `alice` | 30 | 5,000 tokens/minute |
| `ahead-bob-throttled` | `bob` | 30 | 20 tokens/minute |

A request can finish beyond the nominal token threshold: completed response usage is accounted for, and the next request is rejected. Issuing a second key did not reset Bob's quota. A consumer selecting a subscription they did not own received **400 `invalid_subscription`**, with no key issued; this build did not return 403 for that API operation.

## Group priority and an individual cap

Both `dual-user` and `capped-user` belong to `quota-standard` and `quota-bulk`. API-key creation without a requested subscription selects the highest-priority applicable tier.

| Subscription | Matches | Priority | Budget |
|---|---|---:|---:|
| `ahead-quota-bulk` | Group `quota-bulk` | 20 | 20,000 tokens/hour |
| `ahead-quota-standard` | Group `quota-standard` | 30 | 10,000 tokens/hour |
| `ahead-quota-individual` | User `capped-user` | 50 | 5,000 tokens/hour |

The real token-accounting rehearsal reached **10,025 tokens then 429** for `dual-user`, and **5,213 tokens then 429** for `capped-user`. These are simulator tokens used to prove quota enforcement, not model throughput or quality measurements. The first two group budgets did not sum to 30,000. A per-user rule wins here because of its higher priority, not merely because it names a user.

```bash
oc get maassubscription -n ai-tenant-ahead \
  ahead-quota-bulk ahead-quota-standard ahead-quota-individual \
  -o 'custom-columns=NAME:.metadata.name,PRIORITY:.spec.priority,LIMIT:.spec.modelRefs[0].tokenRateLimits[0].limit,WINDOW:.spec.modelRefs[0].tokenRateLimits[0].window'
```

The evidence records the initial partial burn and its continuation. Do not repeat the hour-long burn immediately before presenting an interactive request with these same subscriptions.

## Corporate access matrix

All three backends in this scenario are simulators, including the model called “cloud.” Each division gets one subscription spanning its allowed models.

| Division / sample user | General simulator | Code simulator | Cloud simulator |
|---|---|---|---|
| Sales / `sales-1` | 200; 500 tokens/min | 403 | 403 |
| Products / `prod-1` | 200; 500 tokens/min | 200; 500 tokens/min | 403 |
| Engineering / `eng-1` | 200; 500 tokens/min | 200; 1,000 tokens/min | 200, then 429 at 20 tokens/min |

The discovery catalogs contained exactly one, two and three models respectively. When Engineering's cloud budget was exhausted, its code-model request still returned 200. A second Engineering key did not bypass the cloud quota.

Subscriptions are `ahead-corp-sales`, `ahead-corp-products` and `ahead-corp-engineering`. Corresponding authorization policies end in `-access`. OIDC groups are `corp-sales`, `corp-products` and `corp-engineering`; no cluster-wide OAuth provider or user membership was rewritten for this scenario.

## Service accounts and external identity

Two workloads use their service-account tokens directly, with access authorized for the namespace and separate per-workload subscriptions:

| Service account | Subscription | Budget | Observed result |
|---|---|---:|---|
| `batch-scorer` | `ahead-sa-batch-scorer` | 120 tokens/min | 200, including the mounted token in an actual Job |
| `report-writer` | `ahead-sa-report-writer` | 15 tokens/min | 200, then 429 |

```bash
oc get job ahead-service-account-proof -n ahead
oc logs job/ahead-service-account-proof -n ahead
```

The Job prints the simulator response and HTTP status, not its token. It completed successfully. Non-overlapping service-account subscriptions avoid the direct-token ambiguity described by the source guide.

The dedicated Keycloak realm contains `maas-user` in `data-scientists` and `ml-engineers`, and `restricted-user` in `data-scientists`. Both performed OIDC login, discovered their permitted model, obtained an API key and received inference 200. Issued keys can retain the group snapshot from issuance; revoke/reissue keys after membership changes.

### Cached signing keys

The JWKS proof issued fresh JWTs before a temporary outage but did not present them to the gateway. It then restricted only the AHEAD Keycloak HTTP endpoint. Discovery became unreachable from both the administrator's machine and an in-cluster probe. All three previously unseen JWTs still created API keys with **201**, after which the Keycloak network configuration was restored and discovery returned **200**.

An altered JWT was denied with **500 during the IdP outage** and **401 after recovery**. The 500 is a known error-handling limitation of this installed path; it is not reported as a successful 401 test. No key was issued to the altered token. The shared Authorino egress policy was not changed.

### Persistent lab identity

Keycloak's initial ephemeral PostgreSQL was migrated into a dedicated **1Gi gp3 PVC** with a private backup. Before/after counts matched: **2 realms, 14 users and 14 clients**, including administrative records. Three sample identities retained their subject IDs and group memberships. After an additional PostgreSQL rollout, the counts still matched, a fresh OIDC login returned **200**, and an existing API key still inferred with **200**. This validates the tested restart path, not disaster recovery or high availability.

## A real external model

`ahead-claude-sonnet` is a separate Anthropic registration. A bounded request returned **200**, the expected text and **27 total tokens**. The original Claude resource and provider Secret were preserved.

The installed multi-tenant implementation supports external models through the **default tenant only**. This registration therefore uses the existing default gateway with new `ahead-external` / `ahead-external-access` governance; it does not route through the AHEAD tenant gateway. The AHEAD copy of the provider Secret requires `inference.llm-d.ai/ipp-managed=true`. Missing that label caused an initial 500 and was corrected on the copy only.

An external credential is required to repeat this step; the public guide contains none. Use the administrator's private AHEAD rehearsal script and an explicitly selected `ahead-external` subscription. This call uses a real provider and is separate from the corporate cloud simulator.

## Metrics: filter before interpreting

In **Observe & monitor → Dashboard → MaaS Usage**, filter to one of the `ahead-` subscriptions. Use `ahead-external` for real external-model usage; other AHEAD subscriptions in this workshop measure simulator traffic. Aurora's `showroom-load` is the existing real Llama workload. Do not combine these as one performance benchmark.

```promql
sum(istio_requests_total{gateway_name="ahead"})
sum by (subscription) (authorized_hits_total{subscription=~"ahead-.*"})
sum by (subscription) (limited_calls_total{subscription=~"ahead-.*"})
```

The rehearsal observed nonempty gateway, consumption and rate-limit series in the existing Thanos datasource. The native dashboard's summary follows the selected time range while its current chart uses a fixed rolling two-hour expression; their totals can differ. Prometheus sampling/`increase()` can also extrapolate. These counters are not exact per-request Loki billing records.

## Preserved state and deferred extensions

The initial before/after comparison kept the original MaaS tenant/configuration, subscriptions, policies, model references, shared Config, DSC, DSCI and default Gateway specs and UIDs unchanged. Original Llama, scheduler, default gateway and MaaS API pod UIDs were unchanged, with zero additional restarts during that check. Later persistence work touched only AHEAD's identity service and database.

| Deferred option | Why it remains outside the live path | Procedure for a later coordinated window |
|---|---|---|
| Global Loki usage logs | Requires shared MaaS `Config/default.spec.usageLogging`, collectors/storage and generated logging configuration | Prepare dedicated storage, validate operator/version compatibility, preserve current Config, review generated changes, enable in a scheduled window, confirm per-request records and existing demo health |
| Redis for shared Limitador | Changing storage restarts the shared limiter and changes counter continuity for all tenants | Preserve active quota evidence, prepare durable Redis and its Secret, coordinate with load/demo owners, change storage in a scheduled window, test persistence and recovery before resuming load |

Neither option is marked passed or silently enabled. Cleanup removes only owned temporary probes and rehearsal keys; persistent lab resources remain for presentations. Do not run the source guide's broad setup or cleanup scripts against this shared environment.

## Sources and related paths

- [Companion MaaS guide](https://rh-aiservices-bu.github.io/rhoai-maas-guide/modules/main/index.html), source commit `ea53fed1827eb1180a0f36c1255b232a582bf944`.
- [Red Hat OpenShift AI 3.5 MaaS documentation](https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html/govern_llm_access_with_models-as-a-service/index).
- [Aurora MaaS lab](maas.md), [MaaS presentation](../demos/maas.md), [inference benchmarks](benchmark.md), and [validation status](../operations/validation.md).
