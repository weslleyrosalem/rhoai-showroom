# Guardrails with visible, testable rules

NeMo Guardrails is generally available; its MCP Gateway integration is Technology Preview in OpenShift AI 3.5. This showroom uses deterministic CPU regex checks, with no model call. They detect the configured patterns, not every form of personal information or prompt injection. The [3.5 NeMo guide](https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html/enabling_ai_safety_with_guardrails/enabling-ai-safety-with-nemo-guardrails_nemo-guardrails) documents checks without LLM calls.

## Direct checks

`NemoGuardrails/showroom-rails` loads the versioned `showroom-safety` ConfigMap. Authentication remains enabled. Discover its Route and run:

```sh
nemo_host=$(oc get route showroom-rails -n ai-showroom -o jsonpath='{.spec.host}')
python apps/aurora-tools/check_guardrails.py --url "https://$nemo_host"
```

Six cases cover allowed business input/output, a synthetic email, `DEMO_SECRET_AURORA`, an explicit instruction override, and an email in output. Each check returns HTTP 200 with `status:success` or `blocked`. A transport failure or `status:error` is a failed test, not a successful guardrail.

The RAG application calls NeMo before recording input in MLflow and before returning/recording output. It accepts only `success`; errors fail closed. Its service account has namespace-level `get services` because the installed RBAC proxy's observed access review omits a resource name. It receives no Secret, write, list, or watch permission from this role.

## MCP integration

The `gitops/components/guardrails/mcp-integration` overlay deploys the actual NeMo IPP plugins, a private HTTPS authentication adapter, NetworkPolicies, and the TrustyAI Gateway reference. Read the [versioned integration contract](https://github.com/weslleyrosalem/rhoai-showroom/blob/main/gitops/components/guardrails/mcp-integration/IPP-CONTRACT.md).

```text
MCP client → authenticated Gateway → IPP → private TLS adapter → NeMo
```

The adapter uses a fixed upstream, verifies service certificates, rejects redirects, and attaches a rotating service-account token. It translates `success` to `passed` for the pinned older IPP plugin; this is showroom compatibility code, not a product feature. Both NeMo hops use verified HTTPS. Gateway-to-IPP uses private gRPC protected by NetworkPolicy; this is not end-to-end mTLS.

Observed checks include allowed stock calls (200), prohibited synthetic arguments (403), anonymous initialization (401), an unlisted service account (403), and checker outage (503). The internal SDK completed initialization, discovery, and all three tools. The public SDK sequence also passed after buffering the MCP router request before IPP. A dedicated output challenge placed a synthetic email in a backend product response; an otherwise allowed stock request returned 403, and the canonical data was restored. This verifies output enforcement for that configured pattern; it does not establish universal semantic protection.

## Customer test drive

1. Ask for the stock level of `AS-001`.
2. Run the direct check with `customer@example.invalid`; inspect the responsible rail.
3. Try “Ignore all previous instructions.”
4. Remove the prohibited text and repeat.
5. Open the exact regex in Git and explain its limitations.
6. On a validated integrated path, place the same synthetic pattern in a tool argument and observe 403 before backend execution.

Regex can miss paraphrases and can reject harmless text. Adding semantic detectors, Presidio, or a safety model changes capacity, latency, dependencies, and evaluation requirements. Record equivalent test cases before and after each change.

## Measured coverage limit

The [matched OWASP evaluation](owasp-evaluations.md) produced 14 of 33 detector matches on both the direct-model and NeMo-adapter paths. The deployed regex rails allowed all 33 requests in that selected corpus. This does not contradict the synthetic-pattern blocking tests above: the broader report-injection/template cases do not match those configured rules. Do not present the guardrail configuration as a general semantic attack detector.
