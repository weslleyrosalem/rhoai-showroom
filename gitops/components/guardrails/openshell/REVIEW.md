# OpenShell deployment review

This optional lab uses OpenShell chart/CLI **0.0.116**, chart digest
`sha256:df55cd1538bdfb7836834c30dfcf8373b85ffea83bbfd70d50dbe69407a0d2b3`,
and matching ODH gateway/supervisor tag **v0.0.116-rhaiv.0**. It is Developer
Preview, outside the default GitOps application.

The Agent Sandbox Operator **0.9.0** is a prerequisite and watches all namespaces.
Its OLM InstallPlan is manual so the exact CSV can be checked before approval.

The custom SCC is available only to
`system:serviceaccount:ai-showroom-sandbox:showroom-openshell-sandbox` through a
namespaced RoleBinding. It permits a root supervisor with SYS_ADMIN (mounts and
namespaces), NET_ADMIN (network rules), SYS_PTRACE (process identification), and
SYSLOG (requested by the supervisor). It retains ordinary container capabilities
needed to drop to the agent UID. This is broader than restricted-v2. It does not
permit fully privileged containers, host namespaces, host ports, or hostPath.
SELinux namespace labels and RuntimeDefault seccomp remain in place. The agent
process must run unprivileged; successful admission is not proof of isolation.

The gateway runs non-root. The Helm chart grants it namespace-scoped Sandbox
lifecycle and event/pod reads; cluster-scoped node reads, namespace get, and
TokenReview creation support scheduling, OpenShift UID resolution, and sandbox
identity. Shared workspace mode prevents namespace creation and cluster-wide
Sandbox management. Inspect the rendered chart for any new privileges on upgrade.

No public Route or anonymous user mode is enabled. A dedicated audience alone
does not restrict which service account can authenticate. The mandatory Envoy
front proxy therefore uses a local authorization adapter with a live TokenReview
and an exact administrative subject check. A different valid service account
token with the same audience was denied, as were anonymous and invalid requests.
The adapter can create TokenReviews and has no Secret or workload-management
permissions. Its native callback allowlist delegates gateway-issued sandbox JWT
verification to the existing gateway; forged callback credentials were rejected.

The gateway's native authentication-only mode is confined behind that proxy;
its NetworkPolicy accepts ingress only from proxy pods. The proxy accepts network
ingress only from sandbox pods carrying the actual Agent Sandbox controller label
inside the dedicated namespace. Administrators connect through authenticated
`oc port-forward`; customer roles cannot use it there. An unlabeled pod could
connect to neither proxy nor backend. The native Kubernetes driver does not
support mTLS user authentication, and service-account tokens do not contain the
role arrays expected by native OIDC role authorization. These constraints are
why the reviewed front proxy is required, not optional. Both TLS hops verify
certificates. Local credentials have owner-only permissions and remain outside
Git. Short-lived tokens must be renewed for a later demonstration.

A real syscall check from a standard restricted pod on the installed RHCOS kernel
5.14.0-687.41.1.el9_8.x86_64 returned **Landlock ABI 6** with errno 0. Repeat on the
node chosen for each sandbox. Do not disable Landlock, seccomp, or network
rejection to make a test pass. No additional GPU is requested; inference uses the
existing showroom model endpoint.

Observed agent checks passed: non-root namespace UID, zero effective capabilities,
no-new-privileges, seccomp mode 2, denied writes outside the filesystem policy,
unreadable TLS private key and service-account token, unapproved egress denied
with proxy 403, and a real model response through verified `inference.local` TLS.
The runtime reported an unlimited PID cgroup; no node-wide PID setting was
changed. This remains a documented resource-exhaustion limitation. The lab does
not claim a complete production hardening baseline or a full NeMoClaw deployment.

Sources: [RHOAI preview guide](https://github.com/opendatahub-io/agent-ops/blob/7230605c8c0a4cec41c3e39e52e521db5c941355/guides/getting-started-openshell-openshift.md),
[documented SCC requirements](https://github.com/opendatahub-io/agent-ops/blob/7230605c8c0a4cec41c3e39e52e521db5c941355/scc-requirements.md),
[version-pinned driver capabilities](https://github.com/NVIDIA/OpenShell/blob/d1155aa70042d3e2ee49dbfa15346b108b7c1d92/crates/openshell-driver-kubernetes/src/driver.rs).
