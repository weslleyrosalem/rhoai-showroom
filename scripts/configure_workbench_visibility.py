#!/usr/bin/env python3
"""Expose existing Aurora workbench storage and its actual S3 connection.

PLAN is read-only. APPLY patches metadata only, using UID/resourceVersion tests,
then verifies unchanged PVC spec, Secret contents, Notebook spec, and pod restarts.
No credentials, workload specs, permissions, or backend database disks are changed.
Primary convention: odh-dashboard commit cc402383e903f71dcff388369eea86dcb2a94d59,
frontend/src/api/k8s/pvcs.ts and packages/k8s-core/src/connectionTypeUtils.ts.
"""
import argparse
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
NS = 'ai-showroom'
OWNER = 'rhoai-showroom'
S3_LABELS = {'opendatahub.io/dashboard': 'true', 'opendatahub.io/managed': 'true'}
S3_ANNOTATIONS = {
    'opendatahub.io/connection-type-ref': 's3',
    'opendatahub.io/connection-type': 's3',
    'openshift.io/display-name': 'Aurora Supply — Workbench object storage',
    'openshift.io/description': 'Existing S3-compatible connection used by the Aurora workbench for synthetic data and experiment artifacts. Internal showroom endpoint.',
}
PVC_LABELS = {'app.kubernetes.io/part-of': OWNER, 'opendatahub.io/dashboard': 'true'}
PVC_ANNOTATIONS = {
    'openshift.io/display-name': 'Aurora Supply — Workbench storage',
    'openshift.io/description': 'Persistent notebooks, source code, and local experiment files for the Aurora Supply data science lab',
}


def oc(*args, body=None):
    result = subprocess.run(['oc', '--request-timeout=30s', *args], input=None if body is None else json.dumps(body),
                            capture_output=True, text=True, timeout=40)
    if result.returncode:
        raise RuntimeError('OpenShift operation failed; no command body or response was logged')
    return result.stdout.strip()


def get(kind, name, namespace=NS):
    return json.loads(oc('get', kind, name, '-n', namespace, '-o', 'json'))


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def snapshot():
    pvc = get('pvc', 'aurora-lab')
    secret = get('secret', 'showroom-s3-credentials')
    notebook = get('notebook', 'aurora-lab')
    pods = json.loads(oc('get', 'pods', '-n', NS, '-l', 'notebook-name=aurora-lab', '-o', 'json'))['items']
    if pvc['status'].get('phase') != 'Bound':
        raise ValueError('Existing workbench disk must already be Bound')
    if pvc['metadata'].get('annotations', {}).get('argocd.argoproj.io/tracking-id') != 'rhoai-showroom:/PersistentVolumeClaim:ai-showroom/aurora-lab':
        raise ValueError('Workbench disk is not tracked by the showroom application')
    if secret['metadata'].get('labels', {}).get('app.kubernetes.io/part-of') != OWNER:
        raise ValueError('Existing S3 Secret is not showroom-owned')
    declared = secret['metadata'].get('annotations', {})
    if any(declared.get(key) not in (None, 's3') for key in
           ('opendatahub.io/connection-type-ref', 'opendatahub.io/connection-type')):
        raise ValueError('Existing connection declares another type; refusing to convert it')
    if declared.get('opendatahub.io/connection-hidden') == 'true':
        raise ValueError('Existing connection is intentionally hidden; review before exposing it')
    spec = notebook['spec']['template']['spec']
    if not any(v.get('persistentVolumeClaim', {}).get('claimName') == 'aurora-lab' for v in spec.get('volumes', [])):
        raise ValueError('Workbench does not use this persistent disk')
    if not any(v.get('secretRef', {}).get('name') == 'showroom-s3-credentials'
               for c in spec['containers'] for v in c.get('envFrom', [])):
        raise ValueError('Workbench does not use this existing connection')
    fields = json.loads(get('configmap', 's3', 'redhat-ods-applications')['data']['fields'])
    required = {field['envVar'] for field in fields if field.get('required')}
    if not required or not required <= secret.get('data', {}).keys():
        raise ValueError('Existing connection lacks the installed S3 type required keys')
    if not pods or any(p['metadata'].get('deletionTimestamp') for p in pods):
        raise ValueError('Workbench pods are absent or being replaced; retry in a stable window')
    stable = {
        'pvc_uid': pvc['metadata']['uid'], 'pvc_spec_sha256': digest(pvc['spec']),
        'secret_uid': secret['metadata']['uid'], 'secret_data_sha256': digest(secret.get('data', {})),
        'secret_type': secret.get('type'), 'secret_immutable': secret.get('immutable'),
        'notebook_uid': notebook['metadata']['uid'], 'notebook_spec_sha256': digest(notebook['spec']),
        'notebook_generation': notebook['metadata'].get('generation'),
        'pods': sorted([{'name': p['metadata']['name'], 'uid': p['metadata']['uid'],
                        'restarts': {s['name']: s['restartCount'] for s in p.get('status', {}).get('containerStatuses', [])}}
                       for p in pods], key=lambda p: p['name']),
    }
    # Retain metadata and hashes only; Secret data never leaves memory.
    return pvc['metadata'], secret['metadata'], stable


def patch_metadata(kind, metadata, labels, annotations):
    desired_labels = {**metadata.get('labels', {}), **labels}
    desired_annotations = {**metadata.get('annotations', {}), **annotations}
    if metadata.get('labels') == desired_labels and metadata.get('annotations') == desired_annotations:
        return 'UNCHANGED'
    patch = [
        {'op': 'test', 'path': '/metadata/uid', 'value': metadata['uid']},
        {'op': 'test', 'path': '/metadata/resourceVersion', 'value': metadata['resourceVersion']},
        {'op': 'add', 'path': '/metadata/labels', 'value': desired_labels},
        {'op': 'add', 'path': '/metadata/annotations', 'value': desired_annotations},
    ]
    args = ('patch', kind, metadata['name'], '-n', NS, '--type=json', '--patch-file=/dev/stdin')
    oc(*args, '--dry-run=server', '-o', 'name', body=patch)
    oc(*args, '-o', 'name', body=patch)
    return 'UPDATED_METADATA_ONLY'


def save(directory, name, value):
    with os.fdopen(os.open(directory / name, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), 'w') as stream:
        json.dump(value, stream, indent=2)
        stream.write('\n')
        stream.flush()
        os.fsync(stream.fileno())


def audit_metadata(metadata):
    # Do not copy arbitrary annotations, managed fields, or last-applied payloads.
    labels = set(S3_LABELS) | set(PVC_LABELS)
    annotations = set(S3_ANNOTATIONS) | set(PVC_ANNOTATIONS) | {'argocd.argoproj.io/tracking-id'}
    return {key: metadata.get(key) for key in ('name', 'namespace', 'uid', 'resourceVersion')} | {
        'labels': {key: value for key, value in metadata.get('labels', {}).items() if key in labels},
        'annotations': {key: value for key, value in metadata.get('annotations', {}).items() if key in annotations}}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--expected-server', required=True)
    parser.add_argument('--expected-user', required=True)
    parser.add_argument('--audit-dir', type=Path, help='New private directory outside the repository; required for APPLY')
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    if oc('whoami', '--show-server') != args.expected_server or oc('whoami') != args.expected_user:
        raise ValueError('Unexpected cluster or identity')
    pvc, secret, before = snapshot()
    summary = {'mode': 'APPLY' if args.apply else 'PLAN', 'namespace': NS,
               'storage': pvc['name'], 'connection': secret['name'],
               'changes': 'Dashboard labels and readable metadata only',
               'credentials_or_permissions_changed': False}
    if not args.apply:
        print(json.dumps(summary, indent=2))
        return
    if not args.audit_dir:
        raise ValueError('APPLY requires an exclusive private audit directory')
    audit = args.audit_dir.resolve()
    if audit.exists() or audit == ROOT or ROOT in audit.parents:
        raise ValueError('Use a new private audit directory outside the repository')
    audit.mkdir(parents=True, mode=0o700)
    os.chmod(audit, 0o700)
    save(audit, 'before.json', {'timestamp': dt.datetime.now(dt.timezone.utc).isoformat(),
        'pvc_metadata': audit_metadata(pvc), 'connection_metadata': audit_metadata(secret), 'invariants': before})
    summary['storage_result'] = patch_metadata('pvc', pvc, PVC_LABELS, PVC_ANNOTATIONS)
    summary['connection_result'] = patch_metadata('secret', secret, S3_LABELS, S3_ANNOTATIONS)
    new_pvc, new_secret, after = snapshot()
    unchanged = before == after
    save(audit, 'after.json', {'timestamp': dt.datetime.now(dt.timezone.utc).isoformat(),
        'pvc_metadata': audit_metadata(new_pvc), 'connection_metadata': audit_metadata(new_secret), 'invariants': after,
        'invariants_unchanged': unchanged})
    if not unchanged:
        raise RuntimeError('A protected invariant changed during the observation window; inspect the private audit')
    summary['invariants_unchanged'] = True
    print(json.dumps(summary, indent=2))


if __name__ == '__main__':
    try:
        main()
    except (ValueError, RuntimeError, KeyError, OSError, subprocess.TimeoutExpired) as error:
        print(json.dumps({'status': 'BLOCKED', 'reason': str(error)}), file=sys.stderr)
        sys.exit(2)
