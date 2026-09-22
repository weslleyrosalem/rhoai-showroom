#!/usr/bin/env python3
"""Measure native Qwen protocol/tool/routing acceptance and record owned registry evidence.

Default PLAN reads only. --apply performs bounded inference, saves a private
report, and updates runtime metadata only. Safety/performance and lifecycle are
preserved. This is a runtime compatibility check, never a promotion workflow.
"""
import argparse
import datetime as dt
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import subprocess
import sys
import register_model as registry

ROOT = Path(__file__).resolve().parents[3]
spec = importlib.util.spec_from_file_location('inference_probe', ROOT / 'scripts/inference_probe.py')
probe = importlib.util.module_from_spec(spec)
spec.loader.exec_module(probe)
DESCRIPTION = 'Pinned candidate. Runtime protocol evidence is recorded separately; safety and performance remain independent acceptance gates.'


def connection(args):
    instance = registry.resource('modelregistries.modelregistry.opendatahub.io', 'aurora-registry', 'rhoai-model-registries')
    route = registry.resource('route', 'aurora-registry-https', 'rhoai-model-registries')
    domain = registry.resource('ingress.config.openshift.io', 'cluster')['spec']['domain']
    host = route['spec']['host']
    if (not instance['spec'].get('kubeRBACProxy') or route['spec'].get('tls', {}).get('termination') != 'reencrypt'
        or route['spec'].get('to', {}).get('name') != 'aurora-registry'
        or not any(item.get('uid') == instance['metadata']['uid'] for item in route['metadata'].get('ownerReferences', []))
        or not re.fullmatch(r'[a-zA-Z0-9.-]+', host) or not host.endswith('.' + domain)):
        raise ValueError('Registry must expose its owned authenticated reencrypt Route in this cluster')
    return registry.RegistryClient('https://' + host, registry.oc('whoami', '-t'))


def runtime_properties(properties, evidence_hash, timestamp):
    if properties.get('showroom.owner', {}).get('string_value') != registry.OWNER:
        raise ValueError('Registry version is not showroom-owned')
    if properties.get('showroom.lifecycle', {}).get('string_value') != 'candidate':
        raise ValueError('This helper only records runtime evidence for a candidate')
    changed = dict(properties)
    changed.update(registry.properties({
        'showroom.runtime_validation': 'PASSED_PROTOCOL_TOOL_AND_ROUTING',
        'showroom.runtime_evidence_sha256': evidence_hash,
        'showroom.runtime_evidence_at': timestamp,
        'showroom.runtime_evidence_scope': 'Native authenticated inference, structured get_stock(AS-001), endpoint-picker counter. No safety approval or performance comparison.'}))
    return changed


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--expected-server', required=True)
    parser.add_argument('--expected-user', required=True)
    parser.add_argument('--evidence', type=Path, required=True, help='New private report path outside the repository')
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    if registry.oc('whoami', '--show-server') != args.expected_server or registry.oc('whoami') != args.expected_user:
        raise ValueError('Unexpected cluster or identity')
    destination = args.evidence.resolve()
    if destination.is_relative_to(ROOT) or destination.exists():
        raise ValueError('Use a new private evidence path outside the repository')
    candidate = registry.validate_candidate(json.loads((Path(__file__).parent / 'registry/qwen-4b-candidate.json').read_text()))
    client = connection(args)
    onboard = registry.onboard(client, candidate, False)
    identifier = onboard['model_version']['id']
    if identifier == 'PLAN':
        raise ValueError('Onboard the pinned candidate before recording runtime evidence')
    version = client.request(registry.API + '/model_versions/' + identifier)
    properties = version.get('customProperties', {})
    runtime_properties(properties, 'PLAN', 'PLAN')
    model = registry.resource('llminferenceservice', 'aurora-qwen-4b', 'ai-showroom')
    if (model['metadata'].get('labels', {}).get('app.kubernetes.io/part-of') != registry.OWNER
        or model['spec']['model']['uri'] != candidate['uri']):
        raise ValueError('Live model ownership and immutable revision must match the candidate')
    pods = json.loads(registry.oc('get', 'pods', '-n', 'ai-showroom', '-l',
        'app.kubernetes.io/name=aurora-qwen-4b,kserve.io/component=workload', '-o', 'json'))['items']
    ready = [pod for pod in pods if not pod['metadata'].get('deletionTimestamp') and any(
        c['type'] == 'Ready' and c['status'] == 'True' for c in pod.get('status', {}).get('conditions', []))]
    resolved_images = []
    for pod in ready:
        requested = next((c.get('image') for c in pod['spec']['containers'] if c['name'] == 'main'), '')
        resolved = next((c.get('imageID', '') for c in pod['status'].get('containerStatuses', []) if c['name'] == 'main'), '')
        # Kubelet reports the platform image digest for a pinned multi-platform index.
        # Preserve both values instead of comparing two different OCI digest levels.
        if requested != candidate['runtime_image'] or not re.search(r'@sha256:[0-9a-f]{64}$', resolved):
            raise ValueError('Ready backends must request the candidate immutable image and report a resolved digest')
        resolved_images.append({'requested': requested, 'resolved': resolved})
    if not ready:
        raise ValueError('No Ready backend is available')
    if not args.apply:
        print(json.dumps({'mode': 'PLAN', 'model_version_id': identifier, 'ready_backends': len(ready),
                          'will_measure': ['native inference', 'automatic structured tool call', 'EPP counter'],
                          'will_preserve': ['candidate lifecycle', 'safety evaluation', 'performance evaluation', 'immutable provenance']}))
        return
    processes = []
    try:
        gateway = probe.forward('service/showroom-inference-maas-gateway-class', 8080, processes)
        picker = probe.forward('deployment/aurora-qwen-4b-kserve-router-scheduler', 9090, processes)
        token = registry.oc('whoami', '-t')
        before = probe.picker_metrics(picker, token)
        body = {'model': 'aurora-qwen-4b', 'max_tokens': 128, 'temperature': 0,
                'messages': [{'role': 'system', 'content': 'Use the inventory tool for stock requests. Never invent stock or execute a purchase.'},
                             {'role': 'user', 'content': 'What is the stock of AS-001?'}],
                'tools': [{'type': 'function', 'function': {'name': 'get_stock', 'description': 'Read current synthetic Aurora Supply stock for an exact SKU.',
                    'parameters': {'type': 'object', 'properties': {'sku': {'type': 'string'}}, 'required': ['sku'], 'additionalProperties': False}}}],
                'tool_choice': 'auto'}
        status, raw, latency = probe.request(gateway, '/ai-showroom/aurora-qwen-4b/v1/chat/completions', token, body)
        response = json.loads(raw) if status == 200 and raw else {}
        calls = response.get('choices', [{}])[0].get('message', {}).get('tool_calls', [])
        after = probe.picker_metrics(picker, token)
        delta = sum(after.values()) - sum(before.values())
        passed = (status == 200 and bool(response.get('usage')) and len(calls) == 1
                  and calls[0]['function']['name'] == 'get_stock'
                  and json.loads(calls[0]['function']['arguments']) == {'sku': 'AS-001'} and delta >= 1)
        evidence = {'status': 'PASSED' if passed else 'FAILED', 'timestamp': dt.datetime.now(dt.timezone.utc).isoformat(),
                    'cluster_server': args.expected_server, 'model_revision': candidate['revision'], 'runtime_image': candidate['runtime_image'],
                    'ready_backends': len(ready), 'resolved_images': resolved_images, 'http_status': status, 'usage': response.get('usage'),
                    'tool_calls': calls, 'client_latency_seconds': latency, 'picker_request_delta': delta,
                    'scope': 'Runtime protocol/tool/routing acceptance only. No model safety, quality, or performance approval.'}
        destination.parent.mkdir(parents=True, exist_ok=True)
        with destination.open('x') as output:
            json.dump(evidence, output, indent=2)
        destination.chmod(0o600)
        if not passed:
            raise ValueError('Runtime acceptance failed; registry was not modified')
        # Re-read immediately before writing so a change during the test is not overwritten.
        current = client.request(registry.API + '/model_versions/' + identifier)
        if current != version:
            raise ValueError('Registry version changed during measurement; review again before updating')
        digest = hashlib.sha256(destination.read_bytes()).hexdigest()
        changes = runtime_properties(properties, digest, evidence['timestamp'])
        updated = client.request(registry.API + '/model_versions/' + identifier,
                                 {'description': DESCRIPTION, 'customProperties': changes}, method='PATCH')
        if updated.get('customProperties') != changes:
            raise RuntimeError('Registry response differs from the reviewed metadata; inspect the version')
        print(json.dumps({'mode': 'APPLY', 'runtime_status': 'PASSED_PROTOCOL_TOOL_AND_ROUTING',
                          'model_version_id': identifier, 'evidence_sha256': digest,
                          'lifecycle': changes['showroom.lifecycle']['string_value'],
                          'safety_evaluation': changes['showroom.safety_evaluation']['string_value'],
                          'performance_evaluation': changes['showroom.performance_evaluation']['string_value']}))
    finally:
        for process in processes:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)


if __name__ == '__main__':
    try:
        main()
    except (ValueError, RuntimeError, KeyError, OSError, subprocess.TimeoutExpired) as error:
        print(json.dumps({'status': 'BLOCKED', 'reason': str(error)}), file=sys.stderr)
        sys.exit(2)
