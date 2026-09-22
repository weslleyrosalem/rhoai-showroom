# Private OpenShell preview lab

This optional extension runs a real OpenShell sandbox in `ai-showroom-sandbox`.
It is **Developer Preview in OpenShift AI 3.5**, using upstream artifacts; the
upstream Kubernetes chart is experimental. It is outside the default Argo CD
application. Read [REVIEW.md](REVIEW.md) before installation.

The tested path is:

```text
Administrative CLI → verified TLS → Envoy + exact-subject TokenReview
                  → verified TLS → OpenShell gateway → Agent Sandbox controller
Agent → OpenShell supervisor / policy → inference.local → existing MaaS model
```

There is no public Route and no additional GPU. Customer showroom roles do not
have pod, Sandbox, or port-forward access in the isolation namespace. The lab is
an administrator-led test drive, not a shared customer agent-hosting service.

## Versions and permissions

| Component | Pin |
|---|---|
| OpenShell CLI/chart | 0.0.116 |
| OCI chart | `sha256:df55cd1538bdfb7836834c30dfcf8373b85ffea83bbfd70d50dbe69407a0d2b3` |
| ODH gateway and supervisor | `v0.0.116-rhaiv.0`, immutable digests in `values.yaml` |
| Agent Sandbox Operator | 0.9.0, manual OLM InstallPlan |
| Sandbox base | Immutable community image digest in `values.yaml` |

The sandbox supervisor requires a custom SCC with four extra capabilities,
documented in [REVIEW.md](REVIEW.md). Only its dedicated service account can use
that SCC. The agent drops to the namespace's allocated UID, has zero effective
capabilities, and runs under Landlock, seccomp, and no-new-privileges. Do not
substitute the privileged SCC or disable TLS or Landlock to pass a check.

Three narrow chart patches are explicit and version-pinned: preserve empty
backend role names behind the subject gate; send the canonical Service through
that gate; select the actual operator-generated sandbox pod label for SSH
isolation. Version 0.0.116 does not support mTLS **user authorization** with its
Kubernetes driver, and ordinary service-account JWTs do not contain OpenShell
role arrays. The backend's authentication-only mode is safe here only in
combination with the mandatory front gate and backend NetworkPolicy.

The front gate TokenReviews administrative tokens with audience
`showroom-openshell` and requires the exact subject
`system:serviceaccount:ai-showroom-sandbox:showroom-openshell-client`. A different
valid service account token with that audience is denied. Bootstrap accepts only
the sandbox service account with audience `openshell-gateway` on
`IssueSandboxToken`. Gateway-issued sandbox JWTs can reach only the pinned
callback method list; the native gateway still verifies their signature,
audience, expiry, and same-sandbox identity. An unavailable authorizer fails
closed. The adapter has only `create tokenreviews` cluster permission.

## Install and connect

Prerequisites: cluster administrator access, Helm, `oc`, Python 3, `patch`, the
core showroom MaaS key, and the [OpenShell 0.0.116 CLI](https://github.com/NVIDIA/OpenShell/releases/tag/v0.0.116)
with its published checksum verified. Set `SHOWROOM_SERVER` to the expected
cluster API URL independently of the current CLI context.

```bash
oc apply -f gitops/components/guardrails/openshell/operator.yaml
oc get installplan -n agent-sandbox-system
```

Inspect the generated plan. Approve it only when its CSV list contains the
intended `agent-sandbox-operator.v0.9.0` and no unexpected installations:

```bash
oc patch installplan VERIFIED_PLAN_NAME -n agent-sandbox-system \
  --type merge -p '{"spec":{"approved":true}}'
oc get csv,pods -n agent-sandbox-system
python3 gitops/components/guardrails/openshell/install.py \
  --expected-server "$SHOWROOM_SERVER"
python3 gitops/components/guardrails/openshell/install.py \
  --expected-server "$SHOWROOM_SERVER" --apply
```

The installer checks the cluster identity and exact chart digest, applies only
this extension, and resolves the cluster OIDC issuer. It does not print rendered
Secrets. Keep a separate terminal running:

```bash
oc port-forward -n ai-showroom-sandbox service/showroom-openshell 38004:8080
```

Create owner-only CLI state **outside the repository**. Refresh the short-lived
token by rerunning `configure_cli.py` when needed; never paste a token in a guide.

```bash
export SHOWROOM_STATE="$(mktemp -d)"
python3 gitops/components/guardrails/openshell/configure_cli.py \
  --expected-server "$SHOWROOM_SERVER" --state-dir "$SHOWROOM_STATE"
export XDG_CONFIG_HOME="$SHOWROOM_STATE"
openshell -g showroom status
python3 gitops/components/guardrails/openshell/configure_provider.py \
  --expected-server "$SHOWROOM_SERVER" --state-dir "$SHOWROOM_STATE"
openshell -g showroom sandbox create --name aurora-sandbox \
  --from ghcr.io/nvidia/openshell-community/sandboxes/base@sha256:c2a43bb0d765774e2790b3babfb20997bb2eac7b4bf4c6d7d8661e99817bf904 \
  --cpu 1 --memory 1Gi \
  --policy gitops/components/guardrails/openshell/sandbox-policy.yaml \
  --provider aurora-maas --no-auto-providers --detach -- sleep infinity
```

The provider helper reads the existing MaaS Secret into memory, restricts the
endpoint to this cluster's HTTPS application domain, and passes the key through
an environment lookup, not a command-line value. The gateway stores its provider
credential. Agents receive credential indirection, not the real API key.

## Test drive and acceptance

```bash
python3 gitops/components/guardrails/openshell/validate.py \
  --expected-server "$SHOWROOM_SERVER" --state-dir "$SHOWROOM_STATE"
openshell -g showroom term
```

Run test commands with `openshell sandbox exec`. `oc exec` starts an administrative
process outside the agent enforcement path and is not a valid isolation test.
The validation checks the named user, anonymous and other-subject rejection,
forged native tokens, process restrictions, an allowed file write, a denied
write outside the policy, blocked credential reads, denied Internet egress,
and a real MaaS response through verified `https://inference.local` TLS.

Observed on the deployment rehearsal: UID from the OpenShift namespace range;
effective capabilities 0; no-new-privileges 1; seccomp mode 2; `/tmp` write allowed;
`/var/tmp` write and TLS key/token reads denied with errno 13; `example.org` proxy
403; model response HTTP 200. A separate unlabeled pod in the isolation namespace
could reach neither the access proxy nor the backend. Showroom visitor and
engineer service accounts could not open a port-forward.

The host kernel reported **Landlock ABI 6**. Check every node used by this lab.
The supervisor also reported an **unlimited runtime PID cgroup**; this lab has not
configured a node-wide PID limit and does not claim complete resource-exhaustion
protection. Successful acceptance is evidence for these tested controls, not a
production security certification. Upgrades require rechecking all three chart
patches, callback method authorization, labels, SCC requirements, and tests.

## Pause and remove

Stop the demo sandbox while keeping its workspace with
`openshell -g showroom sandbox stop aurora-sandbox`. Start it again with
`openshell -g showroom sandbox start aurora-sandbox` and rerun validation.
`sandbox delete aurora-sandbox` removes the demo sandbox and its workspace;
export anything worth retaining first. Remove the extension's Helm release and
only the explicitly owned manifests when decommissioning. Do not delete the
shared Agent Sandbox Operator if other sandboxes use it. Remove local CLI state
after the session; it contains a short-lived token and a TLS private key.

Sources: [OpenShift preview guide](https://github.com/opendatahub-io/agent-ops/blob/7230605c8c0a4cec41c3e39e52e521db5c941355/guides/getting-started-openshell-openshift.md),
[native authentication restriction](https://github.com/NVIDIA/OpenShell/blob/v0.0.116/crates/openshell-server/src/cli.rs),
[native RPC authorization](https://github.com/NVIDIA/OpenShell/blob/v0.0.116/proto/openshell.proto),
[Envoy external authorization](https://www.envoyproxy.io/docs/envoy/latest/configuration/http/http_filters/ext_authz_filter).
