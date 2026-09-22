# Existing AHEAD Granite backend isolation

This optional policy targets only the existing `ahead/redhataigranite-31-8b-instruct` workload. It does not create a model, change replicas, grant Workbench permissions, or alter another AHEAD workload.

TCP 8000 admits only the AHEAD Gateway pods in `openshift-ingress`, this model's scheduler in `ahead`, and the installed OpenShift AI collector in `redhat-ods-monitoring`. All selectors were checked against the running workloads. The Workbench must use the tenant Gateway and a permitted MaaS API key; it receives no direct backend allowance. NetworkPolicy does not encrypt traffic or replace MaaS authentication. Namespace administrators able to create or relabel trusted pods remain privileged.

An administrator should render and inspect this policy, verify the selected cluster and identity, and apply it alongside the existing tenant governance. Its acceptance gates are an authorized request through the AHEAD Gateway and a denied direct backend connection from the Workbench. Preserve current workload readiness and collector access. Do not infer those functional results merely from a created NetworkPolicy. This optional file is not included in the core Argo application.

The dedicated presenter subscription and access policy must name only this model and its intended presenter. The observed configuration uses `ai-tenant-ahead/ahead-granite-presenter`, owner `aiadmin`, priority 60, and 20,000 tokens/minute. These values are a scoped demonstration configuration, not a general visitor entitlement. A key for that subscription must not authorize another model.

The existing AHEAD Gateway contains an explicit allow-true placeholder named `tenant-gateway-isolation`. Model authorization and subscription validation use the tenant's API, but that placeholder itself does not enforce hostname-to-key tenant isolation. Do not describe cross-tenant isolation as proven without a separate negative test. This policy does not modify that shared Gateway rule.

## Reproduce the scoped governance

Prerequisites are the existing `AITenant/ahead`, its `ai-tenant-ahead` namespace and Gateway, and the user's two-replica Granite deployment. Inspect and adapt the model name and presenter identity before using this optional profile on another cluster. `governance.yaml` records the observed desired MaaS model reference, exact-model authorization, and subscription; it contains no keys.

After independently verifying the cluster and identity, associate the existing model with `spec.router.gateway.refs: [{name: ahead, namespace: openshift-ingress}]` and apply this directory with `oc apply -k`. Changing only the MaaS model reference is insufficient: verify the generated HTTPRoute's current parent is the AHEAD Gateway. Preserve the model URI, resources, replicas, and runtime settings. This profile does not create or take over the user's model deployment and is not part of the core Argo overlay.

## Observed acceptance, September 22 at 13:59 UTC

Both Granite replicas were Ready with zero restarts. Authorized tenant discovery returned exactly one model, the Granite publisher alias. One real chat returned HTTP 200 in 0.526 seconds with 80 provider-reported tokens and the requested phrase. Anonymous discovery returned 401; the same key requesting an unsubscribed model returned 403. Direct TCP 8000 connections from the Aurora Workbench timed out against both backend pods after the policy was applied.

The ten-minute rehearsal key was revoked successfully through the API. The installed authorization cache has a 60-second lifetime, so that API result does not establish instantaneous rejection of a previously cached key. These checks establish the tested access path, not a general model-quality or cross-tenant isolation verdict.

## Create a key when the native dialog cannot select AHEAD

The observed OpenShift AI 3.5.1 **API keys → Create API key** subscription selector uses the default tenant and does not list `ahead-granite-presenter`. Do not change the global dashboard tenant or select an unrelated subscription. The administrator helper uses the dedicated AHEAD Gateway API.

From the repository root, use an independently verified API server and the intended identity. Do not derive the expected values from the current context inside the command; this comparison catches an accidental context change.

```bash
python3 scripts/ahead-llmd/ahead_granite_key.py create \
  --expected-server "$SHOWROOM_SERVER" --expected-user aiadmin \
  --private-dir "$PRIVATE_PARENT/ahead-granite-session" --expires-in 1h
```

This command performs a read-only plan. `SHOWROOM_SERVER` must contain the independently verified HTTPS cluster API URL. `PRIVATE_PARENT` must be an existing location outside every Git checkout; the session directory must not exist. Repeat with **`--apply`** to create one key. Lifetimes are `10m`, `1h` (default), and `2h`. `--private-output` is an alias for `--private-dir`.

The helper discovers the AHEAD HTTPS Gateway, verifies exact tenant/model/presenter governance, and saves `credential.json` in a new mode-0700 directory with mode-0600 file permissions. It prints only the nonsecret file location and expiration. The file contains the key, ID, notebook base URL, and model ID. Inspect it privately, configure notebook 09 with the endpoint/model, and enter the key only in its masked prompt. Never project, upload, or commit this file. The helper sends no inference and creates no Kubernetes Secret.

Revoke only that saved key when finished:

```bash
python3 scripts/ahead-llmd/ahead_granite_key.py revoke \
  --expected-server "$SHOWROOM_SERVER" --expected-user aiadmin \
  --credential-file "$PRIVATE_PARENT/ahead-granite-session/credential.json" --apply
```

Revocation checks the current cluster/tenant, private file scope, and remote key ID, name, owner, and subscription before deleting that exact key. Without `--apply`, it only plans the action. Keep the private record for audit; revocation does not erase it. The observed 60-second authorization cache means API success does not prove instantaneous rejection of a cached request. If creation is interrupted, inspect the tenant's key metadata before retrying: the helper never automatically repeats an uncertain creation request.
