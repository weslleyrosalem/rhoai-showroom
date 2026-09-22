#!/usr/bin/env python3
"""Associate an existing owned LLMInferenceService with its exact registry artifact.

PLAN is the default. APPLY changes only native registry metadata, never the
serving spec, registry records, lifecycle, permissions, or validation scores.
"""
import argparse
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time

import register_model as registry

ROOT = Path(__file__).resolve().parents[3]
PREFIX = 'modelregistry.opendatahub.io/'
KIND = 'llminferenceservices.serving.kserve.io'


def connection(args):
    instance = registry.resource('modelregistries.modelregistry.opendatahub.io', args.registry, args.registry_namespace)
    route = registry.resource('route', args.registry + '-https', args.registry_namespace)
    domain = registry.resource('ingress.config.openshift.io', 'cluster')['spec']['domain']
    host = route['spec']['host']
    if (not any(c.get('type') == 'Available' and c.get('status') == 'True'
                for c in instance.get('status', {}).get('conditions', []))
        or not instance['spec'].get('kubeRBACProxy')
        or route['spec'].get('tls', {}).get('termination') != 'reencrypt'
        or route['spec'].get('to', {}).get('name') != args.registry
        or not any(owner.get('uid') == instance['metadata']['uid'] for owner in route['metadata'].get('ownerReferences', []))
        or not re.fullmatch(r'[a-zA-Z0-9.-]+', host) or not host.endswith('.' + domain)):
        raise ValueError('Require an Available registry and its owned authenticated reencrypt Route in this cluster')
    return registry.RegistryClient('https://' + host, registry.oc('whoami', '-t'))


def discover(client, candidate):
    result = registry.onboard(client, candidate, False)
    if any(not re.fullmatch(r'[1-9][0-9]*', str(item['id'])) for item in result.values()):
        raise ValueError('Onboard the exact pinned candidate before linking a deployment')
    version = client.request(registry.API + '/model_versions/' + result['model_version']['id'])
    if version.get('customProperties', {}).get('showroom.lifecycle', {}).get('string_value') != 'candidate':
        raise ValueError('This helper only associates an existing candidate; it cannot promote a model')
    return result, version


def association(candidate, registry_name, discovered):
    return {
        'labels': {
            PREFIX + 'name': registry_name,
            PREFIX + 'registered-model-id': discovered['registered_model']['id'],
            PREFIX + 'model-version-id': discovered['model_version']['id'],
        },
        'annotations': {PREFIX + 'model-version-name': candidate['version_name']},
    }


def validate_deployment(model, candidate, desired):
    metadata = model['metadata']
    if metadata.get('deletionTimestamp'):
        raise ValueError('The deployment is being deleted')
    if metadata.get('labels', {}).get('app.kubernetes.io/part-of') != registry.OWNER:
        raise ValueError('The deployment is not owned by this showroom')
    if model.get('spec', {}).get('model', {}).get('uri') != candidate['uri']:
        raise ValueError('The live deployment URI differs from the immutable registered artifact')
    for section, values in desired.items():
        for key, value in values.items():
            existing = metadata.get(section, {}).get(key)
            if existing is not None and existing != value:
                raise ValueError('Conflicting existing registry association: ' + key)
    if not any(c.get('type') == 'Ready' and c.get('status') == 'True'
               for c in model.get('status', {}).get('conditions', [])):
        raise ValueError('The existing deployment must be Ready before linking it')


def snapshot(model, namespace, name):
    pods = json.loads(registry.oc('get', 'pods', '-n', namespace, '-l',
                                'app.kubernetes.io/name=' + name, '-o', 'json'))['items']
    if not pods or any(p['metadata'].get('deletionTimestamp') or not any(
            c.get('type') == 'Ready' and c.get('status') == 'True'
            for c in p.get('status', {}).get('conditions', [])) for p in pods):
        raise ValueError('All selected model and scheduler pods must be present and Ready')
    return {
        'uid': model['metadata']['uid'],
        'generation': model['metadata']['generation'],
        'spec_sha256': hashlib.sha256(json.dumps(model['spec'], sort_keys=True).encode()).hexdigest(),
        'pods': sorted([{'name': p['metadata']['name'], 'uid': p['metadata']['uid'],
                        'restarts': {c['name']: c.get('restartCount', 0)
                                     for c in p.get('status', {}).get('containerStatuses', [])}}
                        for p in pods], key=lambda p: p['name']),
    }


def metadata_patch(model, desired):
    metadata = model['metadata']
    operations = [{'op': 'test', 'path': '/metadata/uid', 'value': metadata['uid']},
                  {'op': 'test', 'path': '/metadata/resourceVersion', 'value': metadata['resourceVersion']}]
    for section, values in desired.items():
        if section not in metadata:
            operations.append({'op': 'add', 'path': '/metadata/' + section, 'value': {}})
        for key, value in values.items():
            if metadata.get(section, {}).get(key) != value:
                escaped = key.replace('~', '~0').replace('/', '~1')
                operations.append({'op': 'add', 'path': '/metadata/' + section + '/' + escaped, 'value': value})
    return operations


def save_report(descriptor, report):
    descriptor.seek(0)
    json.dump(report, descriptor, indent=2)
    descriptor.write('\n')
    descriptor.truncate()
    descriptor.flush()
    os.fsync(descriptor.fileno())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--candidate', type=Path, default=Path(__file__).parent / 'registry/qwen-4b-candidate.json')
    parser.add_argument('--registry', default='aurora-registry')
    parser.add_argument('--registry-namespace', default='rhoai-model-registries')
    parser.add_argument('--deployment', default='aurora-qwen-4b')
    parser.add_argument('--deployment-namespace', default='ai-showroom')
    parser.add_argument('--expected-server', required=True, help='Independently verified intended cluster URL')
    parser.add_argument('--expected-user', required=True, help='Independently verified intended identity')
    parser.add_argument('--evidence', type=Path, help='Required for APPLY: new private report path outside this repository')
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    if registry.oc('whoami', '--show-server') != args.expected_server or registry.oc('whoami') != args.expected_user:
        raise ValueError('Current cluster or identity differs from the explicit guard')
    for value in (args.registry, args.registry_namespace, args.deployment, args.deployment_namespace):
        if not re.fullmatch(r'[a-z0-9](?:[-a-z0-9.]*[a-z0-9])?', value):
            raise ValueError('Resource names must be Kubernetes DNS names')
    candidate = registry.validate_candidate(json.loads(args.candidate.read_text()))
    client = connection(args)
    discovered, version = discover(client, candidate)
    desired = association(candidate, args.registry, discovered)
    model = registry.resource(KIND, args.deployment, args.deployment_namespace)
    validate_deployment(model, candidate, desired)
    before = snapshot(model, args.deployment_namespace, args.deployment)
    operations = metadata_patch(model, desired)
    report = {'status': 'PLAN', 'observed_at': dt.datetime.now(dt.timezone.utc).isoformat(),
              'deployment': args.deployment, 'namespace': args.deployment_namespace,
              'registry': args.registry, 'discovered': discovered, 'metadata': desired, 'before': before,
              'lifecycle': 'candidate', 'registry_records_modified': False,
              'scope': 'Native deployment association only. No promotion, model-quality approval, or serving-spec change.'}
    if not args.apply:
        print(json.dumps({'mode': 'PLAN', 'metadata_changes': len(operations) - 2,
                          'registry': args.registry, 'deployment': args.deployment,
                          'association': desired, 'ready_pods': len(before['pods'])}, indent=2))
        return
    if not args.evidence or args.evidence.resolve().is_relative_to(ROOT):
        raise ValueError('APPLY requires a new private evidence path outside the repository')
    destination = args.evidence.resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)
    descriptor = os.open(destination, os.O_RDWR | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, 'w+') as output:
        save_report(output, report)  # Durable pre-mutation observation, without credentials.
        try:
            latest, current_version = discover(client, candidate)
            if latest != discovered or current_version != version:
                raise ValueError('Registry records changed during review; run PLAN again')
            if len(operations) > 2:
                registry.oc('patch', KIND, args.deployment, '-n', args.deployment_namespace,
                            '--type=json', '-p', json.dumps(operations), '--dry-run=server', '-o', 'name')
                registry.oc('patch', KIND, args.deployment, '-n', args.deployment_namespace,
                            '--type=json', '-p', json.dumps(operations), '-o', 'name')
            report['metadata_patch_applied'] = len(operations) > 2
            save_report(output, report)
            # Observe bounded controller reconciliation without sending inference or restarting anything.
            time.sleep(15)
            after_model = registry.resource(KIND, args.deployment, args.deployment_namespace)
            validate_deployment(after_model, candidate, desired)
            if any(after_model['metadata'].get(section, {}).get(key) != value
                   for section, values in desired.items() for key, value in values.items()):
                raise ValueError('The expected registry association did not persist')
            report['after'] = snapshot(after_model, args.deployment_namespace, args.deployment)
            report['unchanged_generation_spec_pods_and_restarts'] = before == report['after']
            if not report['unchanged_generation_spec_pods_and_restarts']:
                raise ValueError('Deployment or pods changed during observation; inspect evidence before continuing')
            final_discovered, final_version = discover(client, candidate)
            if final_discovered != discovered or final_version != version:
                raise ValueError('Registry records changed during observation; association did not approve these changes')
            report['status'] = 'PASSED'
            report['completed_at'] = dt.datetime.now(dt.timezone.utc).isoformat()
            save_report(output, report)
        except Exception as error:
            report['status'] = 'REVIEW_REQUIRED'
            report['reason'] = str(error)
            save_report(output, report)
            raise
    print(json.dumps({'mode': 'APPLY', 'status': report['status'],
                      'metadata_changes': len(operations) - 2, 'lifecycle': 'candidate',
                      'unchanged_generation_spec_pods_and_restarts': True,
                      'observed_ready_pods': len(before['pods'])}, indent=2))


if __name__ == '__main__':
    try:
        main()
    except (ValueError, RuntimeError, KeyError, OSError, subprocess.TimeoutExpired) as error:
        print(json.dumps({'status': 'BLOCKED', 'reason': str(error)}), file=sys.stderr)
        sys.exit(2)
