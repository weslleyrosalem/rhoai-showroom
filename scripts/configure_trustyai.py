#!/usr/bin/env python3
"""Configure KServe logger TLS without replacing existing image/resources.

Sets the documented ConfigMap management opt-out and logger service CA fields.
This never restarts any model. Operator upgrades require reviewing this ConfigMap.
Run after reviewing the current cluster and installing the monitoring component.
"""
import argparse
import json
import os
from pathlib import Path
import subprocess

p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--backup', help='New private path outside the repository for the prepatch ConfigMap (mode 0600)')
p.add_argument('--expected-server', help='Independently verified Kubernetes API URL')
p.add_argument('--expected-user', help='Independently verified oc identity')
p.add_argument('--apply', action='store_true', help='Apply after a server-side dry run')
a = p.parse_args()
if a.apply:
    if not a.expected_server or not a.expected_user or not a.backup:
        p.error('--apply requires --expected-server, --expected-user, and --backup')
    actual_server = subprocess.check_output(['oc', 'whoami', '--show-server'], text=True, timeout=20).strip()
    actual_user = subprocess.check_output(['oc', 'whoami'], text=True, timeout=20).strip()
    if (actual_server.rstrip('/'), actual_user) != (a.expected_server.rstrip('/'), a.expected_user):
        raise SystemExit('Cluster or identity mismatch; no changes made.')
base = ['oc', '-n', 'redhat-ods-applications']
current = json.loads(subprocess.check_output(base + ['get', 'configmap', 'inferenceservice-config', '-o', 'json'], timeout=20))
old = current['data']['logger']
logger = json.loads(old)
for key, value in {'caBundle': 'kserve-logger-ca-bundle', 'caCertFile': 'service-ca.crt', 'tlsSkipVerify': False}.items():
    if key in logger and logger[key] != value:
        raise SystemExit(f'Conflicting existing logger {key}; review that shared configuration before changing it.')
    logger[key] = value
patch = [{'op': 'test', 'path': '/metadata/resourceVersion', 'value': current['metadata']['resourceVersion']}, {'op': 'add', 'path': '/metadata/annotations/opendatahub.io~1managed', 'value': 'false'}, {'op': 'test', 'path': '/data/logger', 'value': old}, {'op': 'replace', 'path': '/data/logger', 'value': json.dumps(logger)}]
command = base + ['patch', 'configmap', 'inferenceservice-config', '--type=json', '--patch-file=/dev/stdin']
subprocess.run(command + ['--dry-run=server'], input=json.dumps(patch), text=True, check=True, timeout=20)
if a.apply:
    backup = Path(a.backup).expanduser().resolve()
    repo = Path(__file__).resolve().parents[1]
    if backup == repo or repo in backup.parents:
        raise SystemExit('Backup must be outside the public repository.')
    backup.parent.mkdir(parents=True, exist_ok=True)
    descriptor = os.open(backup, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    with os.fdopen(descriptor, 'w') as stream:
        json.dump(current, stream, indent=2)
        stream.write('\n')
        stream.flush()
        os.fsync(stream.fileno())
    subprocess.run(command, input=json.dumps(patch), text=True, check=True, timeout=20)
if a.apply:
    secret_name = 'aurora-monitoring-scrape-token'
    secret_namespace = 'ai-showroom-monitoring'
    result = subprocess.run(['oc', 'get', 'secret', secret_name, '-n', secret_namespace, '-o', 'json', '--ignore-not-found'], text=True, capture_output=True, check=True, timeout=20)
    if result.stdout.strip():
        secret = json.loads(result.stdout)
        if secret.get('type') != 'kubernetes.io/service-account-token' or secret['metadata'].get('annotations', {}).get('kubernetes.io/service-account.name') != 'aurora-monitoring-scrape':
            raise SystemExit('Conflicting existing scrape Secret; values were not changed.')
        print('Existing scoped scrape token Secret verified; no values printed or changed.')
    else:
        secret = {'apiVersion': 'v1', 'kind': 'Secret', 'type': 'kubernetes.io/service-account-token', 'metadata': {'name': secret_name, 'namespace': secret_namespace, 'annotations': {'kubernetes.io/service-account.name': 'aurora-monitoring-scrape'}, 'labels': {'app.kubernetes.io/part-of': 'rhoai-showroom'}}}
        subprocess.run(['oc', 'create', '-f', '-'], input=json.dumps(secret), text=True, check=True, timeout=20)
        print('Scoped scrape Secret created; Kubernetes populates its token outside Git.')
print('Logger configuration ' + ('patched' if a.apply else 'server-dry-run accepted') + '; existing image/resources preserved. Validate actual TLS capture separately. No model was restarted.')
