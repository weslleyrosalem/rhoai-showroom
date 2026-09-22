# Model onboarding: from candidate to governed service

**Status:** the curated catalog is available. Registry onboarding and the complete promotion rehearsal are being validated. Candidate registration does not mean a model has passed evaluation or is approved for customer use.

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
