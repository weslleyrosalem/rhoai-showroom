#!/usr/bin/env python3
"""Plan/apply one owned OVMS dashboard compatibility rule; no shared edits."""
import argparse
import json
import os
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]
NAMESPACE = 'openshift-monitoring'
NAME = 'showroom-ovms-resource-limit-compatibility'


def oc(*args, data=None):
    result = subprocess.run(['oc', '--request-timeout=30s', *args], input=data,
                            capture_output=True, text=True, timeout=40)
    if result.returncode:
        raise RuntimeError('OpenShift operation failed; output suppressed')
    return result.stdout.strip()


def main():
    import yaml
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--expected-server', required=True)
    parser.add_argument('--expected-user', required=True)
    parser.add_argument('--backup', type=Path, help='New private file outside the repository, required to apply')
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    if oc('whoami', '--show-server') != args.expected_server or oc('whoami') != args.expected_user:
        raise ValueError('Cluster or identity mismatch')
    desired = yaml.safe_load((ROOT / 'gitops/bootstrap/monitoring-compatibility.yaml').read_text())
    if desired['metadata']['namespace'] != NAMESPACE or desired['metadata']['name'] != NAME:
        raise ValueError('Manifest target must remain the exact owned compatibility rule')
    current_raw = oc('get', 'prometheusrule', NAME, '-n', NAMESPACE, '--ignore-not-found', '-o', 'json')
    current = json.loads(current_raw) if current_raw else None
    if current and current['metadata'].get('labels', {}).get('app.kubernetes.io/part-of') != 'rhoai-showroom':
        raise ValueError('Refuse to modify a foreign rule')
    if current and current['spec'] == desired['spec']:
        print(json.dumps({'mode': 'UNCHANGED', 'resource': NAMESPACE + '/' + NAME}))
        return
    payload = json.dumps(desired)
    operation = ['create', '-f', '-']
    if current:
        operation = ['patch', 'prometheusrule', NAME, '-n', NAMESPACE, '--type=json', '--patch-file=/dev/stdin']
        payload = json.dumps([
            {'op': 'test', 'path': '/metadata/uid', 'value': current['metadata']['uid']},
            {'op': 'test', 'path': '/metadata/resourceVersion', 'value': current['metadata']['resourceVersion']},
            {'op': 'replace', 'path': '/spec', 'value': desired['spec']},
        ])
    oc(*operation, '--dry-run=server', data=payload)
    print(json.dumps({'mode': 'APPLY' if args.apply else 'PLAN', 'resource': NAMESPACE + '/' + NAME,
                      'scope': 'Only aurora-allocation predictor CPU/memory limits in ai-showroom-monitoring',
                      'changes_existing_shared_rules': False, 'spec': desired['spec']}, indent=2))
    if not args.apply:
        return
    if not args.backup:
        raise ValueError('Apply requires an exclusive backup path')
    path = args.backup.expanduser().resolve()
    if path == ROOT or ROOT in path.parents:
        raise ValueError('Backup must be outside the public repository')
    path.parent.mkdir(parents=True, exist_ok=True)
    with os.fdopen(os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600), 'w') as stream:
        json.dump({'expected_server': args.expected_server, 'previous': current, 'desired': desired}, stream, indent=2)
        stream.write('\n')
        stream.flush()
        os.fsync(stream.fileno())
    oc(*operation, data=payload)
    print('Owned compatibility rule applied. Verify real recorded series before claiming chart acceptance.')


if __name__ == '__main__':
    main()
