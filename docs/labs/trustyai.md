# TrustyAI: controls and evaluation

The Aurora security journey uses the TrustyAI-managed NeMo Guardrails and EvalHub components. They connect explicit content policies with repeatable evaluation evidence. The installed operator, each service, and the results of the complete application must be checked separately.

| Showroom component | What to demonstrate | Current acceptance evidence |
|---|---|---|
| NeMo Guardrails | Allow a normal question; reject defined synthetic email, secret, or override cases | Direct input/output checks passed |
| MCP processing integration | Protect actual tool calls and results | Authorized calls passed; unsafe input/output blocked; checker outage failed closed |
| EvalHub | Submit, inspect, and export an evaluation | Real Garak run and exported result JSON |
| Garak | Explain the probe, observed attack success, and limitations | The unguarded model failed the executed quick benchmark |
| MLflow | Preserve runs, metrics, artifacts, and traces | Real artifacts and span data retrieved |

## Check the platform and the result

```bash
oc get datascienceclusters -o yaml
oc get nemoguardrails.trustyai.opendatahub.io -n ai-showroom
oc get evalhubs.trustyai.opendatahub.io -n redhat-ods-applications
```

Inspect the TrustyAI component's `managementState` and the service conditions. This reference configuration uses `mcpGuardrailsMode: false`, which allows EvalHub alongside NeMo in the tested release. Bootstrap stops if a different shared setting exists; review current consumers before adopting this configuration.

Then execute the [guardrail checks](guardrails.md) and inspect the [evaluation](evaluation.md) and [model-score](model-score.md) records. A Ready operator does not establish model quality or policy coverage. NeMo's demonstration regex rules are explicit examples, not a claim to stop every prompt injection or detect every kind of sensitive data.

## Broader TrustyAI capabilities

A standalone `TrustyAIService` for predictive-model fairness, explainability, or drift is a separate deployment and evaluation path. This showroom has not validated that path yet. Do not label the forecast accuracy metrics or GenAI guardrail results as a fairness or drift assessment.

The [OpenShift AI 3.5 evaluation documentation](https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html/evaluating_ai_systems/index) describes the native evaluation workflow. Use the [validation record](../operations/validation.md) to decide which sections are ready for a live demonstration.
