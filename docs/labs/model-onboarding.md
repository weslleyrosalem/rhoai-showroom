# Model onboarding: from candidate to governed service

**Status:** the curated catalog and native registry candidate onboarding are verified. GPU deployment and the complete promotion rehearsal remain separate validation gates. Candidate registration does not mean a model has passed evaluation or is approved for customer use.

Use the Aurora replenishment assistant as the acceptance scenario. Start with `Qwen/Qwen3-4B-Instruct-2507`, pinned to the revision in `gitops/components/models/models.lock.json`. Its initial role is a candidate alternative to the existing demonstration model.

## Follow one version through the process

| Stage | Action | Evidence required before moving on |
|---|---|---|
| Discover | Select the model from the curated catalog | Provider, license, architecture, immutable revision, and intended task |
| Assess fit | Select a hardware profile and context limit | Memory estimate, supported runtime, physical GPU capacity check |
| Register | Create a candidate model version in the model registry | Registry ID, version ID, source URI, and owner |
| Deploy for evaluation | Use the isolated showroom serving manifest | Ready model and a real authenticated response |
| Score quality | Evaluate Aurora questions and relevant public benchmarks | Dataset revision, evaluator version, sampling settings, score direction, sample count, and raw result |
| Test safety | Run EvalHub/Garak and the explicit NeMo/MCP cases | Per-benchmark outcome, allowed and blocked cases, and documented failures |
| Measure performance | Run the controlled serving benchmark | Same model/tokenizer, hardware, context, concurrency, errors, TTFT, and throughput |
| Review | Review the evidence and intended deployment in Git | Named reviewer, decision, limitations, and rollback version |
| Promote | Synchronize an approved manifest and expose it through MaaS | Argo revision, model readiness, subscription, quota, and access tests |
| Observe | Run the complete Aurora question | Sources, tools, trace, model identity, usage, and evaluation evidence |
| Revisit | Repeat gates after changing weights, quantization, runtime, or prompt | New version and fresh evidence for the changed configuration |

The stages and review policy above are this showroom's process. They are not an assertion that the dashboard automatically enforces every gate.

## What a model score means

Catalog benchmark results help select a candidate under the benchmark's documented conditions. They do not measure the current cluster. Custom Hugging Face entries do not automatically become Red Hat-validated models or gain performance scores.

Keep three records distinct: catalog performance data, task-quality/safety evaluations, and measurements from this installation. Never turn a missing score into zero or an evaluation job's completion into a safety pass. A failed Garak probe remains a failed probe even when the evaluation job completed successfully.

For Aurora, check that inventory and prices match tool results, policy claims cite the right document, forecast dates are disclosed, approval thresholds are respected, and no order is created. Include unanswerable questions and attempts to override the purchasing boundary.

## Visitor interaction

Choose a second candidate or quantization variant and explain which evidence must be repeated. Compare the candidate's registry metadata with its serving configuration. Let the visitor identify one missing gate and keep the version in candidate state until that evidence exists.

A failed or incomplete candidate stays available for analysis without replacing the working demonstration model. Revert the showroom deployment manifest to a previously tested revision to recover the presentation.

## Native platform foundations

The catalog supports discovery and comparison; the model registry holds versioned metadata for the model lifecycle. Follow the [OpenShift AI 3.5 registry overview](https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html/working_with_model_registries/overview-of-model-registries_working-model-registry) and [catalog workflow](https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html/working_with_the_model_catalog/index).

Continue with [model catalog](model-catalog.md), [evaluations](evaluation.md), [red teaming](red-teaming.md), [benchmarking](benchmark.md), and [MaaS](maas.md).


## Rehearse the verified native registration

Open **Settings → Model resources and operations → Model registry settings** and select **Aurora Supply Model Registry** (`aurora-registry`, namespace `rhoai-model-registries`). The cluster-scoped `default-modelregistry` resource is the enabled component; it is not the namespaced registry instance.

The September 22, 2026 rehearsal registered these linked native records:

| Record | Name | Registry-local ID |
|---|---|---|
| Registered model | Aurora Supply - Qwen3-4B | 1 |
| Model version | instruct-2507-cdbee75f | 2 |
| Model artifact | aurora-qwen-4b-cdbee75f | 1 |

The artifact location is `hf://Qwen/Qwen3-4B-Instruct-2507:cdbee75f17c01a7cc42f958dc650907174af0554`. Version metadata includes the runtime image digest, Apache 2.0 license, catalog source, hardware profile, and deployment manifest. Its lifecycle remains `candidate`. The September 22 runtime recorder later measured native inference, structured tool calling, and endpoint-picker processing, updating runtime status to `PASSED_PROTOCOL_TOOL_AND_ROUTING`. Safety and performance remain `NOT_RUN`; fresh registrations still initialize all checks as `NOT_RUN`. IDs are local to this registry and can differ on a fresh installation.

Run the read-only onboarding plan from the repository root. Replace the guarded server and identity with values that you have intentionally selected.

```bash
oc get modelregistries.modelregistry.opendatahub.io -A
python3 gitops/components/models/register_model.py \
  --expected-server https://api.YOUR-CLUSTER:443 \
  --expected-user YOUR-ADMIN
```

On a fresh cluster, create the dedicated instance using the [registry prerequisites and manifests](https://github.com/weslleyrosalem/rhoai-showroom/blob/main/gitops/components/models/registry/README.md). After reviewing the helper plan, repeat the command with `--apply` to create absent metadata records. On the current showroom, the repeated apply preserved all three IDs. It did not duplicate the version, reset lifecycle evidence, download weights, or start a GPU deployment.

For a test drive, open the version's properties and ask the visitor to find the immutable weight revision, hardware target, and three missing validation gates. Then run the helper without `--apply` and explain the `preserved` actions. A second candidate can be prepared by copying the [candidate example](https://github.com/weslleyrosalem/rhoai-showroom/blob/main/gitops/components/models/registry/qwen-4b-candidate.json) with unique names and verified pins. Registering it is an explicit write; it still does not promote it.

The registry is protected by kube-rbac-proxy with verified TLS. The generated registry role is granted to showroom platform administrators and data scientists. Visitors are not granted editing access. The demo PostgreSQL database has a Bound 5Gi persistent volume. Preserve the registry and its database during resets; the generated database is intended for nonproduction use.

The access rehearsal returned **401** without a token, **403** for an unbound short-lived ServiceAccount token, and **200** for the same identity after granting the generated registry role. Separate SubjectAccessReviews confirmed the data scientist group grant and visitor denial. This tests group authorization and equivalent-role API access; it does not claim a separate human login was exercised. The temporary ServiceAccount and binding were deleted after the test. Allow for the authorization cache to expire when testing a newly granted role.

A direct TCP connection from the RAG pod to the registry pod's REST port 8080 timed out while the authenticated Route's port 443 remained reachable. The backend cannot be used from that application pod to bypass the registry proxy. This is a scoped network test, not a claim about cluster-administrator port forwarding or every possible source namespace.


## Update the runtime evidence after testing

After the native Qwen deployment is Ready, the separate runtime recorder can measure one bounded automatic tool call and its endpoint-picker counter, then attach the report hash and timestamp to the owned registry version. It checks the live pinned model URI, requested runtime digest, and resolved container digest. The latter can differ for an OCI platform image; both are retained in the report.

```bash
python3 gitops/components/models/record_runtime.py \
  --expected-server "$SHOWROOM_SERVER" --expected-user "$SHOWROOM_USER" \
  --evidence /private/directory/qwen-runtime-NEW-DATE.json
# Review the PLAN, then repeat with --apply.
```

Expected identity values must come from the independently approved environment record. The report path must be new and outside the repository. PLAN is read-only; APPLY performs a native-auth request for `get_stock({"sku":"AS-001"})`, verifies a successful structured response and picker activity, writes the private report, and updates runtime evidence only. It preserves candidate lifecycle, immutable provenance, safety status, and performance status. A failed runtime check never updates the registry. Existing failures must not be replaced with a green overall score.

Use a single editor window for this version. The helper re-reads metadata immediately before the PATCH and aborts if it changed during measurement; the registry API does not provide a Kubernetes resourceVersion compare-and-swap transaction. Keep concurrent promotion/evaluation writers paused for this short update.

On September 22, 2026, version 2 recorded `PASSED_PROTOCOL_TOOL_AND_ROUTING` with a timestamp and SHA-256 evidence reference. Its lifecycle remained `candidate`; safety and performance remained `NOT_RUN`. Fresh registrations still initialize all three checks as `NOT_RUN`. This is acceptance of the native serving protocol, not model quality, a benchmark result, or promotion.
