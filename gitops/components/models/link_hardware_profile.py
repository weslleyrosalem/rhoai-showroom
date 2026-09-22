#!/usr/bin/env python3
"""Link an owned live deployment to an exactly compatible native hardware profile.

PLAN is read-only. APPLY changes only native profile annotations after verifying
per-replica defaults and scheduling constraints. No serving spec is changed.
"""
import argparse
from decimal import Decimal
import datetime as dt
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time

import link_registry_deployment as link
import register_model as registry

PROFILE_KIND = 'hardwareprofiles.infrastructure.opendatahub.io'
PREFIX = 'opendatahub.io/hardware-profile-'


def quantity(value):
    match = re.fullmatch(r'([0-9]+(?:\.[0-9]+)?)(m|Ki|Mi|Gi|Ti|K|M|G|T)?', str(value))
    if not match:
        raise ValueError('Unsupported resource quantity; review compatibility manually')
    scales = {'m': Decimal('.001'), 'Ki': 1024, 'Mi': 1024**2, 'Gi': 1024**3,
              'Ti': 1024**4, 'K': 1000, 'M': 1000**2, 'G': 1000**3, 'T': 1000**4}
    return Decimal(match[1]) * scales.get(match[2], 1)


def validate(model, profile, candidate):
    for resource in (model, profile):
        if resource['metadata'].get('labels', {}).get('app.kubernetes.io/part-of') != registry.OWNER:
            raise ValueError('The model and profile must both belong to this showroom')
    if (model['spec']['model']['uri'] != candidate['uri']
        or profile['metadata']['name'] != candidate['hardware_profile']):
        raise ValueError('The candidate immutable URI and hardware profile must match')
    if profile['metadata'].get('annotations', {}).get('opendatahub.io/disabled') != 'false':
        raise ValueError('The hardware profile must be explicitly enabled')
    annotations = model['metadata'].get('annotations', {})
    for suffix, value in [('name', profile['metadata']['name']), ('namespace', profile['metadata']['namespace'])]:
        if annotations.get(PREFIX + suffix) not in (None, value):
            raise ValueError('Conflicting existing hardware profile association')
    template = model['spec']['template']
    if len(template['containers']) != 1 or template['containers'][0]['name'] != 'main':
        raise ValueError('This bounded helper expects one main model container per replica')
    resources = template['containers'][0]['resources']
    identifiers = profile['spec']['identifiers']
    expected = {item['identifier']: quantity(item['defaultCount']) for item in identifiers}
    for section in ('requests', 'limits'):
        actual = {key: quantity(value) for key, value in resources[section].items()}
        if actual != expected:
            raise ValueError('Per-replica resources differ from the profile defaults')
    scheduling = profile['spec'].get('scheduling', {})
    if scheduling.get('type') != 'Node':
        raise ValueError('This helper only links a directly scheduled Node profile')
    required = scheduling['node']
    if any(template.get('nodeSelector', {}).get(key) != value for key, value in required.get('nodeSelector', {}).items()):
        raise ValueError('The deployment does not satisfy the profile node selectors')
    if sorted(template.get('tolerations', []), key=lambda v: json.dumps(v, sort_keys=True)) != sorted(
            required.get('tolerations', []), key=lambda v: json.dumps(v, sort_keys=True)):
        raise ValueError('Deployment tolerations differ from the profile')
    return {'annotations': {PREFIX + 'name': profile['metadata']['name'],
                            PREFIX + 'namespace': profile['metadata']['namespace'],
                            PREFIX + 'resource-version': profile['metadata']['resourceVersion']}}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--expected-server', required=True)
    parser.add_argument('--expected-user', required=True)
    parser.add_argument('--evidence', type=Path)
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    if registry.oc('whoami', '--show-server') != args.expected_server or registry.oc('whoami') != args.expected_user:
        raise ValueError('Unexpected cluster or identity')
    candidate = registry.validate_candidate(json.loads((Path(__file__).parent / 'registry/qwen-4b-candidate.json').read_text()))
    model = registry.resource(link.KIND, 'aurora-qwen-4b', 'ai-showroom')
    profile = registry.resource(PROFILE_KIND, candidate['hardware_profile'], 'ai-showroom')
    desired = validate(model, profile, candidate)
    before = link.snapshot(model, 'ai-showroom', 'aurora-qwen-4b')
    operations = link.metadata_patch(model, desired)
    report = {'mode': 'APPLY' if args.apply else 'PLAN', 'status': 'PLAN',
              'timestamp': dt.datetime.now(dt.timezone.utc).isoformat(),
              'profile': profile['metadata']['name'], 'profile_namespace': profile['metadata']['namespace'],
              'profile_uid': profile['metadata']['uid'], 'profile_resource_version': profile['metadata']['resourceVersion'],
              'metadata_changes': len(operations) - 2,
              'per_replica': model['spec']['template']['containers'][0]['resources'],
              'resources_exactly_match_profile_defaults': True,
              'additional_node_selectors': {key: value for key, value in model['spec']['template'].get('nodeSelector', {}).items()
                                          if key not in profile['spec']['scheduling']['node'].get('nodeSelector', {})},
              'existing_affinity_preserved': True, 'before': before}
    if not args.apply:
        print(json.dumps({key: value for key, value in report.items() if key != 'before'}, indent=2))
        return
    if not args.evidence or args.evidence.resolve().is_relative_to(link.ROOT):
        raise ValueError('APPLY requires a new private evidence file outside the repository')
    destination = args.evidence.resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)
    with os.fdopen(os.open(destination, os.O_RDWR | os.O_CREAT | os.O_EXCL, 0o600), 'w+') as output:
        link.save_report(output, report)
        try:
            if registry.resource(PROFILE_KIND, candidate['hardware_profile'], 'ai-showroom')['metadata']['resourceVersion'] != profile['metadata']['resourceVersion']:
                raise ValueError('The profile changed during review; run PLAN again')
            if len(operations) > 2:
                registry.oc('patch', link.KIND, 'aurora-qwen-4b', '-n', 'ai-showroom', '--type=json', '-p', json.dumps(operations), '--dry-run=server', '-o', 'name')
                registry.oc('patch', link.KIND, 'aurora-qwen-4b', '-n', 'ai-showroom', '--type=json', '-p', json.dumps(operations), '-o', 'name')
            report['metadata_patch_applied'] = len(operations) > 2
            link.save_report(output, report)
            time.sleep(15)
            after_model = registry.resource(link.KIND, 'aurora-qwen-4b', 'ai-showroom')
            after_profile = registry.resource(PROFILE_KIND, candidate['hardware_profile'], 'ai-showroom')
            if after_profile['metadata']['resourceVersion'] != profile['metadata']['resourceVersion']:
                raise ValueError('Profile changed during observation; inspect evidence')
            validate(after_model, after_profile, candidate)
            if any(after_model['metadata'].get('annotations', {}).get(key) != value for key, value in desired['annotations'].items()):
                raise ValueError('Native hardware profile annotations did not persist')
            report['after'] = link.snapshot(after_model, 'ai-showroom', 'aurora-qwen-4b')
            if report['after'] != before:
                raise ValueError('Model spec, generation, pod UIDs, or restart counts changed during observation')
            report['status'] = 'PASSED'
            report['unchanged_generation_spec_pods_and_restarts'] = True
            link.save_report(output, report)
        except Exception as error:
            report['status'] = 'REVIEW_REQUIRED'
            report['reason'] = str(error)
            link.save_report(output, report)
            raise
    print(json.dumps({'status': report['status'], 'metadata_changes': report['metadata_changes'],
                      'unchanged_generation_spec_pods_and_restarts': True}, indent=2))


if __name__ == '__main__':
    try:
        main()
    except (ValueError, RuntimeError, KeyError, OSError, subprocess.TimeoutExpired) as error:
        print(json.dumps({'status': 'BLOCKED', 'reason': str(error)}), file=sys.stderr)
        sys.exit(2)
