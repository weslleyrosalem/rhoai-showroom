#!/usr/bin/env python3
"""Provision a short-lived MaaS key into an owned Secret without printing it.

Read-only unless --apply. Uses the current oc identity and the cluster Gateway.
Private key files remain outside this repository. Does not revoke older keys.
"""
import argparse
import datetime as dt
import json
import os
from pathlib import Path
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request

REPO = Path(__file__).resolve().parents[4]
OWNER = 'rhoai-showroom'

class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None

def oc(*args):
    result = subprocess.run(['oc', '--request-timeout=30s', *args], capture_output=True, text=True)
    if result.returncode:
        raise RuntimeError('OpenShift request failed; credential-bearing output suppressed')
    return result.stdout.strip()

def get(kind, name, namespace):
    return json.loads(oc('get', kind, name, '-n', namespace, '-o', 'json'))

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--expected-server', required=True)
    p.add_argument('--expected-user', default='aiadmin')
    p.add_argument('--subscription', default='showroom-standard')
    p.add_argument('--namespace', default='ai-showroom')
    p.add_argument('--secret-name', default='showroom-maas-key')
    p.add_argument('--model-id', required=True)
    p.add_argument('--key-file', type=Path, required=True)
    p.add_argument('--apply', action='store_true')
    args = p.parse_args()
    try:
        if oc('whoami', '--show-server') != args.expected_server or oc('whoami') != args.expected_user:
            raise ValueError('Unexpected OpenShift server or identity')
        key_file = args.key_file.expanduser().absolute()
        if key_file.is_symlink() or key_file.resolve().is_relative_to(REPO):
            raise ValueError('Key file must be outside the repository and must not be a symlink')
        gateway = get('gateway', 'maas-default-gateway', 'openshift-ingress')
        hosts = {x['hostname'] for x in gateway['spec']['listeners'] if x.get('hostname') and x.get('protocol') == 'HTTPS'}
        if len(hosts) != 1 or '*' in next(iter(hosts)):
            raise ValueError('Expected exactly one explicit HTTPS gateway hostname')
        host = next(iter(hosts))
        parsed = urllib.parse.urlsplit('https://' + host)
        if parsed.hostname != host or parsed.username or parsed.password or parsed.path:
            raise ValueError('Invalid gateway hostname')
        base = 'https://' + host
        subscription = get('maassubscription', args.subscription, 'models-as-a-service')
        if subscription.get('status', {}).get('phase') != 'Active':
            raise ValueError('Subscription must be Active before key issuance')
        refs = subscription['spec'].get('modelRefs', [])
        allowed = {'publishers/' + x['namespace'] + '/models/' + x['name'] for x in refs}
        if args.model_id not in allowed:
            raise ValueError('Model does not belong to the selected subscription')
        raw = oc('get', 'secret', args.secret_name, '-n', args.namespace, '--ignore-not-found', '-o', 'json')
        if raw and json.loads(raw)['metadata'].get('labels', {}).get('app.kubernetes.io/part-of') != OWNER:
            raise ValueError('Refusing to replace a Secret not owned by this showroom')
        if not args.apply:
            print(json.dumps({'status': 'PLAN', 'subscription': args.subscription, 'secret': args.namespace + '/' + args.secret_name, 'duration': '24h'}))
            return 0
        if key_file.exists():
            if key_file.stat().st_mode & 0o077:
                raise ValueError('Existing key file permissions must be 0600')
            credential = json.loads(key_file.read_text())
            if credential.get('subscription') != args.subscription:
                raise ValueError('Existing key belongs to a different subscription')
            expires = dt.datetime.fromisoformat(credential['expiresAt'].replace('Z', '+00:00'))
            if expires <= dt.datetime.now(dt.timezone.utc) + dt.timedelta(minutes=5):
                raise ValueError('Key expired or expires soon; supply a new private filename to rotate')
        else:
            key_file.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
            if key_file.parent.stat().st_mode & 0o077:
                raise ValueError('Private key directory permissions must be 0700')
            name = args.secret_name + '-' + dt.datetime.now(dt.timezone.utc).strftime('%Y%m%dT%H%M%S')
            body = json.dumps({'name': name, 'expiresIn': '24h', 'subscription': args.subscription}).encode()
            req = urllib.request.Request(base + '/maas-api/v1/api-keys', data=body, headers={'Authorization': 'Bearer ' + oc('whoami', '-t'), 'Content-Type': 'application/json'})
            with urllib.request.build_opener(NoRedirect).open(req, timeout=60) as response:
                credential = json.load(response)
            if not all(credential.get(k) for k in ('key', 'id', 'expiresAt')):
                raise ValueError('MaaS response omitted required credential fields')
            credential.update(subscription=args.subscription, name=name)
            fd = os.open(key_file, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(fd, 'w') as f:
                json.dump(credential, f)
        secret = {'apiVersion': 'v1', 'kind': 'Secret', 'metadata': {'name': args.secret_name, 'namespace': args.namespace, 'labels': {'app.kubernetes.io/part-of': OWNER}, 'annotations': {'showroom.openshift.ai/subscription': args.subscription, 'showroom.openshift.ai/expires-at': credential['expiresAt']}}, 'type': 'Opaque', 'stringData': {'api-key': credential['key'], 'base-url': base + '/v1', 'model-id': args.model_id}}
        # stdin avoids shell history/argv; server-side avoids last-applied Secret copies.
        result = subprocess.run(['oc', 'apply', '--server-side', '--field-manager=rhoai-showroom-runtime', '-f', '-', '--request-timeout=30s'], input=json.dumps(secret), capture_output=True, text=True)
        if result.returncode:
            raise RuntimeError('Secret apply failed; private key retained for a safe retry')
        print(json.dumps({'status': 'APPLIED', 'subscription': args.subscription, 'secret': args.namespace + '/' + args.secret_name, 'expires_at': credential['expiresAt'], 'credential_logged': False}))
        return 0
    except (ValueError, KeyError, OSError, RuntimeError) as exc:
        print(json.dumps({'status': 'BLOCKED', 'reason': str(exc)}), file=sys.stderr)
        return 2

if __name__ == '__main__':
    sys.exit(main())
