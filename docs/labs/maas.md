# Lab — APIs, groups, and quotas

Aurora Supply uses a common model API. The platform decides who may call it and how much each consumer may use. An AuthPolicy grants access; a subscription sets the quota. Both must be valid.

## Repository resources

| Resource | Purpose |
|---|---|
| `showroom-platform-admins` | Initially contains only `aiadmin`; does not create a login |
| `showroom-data-scientists` | Initially empty; map existing identities into it |
| `showroom-visitors` | Initially empty; controlled test-drive access |
| `showroom-model-access` | Authorizes the three groups for the curated model |
| `showroom-test-drive` | 100 tokens/minute, priority 15, three groups |
| `showroom-standard` | 200,000 tokens/hour, priority 20, administrators and scientists |

MaaS objects live in `models-as-a-service`. The portable profile references `ai-showroom/aurora-qwen-4b`. `gitops/profiles/existing-cluster` references the existing Llama in `maas-how-to`, preserving its model, `subplus`, and its AuthPolicy.

Group membership does not create a password or grant cluster-admin. The foundation assigns project-scoped RBAC. Manage membership consistently through Git or your identity provider; Argo may reconcile manual changes to a managed Group.

## Installation and discovery

Apply the module through the reviewed installation/GitOps workflow. To inspect server validation first:

```bash
oc apply --dry-run=server -k gitops/profiles/existing-cluster
oc get maasauthpolicy showroom-model-access -n models-as-a-service
oc get maassubscriptions -n models-as-a-service
```

On a new cluster, use `interactive` after the GPU preflight. `core` installs platform configuration only; its model reference cannot serve requests before a ready backend exists.

## Test drive

1. In the dashboard, create short-lived keys, selecting each subscription **explicitly**. `aiadmin` may also belong to the higher-priority `subplus`; automatic selection would invalidate the small-quota experiment.
2. Store keys in a secret manager or session environment variables. Keep them out of shell history, documents, and screenshots.
3. Make a request without credentials and confirm denial.
4. With the test-drive key, send input plus output exceeding 100 tokens. The first response may finish beyond the threshold; a subsequent request should return 429. The quota does not promise to cut text at exactly the hundredth token.
5. Confirm 200 with the standard key while the test-drive subscription remains limited.
6. Wait for the one-minute window and confirm recovery.
7. Open Usage and verify the selected subscription. Allow collection time before interpreting temporarily missing metrics.

This example assumes verified environment variables and prints only status and usage:

```bash
python3 - <<'PY'
import json, os, urllib.error, urllib.parse, urllib.request
class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None
url = os.environ['SHOWROOM_GATEWAY'].rstrip('/').removesuffix('/v1') + '/v1/chat/completions'
parsed = urllib.parse.urlsplit(url)
if parsed.scheme != 'https' or not parsed.hostname or parsed.username or parsed.password:
    raise ValueError('Use the verified HTTPS endpoint without credentials in its URL')
body = {'model': os.environ['SHOWROOM_MODEL'], 'max_tokens': 64,
        'messages': [{'role':'user','content':'At the fictional Aurora Supply company, explain in five sentences how an LLM token quota governs API consumption across teams and why a later request may return HTTP429.'}]}
request = urllib.request.Request(url, data=json.dumps(body).encode(), headers={
    'Content-Type':'application/json',
    'Authorization':'Bearer '+os.environ['SHOWROOM_API_KEY']})
try:
    with urllib.request.build_opener(NoRedirect).open(request, timeout=60) as response:
        value=json.load(response)
        print({'http_status':response.status,'usage':value.get('usage')})
except urllib.error.HTTPError as error:
    print({'http_status':error.code})
PY
```

New model: `publishers/ai-showroom/models/aurora-qwen-4b`. Shared backend: `publishers/maas-how-to/models/redhataillama-31-8b-instruct`. Discover the identifier in the target installation; it is not universal across clusters.

## Application credentials and rotation

`ai-showroom/showroom-maas-key` holds `api-key`, `base-url` ending in `/v1`, and `model-id`. The reference installation's key belongs explicitly to `showroom-standard`. The installed API accepted a 24-hour expiration and rejected 168 hours. Renew before a demonstration; inspect the Secret's expiration annotation without reading its data.

The optional public Qwen base manifests define separate subscriptions, including `aurora-qwen-4b-interactive` and `aurora-qwen-32b-benchmark`. In the current reference deployment, Qwen4B is a private native-auth routing benchmark and its MaaS resources were removed; the unready Qwen32B deployment and MaaS resources were also removed. Neither appears as a reachable MaaS model. The RAG application continues using its existing Llama key and model.

The helper validates cluster identity, an Active subscription, and the associated model. By default it shows a plan; add `--apply` to issue a 24-hour key and configure the Secret without printing credentials:

```bash
python3 gitops/components/platform/credentials/provision_maas.py \
  --expected-server "$EXPECTED_OPENSHIFT_SERVER" \
  --model-id publishers/maas-how-to/models/redhataillama-31-8b-instruct \
  --subscription showroom-standard \
  --key-file /private/directory/showroom-standard-NEW-DATE.json
```

The private directory must be outside the repository with mode 0700; files are created 0600. A valid existing file is reused for retries. To rotate, use a new filename, revoke the older key in MaaS, and restart workloads that consume the Secret through environment variables. The helper discovers the cluster Gateway, verifies HTTPS, and refuses redirects. For another cluster, provide its authorized identity with `--expected-user` and its model identifier.

## Acceptance and cleanup

Record 200/401/429, timestamps, subscription, and usage without keys. Test a real identity outside the permitted groups; testing only as `aiadmin` does not establish tenant isolation. Reissue keys after membership changes because issued keys may retain a group snapshot.

Revoke only the visit's keys when finished. Remove owned showroom resources by name/label; preserve shared namespaces, models, and `subplus`. This installation uses `maas.opendatahub.io/v1alpha1`; do not copy obsolete API-group examples. [MaaS guide](https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html/govern_llm_access_with_models-as-a-service/deploy-and-manage-models-as-a-service_maas).

## Inspect native consumption charts

Use **Observe & monitor → Dashboard → Usage**. Filter the exact subscription used by the request; select the model and inspect the **Token consumption table**, **Total rate limited**, and **Token consumption chart**. The [native dashboard guide](../operations/native-dashboards.md#1000-am-consumption-and-quota) explains the selected-range summary versus rolling two-hour chart, sampled counters, and the limiter-specific meaning of **Success rate**. Keep the actual HTTP status and recovery evidence alongside these charts.
