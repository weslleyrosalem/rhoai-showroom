# Connect a registered candidate to its existing deployment

Aurora Supply already serves the pinned Qwen3 4B candidate through llm-d. The native model registry should show that deployment when the presenter opens its version. An empty **Deployments** table can mean the registry association is missing; it does not establish that the model is undeployed.

The helper below checks the running deployment against the registered immutable artifact and then adds the same metadata used by the native deployment flow. It discovers cluster-specific registry IDs at runtime. It never deploys or restarts Qwen, edits the serving specification, registers another artifact, promotes the candidate, or assigns an evaluation score.

## Presenter action

1. Open **AI hub → Models → Registry → aurora-registry → Aurora Supply - Qwen3-4B**.
2. Select version **instruct-2507-cdbee75f**, then **Deployments**.
3. Find **Aurora Qwen — tools and policy knowledge** in project **AI Showroom** (`ai-showroom`). Open the existing deployment and compare its pinned model revision with the registry artifact.
4. Explain the boundary: this link identifies which artifact is running. Runtime compatibility, safety, model quality, and performance are separate evidence gates. The version remains a **candidate**.

The version table selects deployments by registered-model ID and version ID, then filters by registry name. OpenShift AI's llm-d watcher participates in that inventory. This is a metadata association with a deployment that already exists, not proof that the registry originally created it. The installed UI retains an “initiated from model registry” information banner even in the populated table. That generic wording does not establish how this existing deployment was originally created. [Native association metadata](https://github.com/opendatahub-io/odh-dashboard/blob/4fdc824a5ff91fc2069ceb35130b2338499e2c5f/packages/model-serving/modelRegistry/utils/deployUtils.ts), [version deployment filters](https://github.com/opendatahub-io/odh-dashboard/blob/4fdc824a5ff91fc2069ceb35130b2338499e2c5f/packages/model-serving/modelRegistry/VersionDeploymentsTab.tsx), [llm-d inventory extension](https://github.com/opendatahub-io/odh-dashboard/blob/4fdc824a5ff91fc2069ceb35130b2338499e2c5f/packages/llmd-serving/extensions/extensions.ts).

## Reproduce the association

Run from the repository root with an identity permitted to read the registry and patch the showroom's `LLMInferenceService`. Supply the independently verified intended cluster and user; do not derive the expected values automatically from the active context.

```bash
python3 gitops/components/models/link_registry_deployment.py \
  --expected-server 'https://api.YOUR-CLUSTER:6443' \
  --expected-user 'YOUR-APPROVED-USER'
```

The default **PLAN** only reads. It validates the registry's owned, authenticated TLS Route; the candidate's provenance; an exact immutable artifact URI match; showroom ownership; and Ready model and scheduler pods. It refuses a conflicting existing registry association. Missing registry entries must be created with the separate onboarding workflow first.

After reviewing the plan, use the same explicit identity guards and a new private evidence path outside this repository:

```bash
python3 gitops/components/models/link_registry_deployment.py \
  --expected-server 'https://api.YOUR-CLUSTER:6443' \
  --expected-user 'YOUR-APPROVED-USER' \
  --apply --evidence '/YOUR-PRIVATE-DIRECTORY/registry-deployment-link.json'
```

APPLY saves a mode-0600 pre-mutation observation, validates the patch with a server dry run, and uses resource-version and UID compare-and-swap tests. It changes only these native metadata fields:

| Metadata | Meaning |
|---|---|
| Label `modelregistry.opendatahub.io/name` | Discovered registry name |
| Label `modelregistry.opendatahub.io/registered-model-id` | Existing registered-model ID |
| Label `modelregistry.opendatahub.io/model-version-id` | Existing exact version ID |
| Annotation `modelregistry.opendatahub.io/model-version-name` | Readable version name |

It then observes reconciliation for 15 seconds and verifies the association, serving-spec hash, generation, selected model/scheduler pod UIDs, and container restart counts. It also verifies that the registry version did not change during the operation. An unexpected difference produces **REVIEW_REQUIRED** and keeps the private report; it does not automatically undo concurrent work. Coordinate this small observation window with other administrators.

These resolved IDs belong to the destination registry. Keep them out of portable GitOps manifests and rerun discovery for each cluster. Repeating PLAN against an already matching association reports zero changes. If another reconciler explicitly owns these same metadata keys, resolve that ownership before applying; do not disable general reconciliation.

## Acceptance

The helper's mismatch tests exercise foreign ownership, different immutable revisions, and conflicting registry/model/version associations. Live acceptance additionally requires unchanged generation, serving spec, model and scheduler pod UIDs, and restart counts. Native browser acceptance is a separate check: the selected version's **Deployments** table must list the existing Qwen deployment.

```bash
python3 -m unittest discover -s tests -p test_registry_deployment_link.py -v
```

## Hardware profile coherence

The linked deployment uses the project profile **Showroom L40S · 1 GPU / 48 GB** (`ai-showroom/showroom-l40s-1`). Each replica requests and limits 4 CPU, 24 GiB of host memory, and one GPU, exactly matching the profile defaults. GPU VRAM and host memory are different resources. Two replicas therefore consume two GPUs overall; the profile remains a per-replica configuration.

Qwen satisfies every profile node selector and the exact GPU toleration. Its additional `g6e.2xlarge` selector and anti-affinity are preserved. The hardware profile does not provision nodes or establish model quality. Native linkage uses `opendatahub.io/hardware-profile-name`, `opendatahub.io/hardware-profile-namespace`, and the observed profile resource-version annotation. Portable model manifests contain only the stable name and namespace; the resource version is discovered separately on each cluster. [Native llm-d extraction](https://github.com/opendatahub-io/odh-dashboard/blob/4fdc824a5ff91fc2069ceb35130b2338499e2c5f/packages/llmd-serving/src/deployments/hardware.ts), [native hardware profile metadata](https://github.com/opendatahub-io/odh-dashboard/blob/4fdc824a5ff91fc2069ceb35130b2338499e2c5f/packages/hardware-profiles/shared/utils.ts).

For an existing deployment, run the bounded helper with the same independently supplied identity guards as above. PLAN validates owned resources, the pinned candidate URI, exact per-replica defaults, selectors, tolerations, and conflicting associations. APPLY requires a new private evidence file, changes only annotations with a resource-version CAS, and verifies generation, spec, model/scheduler pod UIDs, and restart counts after reconciliation.

```bash
python3 gitops/components/models/link_hardware_profile.py \
  --expected-server 'https://api.YOUR-CLUSTER:6443' \
  --expected-user 'YOUR-APPROVED-USER'
```

Add `--apply --evidence '/YOUR-PRIVATE-DIRECTORY/hardware-profile-link.json'` after reviewing PLAN. If profile defaults or deployment resources differ, the helper refuses the association; assess the discrepancy instead of labeling incompatible hardware as a match.
