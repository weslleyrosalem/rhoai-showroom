# GitOps and portability

The repository defines desired state. Argo CD reconciles stable services. Ray jobs, benchmarks, credentials, and cloud expansion have explicit actions and their own evidence.

## Responsibilities

| Layer | Owner | Control |
|---|---|---|
| ROSA pools and physical GPUs | Cloud administrator | OCM/ROSA, maxima, surge, and AWS quotas |
| Operators, DSC, and bootstrap | Platform administrator | Pinned releases, partial patches, reviewed installation |
| Aurora services | Argo CD | Portable or existing-cluster overlay |
| Credentials | Kubernetes or secret manager | Outside Git, expiration, and rotation |
| Experiments | Authorized participant | Explicit jobs/runs, artifacts, and reset steps |

## Application configuration

`gitops/argocd/project.yaml` restricts the repository and destination namespaces. `application.yaml` uses server-side apply, self-heal, and **prune disabled**. It has no cascading deletion finalizer, reducing the risk of removing persistent data or shared services during a demonstration.

The controller requires `gitops/bootstrap/argocd-rbac.yaml`. The `argocd.argoproj.io/managed-by: openshift-gitops` namespace label establishes standard project access; additional roles cover required custom resources. Shared-namespace access is limited to necessary resource types. Participants do not receive cluster-admin.

```bash
oc apply -f gitops/bootstrap/argocd-rbac.yaml
oc apply -f gitops/argocd/project.yaml
# Before applying, choose portable or existing-cluster in spec.source.path.
oc apply -f gitops/argocd/application.yaml
oc get applications.argoproj.io rhoai-showroom -n openshift-gitops
```

To reuse a model, select `gitops/overlays/existing-cluster` and edit its model references before the first sync. A fork must update `repoURL` and `sourceRepos`. Pin `targetRevision` to a release commit for repeatable presentations.

Cluster-specific MCP audience settings belong in a local overlay or configuration manager. Discover TokenReview audiences from the intended API server. The Application ignores only that runtime-specific leaf and uses `RespectIgnoreDifferences=true`. Secrets are excluded from the showroom AppProject.

## Reconciliation test drive

1. Show Synced/Healthy, the source commit, and the application's resources.
2. Commit a harmless demonstration annotation or value in a showroom-owned ConfigMap.
3. Watch the new revision synchronize.
4. Change that managed value temporarily in the console and observe OutOfSync and self-heal.
5. Revert the exercise commit to restore the documented state.

Do not use an operator upgrade, namespace deletion, credential change, or MIG repartitioning as a drift exercise. With `prune: false`, removing a YAML file does not delete its live resource.

## Automation boundaries

Argo does not provision ROSA pools. ResourceQuota limits Kubernetes requests, not physical GPU count. The capacity guard needs a cloud inventory and counts transient nodes. Global DSC, catalog, and ingress settings use partial patches or merges that preserve existing resources. Never export the entire cluster into a public repository.

## Publish the guide

Build with `mkdocs build --strict` and publish the generated site on `gh-pages`. The template `ci/pages.workflow.yaml` supports GitHub Actions; copy it to `.github/workflows/pages.yaml` using a credential authorized to manage workflows. The initial publication used branch-based Pages because the available credential lacked that scope.
