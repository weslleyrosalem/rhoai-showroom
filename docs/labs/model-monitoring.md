# Monitor Aurora inventory service levels

**Customer question:** Does an apparently neutral allocation policy still treat Aurora's warehouse demand consistently when a promotion changes the workload?

Use the **AI Showroom — Predictive Monitoring** project (`ai-showroom-monitoring`). This separate project contains a native `TrustyAIService`, its persistent data, and one real OpenVINO Model Server (OVMS) deployment. OpenShift AI 3.5 supports this predictive-model monitoring integration with OVMS; its documentation warns against mixing unsupported model deployments into the same monitoring namespace. The original generative models remain in their own projects. [Red Hat monitoring documentation](https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html/monitoring_your_ai_systems/configuring-trustyai_monitor).

## The business scenario

The deployed **Aurora inventory — expedited review policy** is a transparent ONNX classifier. It returns `1` when seven-day demand exceeds available stock. That result requests expedited human review; it never creates an order. Warehouse zone has zero weight in the graph. This is a deterministic demonstration model, not the learned Ray demand forecast or a production allocation recommendation.

Each test sends 100 real OVMS predictions, with 50 East and 50 West warehouse observations. Normal inventory produces the same expedited-review rate in both groups. In the promotion scenario, only East demand increases by 60 units. The native KServe agent captures the actual requests and responses over verified TLS; TrustyAI computes the metrics from those records.

A change in group outcome rates shows a service-level disparity in this synthetic workload. It does not establish causal discrimination, legal fairness, a model-quality guarantee, or a reason to equalize decisions despite different operational needs. Inspect the changed demand and inventory conditions before deciding what action is appropriate.

## Native screens and test drive

1. Open **Projects → AI Showroom — Predictive Monitoring → Settings** and inspect the configured **TrustyAI service**.
2. Inspect the project's OVMS model deployment. Explain its three inputs: warehouse zone, seven-day demand, and available units; its output is expedited review.
3. In the Aurora Workbench terminal, use the published repository helper to send a normal batch, then a promotion batch. Inspect the returned group rates, actual inference count, capture confirmation, and TrustyAI results.
4. Inspect the scheduled metrics and their history. Statistical parity difference (SPD) is a difference in outcome proportions; disparate impact ratio (DIR) is a ratio. Their neutral references are `0` and `1`, respectively. For this request, SPD is West minus East and DIR is West divided by East. The installed service's generated prose reverses its group labels; use the observed rates and arithmetic below.
5. Restore the normal batch after discussing the effect. This changes the last 100 observations without deleting the history.

```bash
python scripts/trustyai_metrics.py baseline --schedule
python scripts/trustyai_metrics.py promotion
python scripts/trustyai_metrics.py baseline
```

From a laptop, also pass `--expected-server` and `--expected-user` for every mutating phase. The helper verifies the target model ownership before forwarding the current token. In the Workbench, the mounted cluster identity and fixed showroom model are used directly.

The first setup requires a reference batch before those steps:

```bash
python scripts/trustyai_metrics.py reference
```

Run `reference` once per new dataset. The script preserves the actual OVMS predictions in a named `AURORA_REFERENCE` dataset. Repeated calls append observations; they do not erase history. Run these batches exclusively; concurrent traffic to the same model can satisfy an aggregate count check. The helper waits for 100 additional captured observations before calculating the current batch. A capture timeout stops the demonstration rather than displaying stale metrics.

MeanShift compares the current numeric distribution with that reference. A low p-value is evidence against its no-shift hypothesis under the test's assumptions, **not** the probability that the model is unsafe or that the hypothesis is true. The deliberately simple, partly discrete synthetic fixture is useful for demonstrating a controlled change; use distribution-appropriate tests and representative reference data for real monitoring.

## Measured results

The actual September 22, 2026 acceptance run produced:

| Scenario | East expedited review | West expedited review | SPD, West − East | DIR, West / East | Demand MeanShift p-value |
|---|---:|---:|---:|---:|---:|
| Normal inventory | 60% | 60% | 0.00 | 1.0000 | 1.0 |
| East promotion | 90% | 60% | −0.30 | 0.6667 | 6.445 × 10⁻⁹ |

Fairness metrics use the latest 100 captured predictions. The reported drift comparison uses all 300 recorded unlabeled inferences against 100 fixed reference observations, so its window is intentionally different. Stock and warehouse-zone distributions remained unchanged, both with p = 1.0. A new batch changes these cumulative results. The installed PVC implementation's bounded tag-filtered drift request initially selected older records; the helper explicitly requests the full observed dataset for the reported cumulative comparison. The scheduled drift series uses the latest 100 rows (observed promotion demand p = 0 at reported numeric precision); the one-time API result uses cumulative history. They therefore use different windows; label the chart's window when presenting it.

The native `outsideBounds` field for MeanShift was also true for the unchanged baseline. Read the per-column p-values and documented test assumptions; do not present that aggregate flag as an accurate overall alarm for this fixture.

## Deployment and TLS prerequisite

The resource manifest is `gitops/components/science/trustyai.yaml`. Apply it first: it includes the isolated namespace, official pinned OVMS runtime, checked ONNX artifact, TrustyAI service with a 1 GiB PVC, scrape service account, and scoped network policies. The guarded helper below creates the controller-populated scrape token Secret outside Git; the Argo project intentionally prohibits managing Secrets. Regenerate the model with `onnx==1.19.1` and `python data/trustyai/generate.py`; update the ConfigMap artifact if changing the graph.

The documented KServe logger prerequisite adds its service CA bundle and enables certificate verification. Review the current cluster and pass its independently verified identity to the guarded helper:

```bash
python scripts/configure_trustyai.py \
  --expected-server '<verified Kubernetes API URL>' \
  --expected-user '<verified oc identity>' \
  --backup '<new private path outside this repository>' \
  --apply
```

This preserves the existing logger image and resources. It adds `opendatahub.io/managed: 'false'` to the shared `inferenceservice-config` ConfigMap because otherwise the operator restores its defaults. The helper saves an exclusive mode-0600 prepatch backup outside Git and tests the resource version before changing anything. The opt-out affects the **whole shared ConfigMap**, not only its logger field. No other operator or DSC reconciliation is disabled. Review that ConfigMap during upgrades so new operator defaults are not silently missed. To roll back, compare the private backup with the current ConfigMap, restore only these owned logger fields and the previous management annotation, and re-enable reconciliation deliberately. Do not blindly replace unrelated changes from a newer snapshot. The helper never restarts a model. When enabling capture on an existing monitored deployment, recreate only its predictor pod after the prerequisite is in place. [Primary TrustyAI installation example](https://github.com/trustyai-explainability/odh-trustyai-demos/blob/main/1-Installation/README.md).

## Access and limits

The model has no public Route and requires native KServe authorization on port 8443. Network policies prevent the Workbench from reaching raw OVMS, logger, or TrustyAI backend ports. The showroom policy permits only its OVMS predictor to deliver events to the internal TLS capture port. The native operator also creates a policy for local InferenceService pods and monitoring namespaces; Kubernetes adds these permissions together. The effective native policy allows monitoring namespaces to scrape the internal HTTP metrics endpoint and exposes port 8443 through its authenticated proxy. Our policy cannot override those operator allowances. The native TrustyAI API uses a coarse `get services` permission check for its API, including write operations: project participants permitted to use it can also upload demo data and schedule metrics. This is **not** an application-level read-only permission. Keep this project limited to the synthetic exercise.

The installed capture parser rejects the optional KServe request `id` field, so the helper omits it. The fixture uses FP64 inputs: FP32 group values exposed a numeric-equality issue in the installed fairness implementation, yielding `NaN`; those setup-probe results are not valid fairness measurements. The checked fixture avoids that mismatch. Do not silently replace a non-finite result with zero.

The secure metrics monitors use a dedicated service account with only the permissions needed by the native model and TrustyAI proxies. Its controller-populated service-account token Secret follows the installed KServe monitor convention; its value is never in Git. The OVMS policy permits only the exact user-workload Prometheus pods for its authenticated scrape. TrustyAI also retains the operator policy described above; its authentication remains mandatory on 8443.

The service data is persistent. Validate scheduled requests after a service restart, and rerun `baseline --schedule` if required. Evaluation results in EvalHub and NeMo guardrail decisions remain separate from these model-monitoring metrics.

The native **Model bias** charts were inspected after secure collection was enabled: both named series show the baseline and promotion transitions, with their configured reference bounds. Select a one-hour window for a fresh rehearsal, or a longer window containing the recorded run.

The installed endpoint-performance template expects a legacy resource-limit metric. The optional [compatibility rule](https://github.com/weslleyrosalem/rhoai-showroom/tree/main/gitops/components/platform/telemetry) supplies only the actual limits for this model so its CPU and memory panels work. The template also labels its microsecond latency query as milliseconds. This remains a product-template limitation: do not read that panel's value as milliseconds. The controller regenerates the dashboard, so the showroom preserves its ownership rather than applying a temporary patch that would disappear.
