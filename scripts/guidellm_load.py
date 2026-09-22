#!/usr/bin/env python3
"""Plan or start the opt-in bounded GuideLLM Job, with verified local tokenizer files.

No ROSA/OCM calls. Never prints credentials. Existing Jobs and retained results
are preserved; rerunning --apply can finish tokenizer staging for a waiting Job.
"""
import argparse
import datetime as dt
import gzip
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
COMPONENT = ROOT / 'gitops/components/platform/load'
OWNER = 'rhoai-showroom'
FILES = ('tokenizer.json', 'tokenizer_config.json', 'special_tokens_map.json', 'config.json')


def oc(*args, data=None):
    result = subprocess.run(['oc', '--request-timeout=30s', *args], input=data,
                            capture_output=True, timeout=45,
                            env=dict(os.environ, KUBECTL_REMOTE_COMMAND_WEBSOCKETS='false'))
    if result.returncode:
        raise RuntimeError('OpenShift operation failed; response suppressed to protect credentials')
    return result.stdout


def get(kind, name, namespace):
    raw = oc('get', kind, name, '-n', namespace, '-o', 'json', '--ignore-not-found')
    return json.loads(raw) if raw else None


def owned(resource):
    if resource and resource['metadata'].get('labels', {}).get('app.kubernetes.io/part-of') != OWNER:
        raise ValueError('Refusing to adopt an object not owned by this showroom')


def apply(resource):
    meta = resource['metadata']
    owned(get(resource['kind'], meta['name'], meta['namespace']))
    oc('apply', '--server-side', '--field-manager=rhoai-showroom-load', '-f', '-', data=json.dumps(resource).encode())


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--expected-server', required=True)
    p.add_argument('--expected-user', required=True)
    p.add_argument('--tokenizer-dir', type=Path, required=True)
    p.add_argument('--max-rate', type=float, choices=(0.05, 0.1, 0.25, 0.5), default=0.1)
    p.add_argument('--apply', action='store_true')
    args = p.parse_args()
    if oc('whoami', '--show-server').decode().strip() != args.expected_server or oc('whoami').decode().strip() != args.expected_user:
        raise ValueError('Unexpected cluster or identity')
    job = json.loads((COMPONENT / 'job.yaml').read_text())
    namespace, name = job['metadata']['namespace'], job['metadata']['name']
    environment = {item['name']: item['value'] for item in job['spec']['template']['spec']['containers'][0]['env']}
    stop = dt.datetime.fromisoformat(environment['STOP_AT'].replace('Z', '+00:00'))
    remaining = (stop - dt.datetime.now(dt.timezone.utc)).total_seconds()
    if not 60 < remaining <= 172800:
        raise ValueError('Set STOP_AT to a future absolute deadline within 48 hours before starting')
    source = args.tokenizer_dir.resolve()
    blobs = {name: (source / name).read_bytes() for name in FILES}
    if any(len(blob) > 30000000 for blob in blobs.values()):
        raise ValueError('Tokenizer file exceeds the 30 MB bound')
    manifest = {'status': 'PLAN', 'job': namespace + '/' + name, 'stop_at': stop.isoformat(),
                'max_rate': args.max_rate, 'tokenizer_sha256': {name: hashlib.sha256(blob).hexdigest() for name, blob in blobs.items()},
                'uses_gpu': False, 'preserves_existing_results': True}
    if not args.apply:
        print(json.dumps(manifest))
        return
    secret = get('secret', 'showroom-guidellm-key', namespace)
    owned(secret)
    if not secret or not {'api-key', 'base-url', 'model-id'} <= set(secret.get('data', {})):
        raise ValueError('Provision the dedicated showroom-guidellm-key Secret first')
    annotations = secret['metadata'].get('annotations', {})
    if annotations.get('showroom.openshift.ai/subscription') != 'showroom-load':
        raise ValueError('The load key must belong to showroom-load')
    expiry = dt.datetime.fromisoformat(annotations['showroom.openshift.ai/expires-at'].replace('Z', '+00:00'))
    if expiry <= stop:
        raise ValueError('Credential must expire after the absolute load deadline')
    for resource in json.loads((COMPONENT / 'resources.yaml').read_text())['items']:
        apply(resource)
    config = {'apiVersion': 'v1', 'kind': 'ConfigMap', 'metadata': {'name': 'showroom-guidellm-runner', 'namespace': namespace,
              'labels': {'app.kubernetes.io/part-of': OWNER, 'app.kubernetes.io/component': 'guidellm-load'}},
              'data': {'runner.py': (COMPONENT / 'runner.py').read_text()}}
    apply(config)
    live = get('job', name, namespace)
    owned(live)
    if live:
        if live.get('status', {}).get('completionTime') or live.get('status', {}).get('failed'):
            raise ValueError('Existing Job is finished; keep its evidence and use a new Job name for a new run')
    else:
        job['spec']['activeDeadlineSeconds'] = int(remaining) + 30
        apply(job)
    pods = json.loads(oc('get', 'pods', '-n', namespace, '-l', 'job-name=' + name, '-o', 'json'))['items']
    running = [pod for pod in pods if pod.get('status', {}).get('phase') == 'Running']
    if len(running) != 1:
        print(json.dumps(dict(manifest, status='DEPLOYED_WAITING', next_action='Rerun --apply when the owned CPU pod is Running')))
        return
    pod = running[0]['metadata']['name']
    # A checksum verifies each transfer before the ready marker releases traffic.
    upload = ('import sys,gzip,pathlib,hashlib; data=gzip.decompress(sys.stdin.buffer.read());'
              'assert hashlib.sha256(data).hexdigest()==sys.argv[2];'
              'p=pathlib.Path("/results/tokenizer");p.mkdir(exist_ok=True);'
              '(p/sys.argv[1]).write_bytes(data)')
    ready = oc('exec', '-n', namespace, pod, '--', 'python', '-c',
               'from pathlib import Path;print(Path("/results/tokenizer/.ready").exists())').decode().strip()
    if ready != 'True':
        for name, blob in blobs.items():
            oc('exec', '-i', '-n', namespace, pod, '--', 'python', '-c', upload, name,
               hashlib.sha256(blob).hexdigest(), data=gzip.compress(blob))
    control = json.dumps({'max_rate': args.max_rate})
    oc('exec', '-n', namespace, pod, '--', 'python', '-c',
       'from pathlib import Path;import sys,os;Path("/results/control.json.tmp").write_text(sys.argv[1]);os.replace("/results/control.json.tmp","/results/control.json");Path("/results/tokenizer/.ready").touch()', control)
    print(json.dumps(dict(manifest, status='RUNNING', pod=pod, credential_expires_at=expiry.isoformat())))


if __name__ == '__main__':
    try:
        main()
    except (ValueError, KeyError, OSError, RuntimeError, subprocess.TimeoutExpired) as error:
        print(json.dumps({'status': 'BLOCKED', 'reason': str(error)}), file=sys.stderr)
        sys.exit(2)
