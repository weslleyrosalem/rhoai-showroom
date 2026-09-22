# Native model registry onboarding

The showroom registry is `aurora-registry` in `rhoai-model-registries`. It stores model metadata and immutable artifact locations. It does not copy weights or approve a model for use.

The cluster-scoped resource `modelregistries.components.platform.opendatahub.io/default-modelregistry` represents the enabled platform component. It is **not** a namespaced registry instance. Always use the fully qualified resource `modelregistries.modelregistry.opendatahub.io` when listing actual registries.

## Prerequisites

- OpenShift AI 3.5.1 with the model registry component enabled and its native operator available.
- The three showroom groups already exist. The editor binding grants registry access to `showroom-platform-admins` and `showroom-data-scientists`. Visitors receive no registry editing grant. This native registry role authorizes registry API access; it is not a read-only metadata role.
- A default storage class with at least 5Gi available for the generated PostgreSQL PVC.
- The current `oc` identity can create the dedicated instance and access its authenticated Route.

The operator-generated PostgreSQL option is supported for evaluation, development, and testing only. Production requires an external supported database with an appropriate TLS, backup, and recovery policy. Deleting a registry can remove its operator-owned resources. The CR has `Prune=false`; do not delete it or its PVC as part of a demo reset. Export required metadata and back up the database before removal or migration.

## Create and register a candidate

First inspect the target cluster and existing instances. Do not overwrite an existing same-name registry with different configuration.

```bash
oc whoami
oc whoami --show-server
oc get modelregistries.modelregistry.opendatahub.io -A
oc apply --dry-run=server -k gitops/components/models/registry
# Review the rendered configuration and target context before the write.
oc apply --server-side --field-manager=rhoai-showroom-platform \
  -k gitops/components/models/registry
oc wait --for=condition=Available \
  modelregistries.modelregistry.opendatahub.io/aurora-registry \
  -n rhoai-model-registries --timeout=180s
```

The helper defaults to a read-only PLAN. Supply the server and user you intentionally selected; do not fill them automatically from the current context.

```bash
python3 gitops/components/models/register_model.py \
  --expected-server https://api.YOUR-CLUSTER:443 \
  --expected-user YOUR-ADMIN
# After reviewing the plan, repeat with --apply.
```

The example `qwen-4b-candidate.json` pins the Hugging Face revision, Apache 2.0 license metadata, runtime image digest, hardware profile, catalog source, and deployment manifest. Model, version, and artifact records are linked through the native registry API. The helper uses the current `oc` token in memory and discovers the registry-owned HTTPS Route. It verifies TLS, rejects redirects, and never logs the token or an API error body.

A repeated apply preserves matching records. Same-name entries without the showroom ownership property or with different immutable provenance are rejected. Later evaluation state is preserved; this helper never promotes, resets, updates, or deletes existing records. An interrupted multi-step run can be resumed safely. A schema or connectivity failure can leave a partial registration; rerunning fills absent linked entries after validating those already present.

`candidate` is a custom lifecycle value. Native resource visibility does not mean that safety, runtime compatibility, or performance has been approved. All three validation properties start at `NOT_RUN`. Attach real evidence and use a separately reviewed promotion workflow after execution. Registration itself does not start GPU workloads.

## Add another model

Copy the JSON example and choose unique model, version, and artifact names. Verify the model license and access requirements. Pin a full 40-character Hugging Face commit and an exact runtime image digest. Keep the immutable URI consistent with that model and revision. Add the corresponding catalog allowlist entry, hardware profile, deployment manifest, and lock entry through their own reviewed workflows. Run the helper with `--candidate path/to/new-candidate.json`; do not reuse the Qwen example's identifiers for unrelated weights.

## Verified on the showroom cluster

On September 22, 2026, the native registry became Available with a Bound 5Gi PostgreSQL PVC. Qwen3-4B registration created one registered model, one version, and one artifact; an immediate second apply preserved all three IDs. This is registry onboarding evidence only. It does not establish GPU inference, safety, or benchmark readiness.

## Sources

- [Red Hat OpenShift AI 3.5: managing model registries](https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/managing_model_registries/)
- [Model registry operator and authenticated access](https://github.com/opendatahub-io/model-registry-operator)
- [Official default PostgreSQL sample](https://github.com/opendatahub-io/model-registry-operator/blob/main/config/samples/postgres-auto/modelregistry_v1beta1_modelregistry.yaml)
- [OpenShift AI 3.5 native registry OpenAPI contract](https://github.com/opendatahub-io/model-registry/blob/rhoai-3.5/api/openapi/model-registry.yaml)
- [Qwen3-4B model card](https://huggingface.co/Qwen/Qwen3-4B-Instruct-2507)

The access rehearsal also verified 401 without a token, 403 with an unbound short-lived ServiceAccount token, and 200 after granting the exact generated registry role. SubjectAccessReview separately verified the data scientist group grant and visitor denial. Temporary probe resources were removed. A direct pod-IP connection to REST port 8080 from the RAG pod timed out while the Route TCP control succeeded. Authorization caches can delay a newly granted role during a before/after test.
