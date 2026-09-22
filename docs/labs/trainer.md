# Train Aurora demand models in native Jobs

**Business question:** Can a machine learning engineer distribute training across two CPU workers and compare the result with the accepted baseline before promotion?

This lab uses the native Kubeflow Trainer `TrainJob` API, the operator-provided `torch-distributed-cpu` runtime, and JobSet. It is distinct from the [Ray training lab](ray.md). Open **Develop & train → Jobs** and select `aurora-demand-ddp`, labeled **Aurora demand — two-worker CPU training**.

The public script fits a small PyTorch demand regressor with genuine DistributedDataParallel gradient synchronization over Gloo. It uses product identity, weekday, promotion, and calendar position from the same synthetic Aurora dataset. Two pods run one process each, with a limit of one CPU and 2 GiB per pod. The last 28 days are held out before fitting. A seasonal-naive baseline repeats the final training week's observations; no holdout values are used to fit either model.

## Run and inspect

Prerequisites: the official JobSet operator and native Trainer component are Ready; the `torch-distributed-cpu` runtime exists. The showroom bootstrap installs those prerequisites. This lab does not enable Kueue or the legacy Training Operator.

```bash
oc create configmap aurora-trainer-source -n ai-showroom \
  --from-file=train.py=notebooks/train_distributed.py \
  --from-file=demand.csv=data/demand.csv --dry-run=client -o yaml | oc apply -f -
oc apply -f gitops/components/science/trainjob.yaml
oc get trainjob aurora-demand-ddp -n ai-showroom
oc get pods -n ai-showroom -l jobset.sigs.k8s.io/jobset-name=aurora-demand-ddp
```

Inspect the two pods' logs in the native Jobs details. Each prints its rank, pod name, world size, and training-row count. Rank zero prints the measured holdout MAE, baseline MAE, and `beats_baseline` result. A completed infrastructure job is not automatically a better model.

## Test drive and decision

Keep the recorded baseline run. For a new exercise, create a new named TrainJob from the manifest, change the epoch count in a separately named source ConfigMap, and compare measured holdout MAE. Do not overwrite the accepted Ray forecast used by MCP tools. A candidate must satisfy the quality gate and be explicitly promoted before the replenishment recommendation changes.

The job is intentionally excluded from continuous GitOps reconciliation: training is an explicit action and should not restart on every sync. Its completed record remains available for the native Jobs UI. No GPU or LLM inference is required.

Source: [Kubeflow Trainer ML policy](https://trainer.kubeflow.org/en/latest/operator-guides/ml-policy.html), [Red Hat OpenShift AI installation prerequisites](https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html/installing_and_uninstalling_openshift_ai_self-managed/installing-and-deploying-openshift-ai_install).

## Measured result

The September 22, 2026 run completed on two distinct cluster workers. It trained on **2,696 rows** through December 3 and evaluated **224 rows** from December 4–31. Holdout MAE was **0.82070 units**, compared with **1.33036 units** for the fixed seasonal-naive baseline. The two ranks each trained on 1,348 rows and synchronized gradients for 120 epochs.

The portable manifest requests two pods but does not force separate physical nodes on a smaller cluster. Inspect `spec.nodeName` before making a multi-node claim. The model's MAE is not directly comparable to the native AutoML leaderboard: that experiment uses a different evaluation protocol. This run demonstrates distributed training and a measured baseline gate, not a universally superior model.

MLflow experiment `aurora-native-distributed-training` retains run `21fc3b8a47494f5abd5ad8594e56eef6`, its parameters, both error metrics, source script, and `training/result.json`. Export a subsequent run's actual final JSON log object from the workbench with:

```bash
python scripts/science.py trainer-export --result /path/to/training-result.json
```

This is an explicit export of measured results. It is not automatic Trainer instrumentation, and it does not register or deploy the candidate.

The native Jobs browser rehearsal confirmed the completed job, two workers, per-worker resources, both pods, and measured log output. The Details view currently leaves instrumented epoch/progress fields blank because this script does not emit the Trainer progress protocol. Show the actual logs and MLflow record; do not infer a progress metric from job completion.
