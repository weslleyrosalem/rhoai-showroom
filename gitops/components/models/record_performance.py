#!/usr/bin/env python3
"""Attach measured reference evidence to an existing candidate; never approve it.

PLAN is the default. No inference, deployment, registration, or promotion occurs.
The public report must match its immutable GitHub copy and retained original
measurements. The candidate, artifact URI, live model revision, image index,
and resolved platform digest must agree before metadata can change.
"""
import argparse
import copy
import datetime as dt
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import urllib.request

import register_model as registry
import record_runtime as runtime

ROOT = Path(__file__).resolve().parents[3]
spec = importlib.util.spec_from_file_location('showroom_benchmark', ROOT / 'scripts/benchmark.py')
benchmark = importlib.util.module_from_spec(spec)
spec.loader.exec_module(benchmark)
REPORT_PATH = 'docs/results/engine-ab-20260922.json'
RUNTIME_MANIFEST = 'gitops/components/models/qwen-4b-private'
PUBLIC_REPOSITORY = 'weslleyrosalem/rhoai-showroom'
STATUS = 'MEASURED_REFERENCE_ONLY'
SCOPE = ('One repetition on the same physical L40S and temporary Pod: pinned Qwen4B, BF16, '
         'identical image/resources/tokenizer/template/workload, prefix cache disabled. '
         'Transformers serialized batch-one reference versus vLLM continuous batching; '
         '12 requests at concurrency 1 and 12 at concurrency 2 per engine, 64-token cap. '
         'Historical engine measurements, not the current two-replica gateway path. '
         'No optimized-Transformers, routing, safety, quality, or performance approval claim.')


def matches(pattern, value):
    return isinstance(value, str) and re.fullmatch(pattern, value) is not None


def validate_report(report, candidate):
    if (report.get('schema_version') != 1 or report.get('status') != 'MEASURED_SINGLE_REPETITION'
            or report.get('model') != candidate['model']):
        raise ValueError('Evidence is not the expected measured Qwen reference report')
    runs = report.get('runs', [])
    pairs = {}
    for row in runs:
        metadata = row['metadata']
        key = (metadata.get('engine'), row['config'].get('concurrency'))
        if key in pairs:
            raise ValueError('Duplicate engine/concurrency evidence')
        pairs[key] = row
        scheduling = {'transformers': 'serialized-batch-one-reference', 'vllm': 'vllm-continuous-batching'}
        if (row.get('status') != 'MEASURED'
                or metadata.get('model_revision') != candidate['revision']
                or metadata.get('tokenizer_revision') != candidate['revision']
                or metadata.get('image_digest') != candidate['runtime_image']
                or metadata.get('dtype') != 'bfloat16' or metadata.get('cache_mode') != 'off'
                or metadata.get('gpu_count') != 1 or metadata.get('node_count') != 1
                or metadata.get('cpu_limit') != '4' or metadata.get('memory_limit') != '32Gi'
                or metadata.get('max_model_len') != 8192
                or any(metadata.get(field) != 1 for field in ('tensor_parallel', 'pipeline_parallel', 'data_parallel'))
                or not matches(r'[0-9a-f]{64}', metadata.get('chat_template_sha256'))
                or metadata.get('scheduling') != scheduling.get(metadata.get('engine'))
                or metadata.get('gpu_product') not in ('NVIDIA L40S', 'NVIDIA-L40S')
                or not matches(r'[^\s]+@sha256:[0-9a-f]{64}', metadata.get('resolved_image'))):
            raise ValueError('Evidence model, precision, hardware, cache, or image pin differs')
        summary = row['summary']
        requests = row.get('requests', [])
        if (row['config'].get('requests') != 12 or row['config'].get('max_tokens') != 64
                or summary.get('successful_requests') != 12 or summary.get('errors') != 0
                or summary.get('usage_complete') is not True or len(requests) != 12
                or not all(item.get('ok') is True and item.get('http_status') == 200 for item in requests)):
            raise ValueError('Reference evidence must contain twelve actual successful requests per configuration')
    if set(pairs) != {(engine, concurrency) for engine in ('transformers', 'vllm') for concurrency in (1, 2)}:
        raise ValueError('Both engines and both measured concurrency levels are required')
    if len({row['metadata']['chat_template_sha256'] for row in runs}) != 1:
        raise ValueError('All measured configurations must use the same chat template')
    workloads = {row['config'].get('workload_sha256', '') for row in runs}
    if len(workloads) != 1 or not matches(r'[0-9a-f]{64}', workloads.pop()):
        raise ValueError('All measured configurations must use the same pinned workload')
    for concurrency in (1, 2):
        if benchmark.compare_results(pairs['transformers', concurrency], pairs['vllm', concurrency], 'engine')['status'] != 'COMPARABLE':
            raise ValueError('Retained engine comparison is not comparable')
    resolved = {row['metadata']['resolved_image'] for row in runs}
    if len(resolved) != 1:
        raise ValueError('Engines did not use the same resolved image')
    return resolved.pop()


def verify_originals(report, directory):
    hosts, pods = set(), set()
    for row in report['runs']:
        name = f"{row['metadata']['engine']}-c{row['config']['concurrency']}.json"
        raw = (directory / name).read_bytes()
        if hashlib.sha256(raw).hexdigest() != row.get('private_original_sha256'):
            raise ValueError('Retained original report hash differs: ' + name)
        original = json.loads(raw)
        for key in ('status', 'created_at', 'measurement_boundary', 'config', 'summary', 'warmup', 'requests'):
            if original.get(key) != row.get(key):
                raise ValueError('Public measurements differ from original: ' + name)
        metadata = original['metadata']
        if {k: v for k, v in metadata.items() if k not in ('node', 'pod_uid')} != row['metadata']:
            raise ValueError('Public metadata differs from the retained original')
        hosts.add(metadata.get('node'))
        pods.add(metadata.get('pod_uid'))
    if len(hosts) != 1 or len(pods) != 1 or None in hosts or None in pods:
        raise ValueError('Original runs do not prove the same physical host and Pod')


def verify_live(model, pods, candidate, resolved_image):
    if (model['metadata'].get('labels', {}).get('app.kubernetes.io/part-of') != registry.OWNER
            or model['spec']['model']['uri'] != candidate['uri']
            or model['spec']['template']['containers'][0]['image'] != candidate['runtime_image']):
        raise ValueError('Live owned model source or image differs from measured evidence')
    refs = model['spec'].get('router', {}).get('gateway', {}).get('refs', [])
    if len(refs) != 1 or refs[0].get('name') != 'showroom-inference' or refs[0].get('namespace') != 'ai-showroom':
        raise ValueError('Live runtime does not use the private Gateway overlay being recorded')
    ready = [p for p in pods if not p['metadata'].get('deletionTimestamp') and any(
        c['type'] == 'Ready' and c['status'] == 'True' for c in p.get('status', {}).get('conditions', []))]
    if not ready:
        raise ValueError('No Ready live backend can confirm the resolved image')
    for pod in ready:
        requested = next((c.get('image') for c in pod['spec']['containers'] if c['name'] == 'main'), None)
        resolved = next((c.get('imageID', '') for c in pod['status'].get('containerStatuses', []) if c['name'] == 'main'), '')
        if requested != candidate['runtime_image'] or resolved.removeprefix('docker-pullable://') != resolved_image:
            raise ValueError('Ready backend resolved image differs from measured evidence')
    return len(ready)


def performance_properties(properties, digest, public_url, measured_at):
    if properties.get('showroom.owner', {}).get('string_value') != registry.OWNER:
        raise ValueError('Version is not showroom-owned')
    if properties.get('showroom.lifecycle', {}).get('string_value') != 'candidate':
        raise ValueError('Reference evidence may only be attached to an existing candidate')
    state = properties.get('showroom.performance_evaluation', {}).get('string_value')
    if state not in ('NOT_RUN', STATUS):
        raise ValueError('A different performance decision exists; do not overwrite it')
    previous = properties.get('showroom.performance_evidence_sha256', {}).get('string_value')
    if previous and previous != digest:
        raise ValueError('Different measured performance evidence exists; review before replacing it')
    changed = copy.deepcopy(properties)
    changed.update(registry.properties({
        'showroom.performance_evaluation': STATUS,
        'showroom.performance_evidence_url': public_url,
        'showroom.performance_evidence_sha256': digest,
        'showroom.performance_evidence_at': measured_at,
        'showroom.performance_evidence_scope': SCOPE,
        'showroom.runtime_manifest': RUNTIME_MANIFEST,
    }))
    return changed


def update_if_unchanged(client, identifier, before, properties):
    path = registry.API + '/model_versions/' + identifier
    if client.request(path) != before:
        raise ValueError('Registry version changed during review; aborting metadata update')
    updated = client.request(path, {'customProperties': properties}, method='PATCH')
    if updated.get('customProperties') != properties:
        raise RuntimeError('Registry response differs from the reviewed metadata; inspect the version')
    return updated


def save(directory, name, value):
    with os.fdopen(os.open(directory / name, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), 'w') as stream:
        json.dump(value, stream, indent=2)
        stream.write('\n')
        stream.flush()
        os.fsync(stream.fileno())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--expected-server', required=True)
    parser.add_argument('--expected-user', required=True)
    parser.add_argument('--public-commit', required=True, help='Published immutable Git commit containing the evidence')
    parser.add_argument('--original-runs', type=Path, required=True, help='Private retained engine measurement directory')
    parser.add_argument('--audit-dir', type=Path, help='New private directory outside repository; required to apply')
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    if not re.fullmatch(r'[0-9a-f]{40}', args.public_commit):
        raise ValueError('Public evidence must use a full immutable Git commit')
    if registry.oc('whoami', '--show-server') != args.expected_server or registry.oc('whoami') != args.expected_user:
        raise ValueError('Unexpected cluster or identity')
    raw = (ROOT / REPORT_PATH).read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    public_url = f'https://github.com/{PUBLIC_REPOSITORY}/blob/{args.public_commit}/{REPORT_PATH}'
    raw_url = f'https://raw.githubusercontent.com/{PUBLIC_REPOSITORY}/{args.public_commit}/{REPORT_PATH}'
    # Public evidence fetch deliberately sends no Kubernetes token or API key.
    with urllib.request.build_opener(registry.NoRedirect).open(raw_url, timeout=20) as response:
        published = response.read(4 * 1024 * 1024 + 1)
    if published != raw:
        raise ValueError('Public immutable evidence does not match the reviewed local report')
    report = json.loads(raw)
    candidate = registry.validate_candidate(json.loads((Path(__file__).parent / 'registry/qwen-4b-candidate.json').read_text()))
    resolved = validate_report(report, candidate)
    verify_originals(report, args.original_runs)
    client = runtime.connection(args)
    identifiers = registry.onboard(client, candidate, False)
    if any(item['id'] == 'PLAN' for item in identifiers.values()):
        raise ValueError('The candidate and artifact must already be registered')
    identifier = identifiers['model_version']['id']
    version = client.request(registry.API + '/model_versions/' + identifier)
    artifact = client.request(registry.API + '/model_artifacts/' + identifiers['model_artifact']['id'])
    if artifact['uri'] != candidate['uri']:
        raise ValueError('Registered artifact URI differs from the measured model')
    model = registry.resource('llminferenceservice', 'aurora-qwen-4b', 'ai-showroom')
    pods = json.loads(registry.oc('get', 'pods', '-n', 'ai-showroom', '-l',
        'app.kubernetes.io/name=aurora-qwen-4b,kserve.io/component=workload', '-o', 'json'))['items']
    ready = verify_live(model, pods, candidate, resolved)
    measured_at = max(row['created_at'] for row in report['runs'])
    properties = performance_properties(version.get('customProperties', {}), digest, public_url, measured_at)
    summary = {'mode': 'APPLY' if args.apply else 'PLAN', 'identifiers': identifiers,
               'ready_backends_read_only': ready, 'performance_evaluation': STATUS,
               'evidence_url': public_url, 'evidence_sha256': digest,
               'runtime_manifest': RUNTIME_MANIFEST, 'registration_is_not_approval': True,
               'preserved': ['candidate lifecycle', 'safety status', 'runtime evidence', 'immutable provenance']}
    if properties == version.get('customProperties'):
        summary['mode'] = 'UNCHANGED'
        print(json.dumps(summary, indent=2))
        return
    if not args.apply:
        print(json.dumps(summary, indent=2))
        return
    if not args.audit_dir:
        raise ValueError('Apply requires a new private audit directory')
    audit = args.audit_dir.resolve()
    if audit.exists() or audit == ROOT or ROOT in audit.parents:
        raise ValueError('Use an exclusive private audit directory outside the repository')
    audit.mkdir(parents=True, mode=0o700)
    os.chmod(audit, 0o700)
    save(audit, 'before.json', {'timestamp': dt.datetime.now(dt.timezone.utc).isoformat(),
                               'version': version, 'planned_properties': properties, 'summary': summary})
    # The registry has no version-CAS API. A re-read detects observed concurrent
    # edits, but is not an atomic transaction; use a single-editor review window.
    updated = update_if_unchanged(client, identifier, version, properties)
    save(audit, 'after.json', {'timestamp': dt.datetime.now(dt.timezone.utc).isoformat(), 'version': updated})
    print(json.dumps(summary, indent=2))


if __name__ == '__main__':
    try:
        main()
    except (ValueError, RuntimeError, KeyError, OSError, subprocess.TimeoutExpired) as error:
        print(json.dumps({'status': 'BLOCKED', 'reason': str(error)}), file=sys.stderr)
        sys.exit(2)
