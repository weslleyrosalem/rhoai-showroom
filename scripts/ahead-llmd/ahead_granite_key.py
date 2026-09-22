#!/usr/bin/env python3
"""Plan or explicitly create/revoke one private, short-lived AHEAD Granite key.

No inference, Kubernetes Secret, or dashboard configuration is changed.
The current oc credential stays in memory and is sent only to the verified
AHEAD HTTPS Gateway. Never display or publish credential.json.
"""
import argparse
import datetime as dt
import json
import os
from pathlib import Path
import re
import ssl
import stat
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
import uuid

REPO = Path(__file__).resolve().parents[2]
TENANT, NAMESPACE = 'ahead', 'ai-tenant-ahead'
MODEL = 'redhataigranite-31-8b-instruct'
MODEL_ID = 'publishers/ahead/models/' + MODEL
SUBSCRIPTION = 'ahead-granite-presenter'
DURATIONS = {'10m': 600, '1h': 3600, '2h': 7200}
ID = re.compile(r'[A-Za-z0-9_-]{1,200}')


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


def oc(*args):
    result = subprocess.run(['oc', '--request-timeout=20s', *args],
                            capture_output=True, text=True, timeout=25)
    if result.returncode:
        raise RuntimeError('OpenShift operation failed; output suppressed.')
    return result.stdout.strip()


def get(kind, name, namespace):
    return json.loads(oc('get', kind, name, '-n', namespace, '-o', 'json'))


def timestamp(value):
    parsed = dt.datetime.fromisoformat(value.replace('Z', '+00:00'))
    if parsed.tzinfo is None:
        raise ValueError('An explicit expiration timezone is required.')
    return parsed.astimezone(dt.timezone.utc)


def gateway_origin(gateway):
    hosts = {item.get('hostname') for item in gateway['spec']['listeners']
             if item.get('protocol') == 'HTTPS' and item.get('port') == 443}
    if len(hosts) != 1:
        raise ValueError('Expected exactly one explicit HTTPS443 Gateway hostname.')
    host = next(iter(hosts))
    if (not isinstance(host, str) or len(host) > 253
            or not re.fullmatch(r'[A-Za-z0-9](?:[A-Za-z0-9.-]*[A-Za-z0-9])?', host)
            or '*' in host or '..' in host):
        raise ValueError('Invalid AHEAD Gateway hostname.')
    return 'https://' + host.lower()


def verify_environment(expected_server, expected_user, creating):
    if expected_user != 'aiadmin':
        raise ValueError('This dedicated presenter profile permits only aiadmin.')
    parsed = urllib.parse.urlsplit(expected_server)
    if parsed.scheme != 'https' or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError('Supply the independently verified HTTPS API server.')
    if oc('whoami', '--show-server') != expected_server or oc('whoami') != expected_user:
        raise ValueError('Unexpected OpenShift server or identity.')
    ref = get('maasmodelref', MODEL, TENANT)
    if ref['spec'] != {'modelRef': {'kind': 'LLMInferenceService', 'name': MODEL}, 'tenantRef': TENANT}:
        raise ValueError('Granite MaaS reference differs from the intended tenant/model.')
    subscription = get('maassubscription', SUBSCRIPTION, NAMESPACE)
    expected = {'modelRefs': [{'name': MODEL, 'namespace': TENANT,
                 'tokenRateLimits': [{'limit': 20000, 'window': '1m'}]}],
                'owner': {'users': ['aiadmin']}, 'priority': 60}
    if subscription['spec'] != expected:
        raise ValueError('Presenter subscription no longer matches the reviewed scope.')
    policy = get('maasauthpolicy', 'ahead-granite-presenter-access', NAMESPACE)
    if policy['spec'] != {'modelRefs': [{'name': MODEL, 'namespace': TENANT}],
                          'subjects': {'users': ['aiadmin']}}:
        raise ValueError('Presenter access policy no longer matches the reviewed scope.')
    if creating:
        if subscription.get('status', {}).get('phase') != 'Active':
            raise ValueError('The presenter subscription must be Active for issuance.')
        if not any(c.get('type') == 'Ready' and c.get('status') == 'True'
                   for c in ref.get('status', {}).get('conditions', [])):
            raise ValueError('Granite MaaS reference must be Ready for issuance.')
    route = get('httproute', MODEL + '-kserve-route', TENANT)
    parents = route['spec'].get('parentRefs', [])
    if len(parents) != 1 or parents[0].get('name') != TENANT or parents[0].get('namespace') != 'openshift-ingress':
        raise ValueError('The Granite route must reference only the AHEAD Gateway.')
    return gateway_origin(get('gateway', TENANT, 'openshift-ingress'))


def private_path(value, existing=False):
    path = value.expanduser().absolute()
    for item in (path, *path.parents):
        if item.is_symlink() or (item / '.git').exists():
            raise ValueError('Use a nonsymlink path outside every Git checkout.')
    if REPO == path or REPO in path.parents:
        raise ValueError('Credentials must stay outside the public repository.')
    if not path.parent.is_dir():
        raise ValueError('The chosen private directory must have an existing parent.')
    if existing:
        info = path.lstat()
        if not stat.S_ISDIR(info.st_mode) or info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) != 0o700:
            raise ValueError('The private directory must be owned by you with mode0700.')
    elif path.exists():
        raise ValueError('Choose a NEW private directory; credentials are never overwritten.')
    return path


def request(origin, token, method, path, body=None):
    # Paths originate only from the fixed management API and a validated key ID.
    if not (path == '/maas-api/v1/api-keys' or
            re.fullmatch(r'/maas-api/v1/api-keys/[A-Za-z0-9_-]{1,200}', path)):
        raise ValueError('Unexpected management API path.')
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect(),
                urllib.request.HTTPSHandler(context=ssl.create_default_context()))
    req = urllib.request.Request(origin + path, method=method,
          data=None if body is None else json.dumps(body).encode(),
          headers={'Authorization': 'Bearer ' + token, 'Content-Type': 'application/json'})
    try:
        with opener.open(req, timeout=25) as response:
            raw = response.read(65537)
            if len(raw) > 65536:
                raise ValueError('Oversized management response.')
            value = json.loads(raw) if raw else {}
            if not isinstance(value, dict):
                raise ValueError('Unexpected management response.')
            return response.status, value
    except urllib.error.HTTPError as error:
        # Do not read or print an error body, URL, credential, or header.
        code = error.code
        error.close()
        raise RuntimeError('Management API rejected the request: HTTP' + str(code)) from None
    except (urllib.error.URLError, TimeoutError):
        raise RuntimeError('Verified HTTPS management request failed; details suppressed.') from None


def write_file(fd, value):
    with os.fdopen(fd, 'w') as stream:
        json.dump(value, stream, indent=2, allow_nan=False)
        stream.write('\n'); stream.flush(); os.fsync(stream.fileno())


def create(args, origin):
    directory = private_path(args.private_dir)
    if not args.apply:
        print('PLAN: create one AHEAD Granite presenter key; requested lifetime ' + args.expires_in + '. No key created.')
        return
    os.mkdir(directory, 0o700)
    folder = os.open(directory, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    fd = os.open('credential.json', os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_NOFOLLOW, 0o600, dir_fd=folder)
    try:
        name = 'ahead-granite-presenter-' + uuid.uuid4().hex
        token = oc('whoami', '-t')
        status, value = request(origin, token, 'POST', '/maas-api/v1/api-keys',
                 {'name': name, 'expiresIn': args.expires_in, 'subscription': SUBSCRIPTION})
        if status != 201 or not ID.fullmatch(value.get('id', '')):
            raise ValueError('Key creation did not return the expected identity.')
        # Save only allowlisted fields, including the ID needed for cleanup.
        credential = {'schema_version': 1, 'tenant': TENANT, 'subscription': SUBSCRIPTION,
                      'owner': 'aiadmin', 'expected_server': args.expected_server,
                      'gateway_origin': origin, 'base_url': origin + '/v1', 'model_id': MODEL_ID,
                      'id': value['id'], 'name': name, 'key': value.get('key'),
                      'expires_at': value.get('expiresAt')}
        # Persist the one-time response before subsequent validation, so a key
        # with an unexpected server response still has a recoverable identity.
        write_file(fd, credential); fd = None
        key = credential['key']
        if not isinstance(key, str) or not key.startswith('sk-oai-') or any(c.isspace() for c in key):
            raise ValueError('Unexpected credential response; retain the private file for revocation.')
        remaining = (timestamp(credential['expires_at']) - dt.datetime.now(dt.timezone.utc)).total_seconds()
        if not 0 < remaining <= DURATIONS[args.expires_in] + 60:
            raise ValueError('Unexpected expiration; retain the private file and revoke the key.')
        print('Credential saved privately: ' + str(directory / 'credential.json'))
        print('Key expiration: ' + credential['expires_at'])
    finally:
        if fd is not None:
            os.close(fd)
        os.close(folder)


def revoke(args, origin):
    path = args.credential_file.expanduser().absolute()
    if path.name != 'credential.json':
        raise ValueError('Select the credential.json file created by this helper.')
    directory = private_path(path.parent, existing=True)
    folder = os.open(directory, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        fd = os.open('credential.json', os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=folder)
        with os.fdopen(fd, 'r') as stream:
            info = os.fstat(stream.fileno())
            if (not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid()
                    or stat.S_IMODE(info.st_mode) != 0o600 or info.st_size > 65536):
                raise ValueError('Credential file must be a private, owned, regular0600 file.')
            value = json.load(stream)
        expected = {'tenant': TENANT, 'subscription': SUBSCRIPTION, 'owner': 'aiadmin',
                    'expected_server': args.expected_server, 'gateway_origin': origin,
                    'base_url': origin + '/v1', 'model_id': MODEL_ID}
        if any(value.get(k) != v for k, v in expected.items()) or not ID.fullmatch(value.get('id', '')):
            raise ValueError('Stored credential does not match this exact cluster, tenant, and model.')
        if not args.apply:
            print('PLAN: revoke only the matching saved AHEAD Granite key. No key revoked.')
            return
        token = oc('whoami', '-t')
        endpoint = '/maas-api/v1/api-keys/' + value['id']
        status, metadata = request(origin, token, 'GET', endpoint)
        if (status != 200 or metadata.get('id') != value['id'] or metadata.get('name') != value.get('name')
                or metadata.get('username') != 'aiadmin' or metadata.get('subscription') != SUBSCRIPTION):
            raise ValueError('Remote key metadata differs; nothing was revoked.')
        if metadata.get('status') != 'revoked':
            status, _ = request(origin, token, 'DELETE', endpoint)
            if status not in (200, 204):
                raise ValueError('Revocation did not return a success status.')
        print('Matching AHEAD Granite key revoked or already revoked.')
        print('A successful revocation response does not prove immediate cache rejection; the observed auth cache is60 seconds.')
    finally:
        os.close(folder)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='action', required=True)
    for name in ('create', 'revoke'):
        command = commands.add_parser(name)
        command.add_argument('--expected-server', required=True)
        command.add_argument('--expected-user', required=True)
        command.add_argument('--apply', action='store_true', help='Perform the explicit operation; otherwise show a read-only plan.')
        if name == 'create':
            command.add_argument('--private-dir', '--private-output', dest='private_dir', type=Path, required=True,
                                 help='A NEW directory outside Git; creates credential.json with mode0600.')
            command.add_argument('--expires-in', choices=DURATIONS, default='1h')
        else:
            command.add_argument('--credential-file', type=Path, required=True)
    args = parser.parse_args()
    try:
        origin = verify_environment(args.expected_server, args.expected_user, args.action == 'create')
        (create if args.action == 'create' else revoke)(args, origin)
        return 0
    except Exception as error:
        # Even unexpected parser/transport failures must not print secret-bearing
        # bodies, traceback locals, URLs, or exception text.
        print('BLOCKED (' + type(error).__name__ + '). No credential was printed. Retain any private file; inspect tenant key metadata before retrying an uncertain creation.', file=sys.stderr)
        return 2


if __name__ == '__main__':
    sys.exit(main())
