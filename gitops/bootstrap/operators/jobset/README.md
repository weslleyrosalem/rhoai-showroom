# JobSet prerequisite for native Trainer jobs

OpenShift AI 3.5 Trainer requires JobSet. This isolated bootstrap installs the
official Red Hat `job-set` package, channel `stable-v1.0`, exact CSV
`jobset-operator.v1.0.0`, in `openshift-jobset-operator`. The package's three image
digests are recorded in `pin.json`. It requires an existing cert-manager
installation. It does not install or enable Kueue or the legacy Training Operator.

Review [OpenShift 4.22 JobSet installation](https://docs.redhat.com/en/documentation/openshift_container_platform/4.22/html/ai_workloads/jobset-operator)
and [OpenShift AI 3.5 distributed-workload prerequisites](https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html/installing_and_uninstalling_openshift_ai_self-managed/installing-the-distributed-workloads-components_install)
for the target environment. This is an explicit shared-platform operation,
outside automatic Argo synchronization. A new catalog head or different package
image stops the helper for review rather than silently upgrading the pin.

Use independently recorded `SHOWROOM_SERVER` and `SHOWROOM_USER` values. Every
helper action prints a plan unless `--apply` is supplied:

```bash
python3 gitops/bootstrap/operators/jobset/install.py subscription \
  --expected-server "$SHOWROOM_SERVER" --expected-user "$SHOWROOM_USER"
```

Add `--apply` after reviewing the plan. The helper creates a single-namespace
OperatorGroup and a **Manual** Subscription. It rejects conflicting unowned
resources. Inspect the referenced InstallPlan before approving its exact name:

```bash
oc get subscription job-set -n openshift-jobset-operator \
  -o jsonpath='{.status.installPlanRef.name}{"\n"}'
oc get installplan REVIEWED_PLAN -n openshift-jobset-operator -o yaml
python3 gitops/bootstrap/operators/jobset/install.py approve \
  --expected-server "$SHOWROOM_SERVER" --expected-user "$SHOWROOM_USER" \
  --install-plan REVIEWED_PLAN --apply
```

Approval is refused if the plan contains another CSV or a different catalog.
Wait for the pinned CSV to report `Succeeded`, then create the documented
`JobSetOperator/cluster` operand:

```bash
oc get csv jobset-operator.v1.0.0 -n openshift-jobset-operator
python3 gitops/bootstrap/operators/jobset/install.py operand \
  --expected-server "$SHOWROOM_SERVER" --expected-user "$SHOWROOM_USER" --apply
oc get jobsetoperator cluster
oc get pods -n openshift-jobset-operator
```

After the operand is Available and the JobSet CRD is Established, enable Trainer:

```bash
python3 gitops/bootstrap/operators/jobset/install.py trainer \
  --expected-server "$SHOWROOM_SERVER" --expected-user "$SHOWROOM_USER" \
  --backup /private/showroom/dsc-before-trainer.json --apply
oc get trainjobs.trainer.kubeflow.org -n ai-showroom
oc get clustertrainingruntimes.trainer.kubeflow.org
```

The backup must be a new private file outside the public repository. The helper
uses an optimistic JSON patch of only
`spec.components.trainer.managementState`. It preserves Kueue, Training Operator,
and every other DSC field. Keep the backup for a targeted rollback; never replace
the entire live DSC with an old snapshot. Enabling an API is not evidence of a
completed native training job. Validate a bounded CPU job and the native Jobs
page separately, with its actual runtime, workers, completion state, and artifacts.
