# Install in another cluster

This procedure deploys the Aurora experience on a compatible ROSA cluster. Infrastructure, operators, and credentials are explicit prerequisites. Cloning this repository does not grant access to an AWS account.

## 1. Prepare the platform

Use OpenShift AI **3.5.1**, OpenShift **4.22+** for MCP Lifecycle, NVIDIA GPU Operator, Node Feature Discovery, OpenShift Service Mesh 3, Red Hat Connectivity Link 1.4.3/MaaS, MCP Gateway Operator 0.7.1, OpenShift GitOps 1.21, Tempo, and OpenTelemetry. Verify supported combinations against your subscription documentation. A ROSA cluster with GPUs does not include all these operators automatically.

The [official RHOAI installation chart](https://developers.redhat.com/articles/2026/08/26/automating-red-hat-openshift-ai-installations-with-helm-and-gitops) can establish the platform in a new cluster. The article documents version `v3.5`; authenticate to the registry and verify the chart artifact and its current values before using it. This showroom has not yet validated that chart as a complete fresh-cluster installer. Preserve existing operators in shared clusters. Do not replace an entire DSC with an example manifest.

You need an installation administrator's authenticated `oc`, Git, Python 3.12, credentials for `registry.redhat.io`, a default StorageClass, working DNS/TLS, and network access to the registries, GitHub, and Hugging Face. These labs use synthetic data and do not require GPT credentials.

## 2. Clone and check

```bash
git clone https://github.com/weslleyrosalem/rhoai-showroom.git
cd rhoai-showroom
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements-docs.txt
# Enter the intended cluster's API address after checking oc whoami.
export SHOWROOM_SERVER=https://api.YOURCLUSTER:6443
python scripts/showroom.py preflight --expected-server "$SHOWROOM_SERVER"
```

The preflight is read-only. It verifies the release and required APIs; it does not prove GPU availability. Also run the [capacity guard](../labs/hardware.md) with a fresh inventory of every ROSA pool.

## 3. Bootstrap the namespace, secrets, and shared services

```bash
python scripts/showroom.py bootstrap --expected-server "$SHOWROOM_SERVER"
oc apply -k gitops/components/storage
oc rollout status deployment/showroom-s3 -n ai-showroom --timeout=180s
oc apply -k gitops/components/mlflow
oc wait mlflow/mlflow --for=condition=Available --timeout=300s
oc apply -k gitops/components/evaluation
```

Bootstrap generates random credentials in Kubernetes, reuses owned Secrets, rejects conflicting credentials, and saves private per-cluster DSC/DSCI snapshots before applying partial patches. The demonstration S3 server uses a 20 Gi PVC. MLflow uses a single replica and a 5 Gi SQLite PVC. EvalHub uses PostgreSQL with a 5 Gi PVC. These are showroom choices without high-availability or disaster-recovery guarantees.

If the cluster already has shared MLflow or EvalHub instances, review their storage and existing consumers before adopting these manifests. Creating another singleton is not tenant isolation. DSC patches preserve other components. Keep `mcpGuardrailsMode: false` to enable EvalHub alongside NeMo.

## 4. Select a model and access policy

For a new cluster, use the portable profile and deploy Qwen4B after capacity is authorized. To reuse an existing model, adapt the model references in `existing-cluster` before synchronization. That overlay's Llama name belongs to the validation environment and is not a universal prerequisite.

Follow [MaaS](../labs/maas.md) to configure groups, subscriptions, and a time-limited key. The `ai-showroom/showroom-maas-key` Secret requires `api-key`, `base-url` ending in `/v1`, and `model-id`. Never store credentials in Git, notebooks, or screenshots.

## 5. Connect the services and adopt GitOps

Follow [MCP](../labs/mcp.md) for the build, TokenReview audience, Authorino TLS, and authenticated smoke tests. The backend stays private. Apply public MCP ingress only after anonymous access is denied and an authorized tool call succeeds.

```bash
oc apply -k gitops/components/guardrails/mcp-integration
oc apply -k gitops/components/science
oc apply -k gitops/components/experience
```

The science component also creates the separate `ai-showroom-monitoring` project for the supported OVMS/TrustyAI exercise. Complete the [logger TLS prerequisite](../labs/model-monitoring.md#deployment-and-tls-prerequisite) with a private backup before sending its reference and scenario batches. This explicit shared ConfigMap adjustment is not silently managed by the Application. Verify capture, authorization, and metric history before presenting predictive monitoring.

The RAG BuildConfig and Workbench clone this repository. In a fork, update both URLs and the AppProject/Application repository references. Follow [Ray](../labs/ray.md) and [pipelines](../labs/pipelines.md) to upload data and submit experiments. Jobs are explicit actions and are not continuously recreated by GitOps.

Complete [GitOps adoption](gitops.md), run the [test drives](test-drive.md), and maintain a validation record for your installation. GPU and MIG profiles require coordinated cloud capacity changes; the default overlay does not provision them.

After GitOps adoption has attached the Application tracking metadata and the Workbench is Ready, expose its existing disk and mounted S3 connection in the native project tabs. This guarded helper changes metadata only; it neither creates credentials nor changes access. Set `SHOWROOM_USER` to the independently verified administrator identity.

```bash
python scripts/configure_workbench_visibility.py \
  --expected-server "$SHOWROOM_SERVER" --expected-user "$SHOWROOM_USER"
# Review the PLAN, then apply with a new private directory outside this checkout.
python scripts/configure_workbench_visibility.py \
  --expected-server "$SHOWROOM_SERVER" --expected-user "$SHOWROOM_USER" \
  --apply --audit-dir /YOUR-PRIVATE-DIRECTORY/workbench-visibility
```

Verify **Aurora Supply — Workbench storage** in Cluster storage and **Aurora Supply — Workbench object storage** in Connections, attached to the running Workbench. Display metadata only; never reveal the connection's credential fields.

## Installation acceptance

An authorized participant receives a model response, RAG sources, and MCP tool results; an unauthorized participant is denied. Ray experiments, MLflow artifacts, and evaluations have actual run IDs and results. Argo reaches Synced/Healthy and corrects a harmless drift. Selected GPU models become Ready and respond. Optional capabilities are marked validated only after their specific tests pass.

## Existing shared configuration

Bootstrap checks the operator release before enabling its optional DSC components, then waits for the required feature APIs. A missing MCP Lifecycle CRD does not prevent that enablement step. Other prerequisite operators must still be installed separately.

If existing TrustyAI mode or tracing storage, retention, or sampling differs, bootstrap stops before modifying resources. Review the existing consumers and proposed partial JSON patches. Use `--allow-shared-changes` only when you intentionally choose the showroom settings for that shared platform. Per-cluster backups are retained locally.

The S3 connection includes endpoint and region fields required by native pipeline templates. The internal OGX connection uses a placeholder API-key field because that private server runs without application authentication. It is not an external credential; network isolation must protect its endpoint.

## Inspect missing operators without changing the cluster

The [operator planner](https://github.com/weslleyrosalem/rhoai-showroom/blob/main/gitops/bootstrap/operators/README.md) checks exact release pins in the configured catalogs, preserves installed operators, and renders manual-approval subscriptions for missing prerequisites. It does not execute installation.

```bash
python3 scripts/platform_bootstrap.py --help
```

Review its documented arguments, OperatorGroup compatibility checks, and generated plan. OLM may add transitive dependencies; review the actual InstallPlan before approval. The reference cluster passed the pin check with all 12 required operators already present. A fresh-cluster installation remains unvalidated.
