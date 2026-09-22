#!/usr/bin/env python3
"""Export typed, allowlisted workshop measurements; never copy raw configuration."""
import argparse
import datetime as dt
import hashlib
import json
import math
import os
from pathlib import Path
import re

MODES = ('single', 'round-robin', 'llmd')
MODEL_URI = 'hf://Qwen/Qwen3-4B-Instruct-2507:cdbee75f17c01a7cc42f958dc650907174af0554'
LIMITATIONS = [
    'Administrator-only loopback port-forwards bypass normal backend network access for baseline measurements.',
    'The llm-d path includes native Gateway authentication and scheduling; baseline bypasses both.',
    'Shared live backends, short windows, and no cache flush preclude causal routing-speedup or statistically robust tail claims.',
    'Distinct fresh prefix salts reduce cross-mode carryover; workload shapes match, prompt bytes differ.',
    'Two existing Qwen3 4B L40S backends replace the source lab four Llama 8B GPUs.',
    'Local prefix caching is not cross-node KV transfer or prefill/decode disaggregation.',
    'Backend and EPP counter deltas include concurrent activity; they are not uniquely attributed request traces.',
]


def number(value, integer=False):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0:
        raise ValueError('Expected a finite nonnegative measurement')
    if integer and not isinstance(value, int):
        raise ValueError('Expected an integer count')
    return value


def exact(value, expected):
    if value != expected or type(value) is not type(expected):
        raise ValueError('Evidence differs from the reviewed workshop contract')
    return expected


def digest(value):
    if not isinstance(value, str) or not re.fullmatch(r'[0-9a-f]{64}', value):
        raise ValueError('Invalid artifact digest')
    return value


def image(value):
    if not isinstance(value, str) or not re.fullmatch(r'registry\.redhat\.io/[a-z0-9_./-]+@sha256:[0-9a-f]{64}', value):
        raise ValueError('Expected a pinned public Red Hat image')
    return value


def timestamp(value):
    parsed = dt.datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        raise ValueError('Evidence timestamp must contain a time zone')
    return parsed.isoformat()


def local_json(root, relative):
    path = (root / relative).resolve()
    if root not in path.parents:
        raise ValueError('Artifact path escapes the selected evidence directory')
    return json.loads(path.read_text()), path


def summarize(directory):
    root = directory.expanduser().resolve()
    evidence, _ = local_json(root, 'evidence.json')
    topology, workload = evidence['topology'], evidence['workload']
    seconds = number(workload['seconds_per_mode'], integer=True)
    if not 5 <= seconds <= 30:
        raise ValueError('Unexpected benchmark duration')
    # Rebuild public fields. Raw model/scheduler configuration, arbitrary
    # annotations, free-form limitations, and request content never pass through.
    result = {
        'status': exact(evidence['status'], 'MEASURED'),
        'started_at': timestamp(evidence['started_at']),
        'finished_at': timestamp(evidence['finished_at']),
        'topology': {
            'ready_backends': exact(topology['ready_backends'], 2),
            'distinct_gpu_nodes': exact(topology['distinct_gpu_nodes'], 2),
            'gpu_type': exact(topology['gpu_type'], 'NVIDIA L40S'),
            'model': {'name': exact(topology['model']['name'], 'aurora-qwen-4b'),
                      'uri': exact(topology['model']['uri'], MODEL_URI)},
            'runtime_image': image(topology['runtime_image']),
            'scheduler_image': image(topology['scheduler_image']),
            'prefix_cache_scorer_present': 'prefix-cache-scorer' in topology['scheduler_config'],
        },
        'workload': {
            'seconds_per_mode': seconds,
            'concurrency': {mode: exact(workload['concurrency'][mode], 1 if mode == 'single' else 2) for mode in MODES},
            'output_tokens': exact(workload['output_tokens'], 32),
            'guidellm_version': exact(workload['guidellm_version'], '0.6.0'),
            'prompt_rows': exact(workload['prompt_rows'], 16),
            'unique_questions': exact(workload['unique_questions'], 4),
        },
        'limitations': LIMITATIONS,
        'authentication': {key: exact(evidence['authentication'][key], value)
                           for key, value in {'anonymous_status': 401, 'authorized_status': 200}.items()},
        'source_workshop': {'repository': 'https://github.com/rhpds/llm-d-showroom',
                           'revision': 'e4d63c30252ce42fa783b1a08a1706d3cda20761'},
        'runs': [],
    }
    seen = set()
    for run in evidence['runs']:
        mode = run['mode']
        if mode not in MODES or mode in seen:
            raise ValueError('Expected distinct known benchmark modes')
        seen.add(mode)
        raw, report = local_json(root, mode + '/benchmarks.json')
        if len(raw['benchmarks']) != 1:
            raise ValueError('Expected one benchmark per mode')
        benchmark = raw['benchmarks'][0]
        metrics = benchmark['metrics']
        totals = {key: number(metrics['request_totals'][key], integer=True)
                  for key in ('successful', 'errored', 'incomplete', 'total')}
        if totals['successful'] <= 0 or totals['errored'] or totals['incomplete'] or totals['total'] != totals['successful']:
            raise ValueError('Benchmark did not pass the functional gate')
        if run.get('exit_code') != 0 or run['proxy_errors'] != 0 or not run['proxy_requests']:
            raise ValueError('Broker or benchmark execution failed')
        if any(row['status'] != 200 or row['backend'] not in (0, 1, 'picker') for row in run['proxy_requests']):
            raise ValueError('Unexpected broker outcome')
        if len(run['backend_delta']) != 2:
            raise ValueError('Expected two backend counter sets')
        queries = sum(number(row.get('vllm:prefix_cache_queries_total', 0)) for row in run['backend_delta'])
        hits = sum(number(row.get('vllm:prefix_cache_hits_total', 0)) for row in run['backend_delta'])
        if hits > queries:
            raise ValueError('Cache counters do not form a valid observation window')
        row = {
            'mode': mode, 'duration_seconds': number(benchmark['duration']), 'requests': totals,
            'guidellm_report_sha256': hashlib.sha256(report.read_bytes()).hexdigest(),
            'prompt_sha256': digest(run['prompt_sha256']), 'broker_requests': len(run['proxy_requests']),
            'broker_upstream_errors': number(run['proxy_errors'], integer=True),
            'client_disconnects': number(run.get('client_disconnects', 0), integer=True),
            'backend_success_deltas': [number(item.get('vllm:request_success_total', 0)) for item in run['backend_delta']],
            'backend_prefix_queries_delta': queries, 'backend_prefix_hits_delta': hits,
            'observed_cache_hit_fraction': hits / queries if queries else None,
            'epp_request_delta': number(run['picker_delta'].get('llm_d_epp_request_total', 0)),
            'broker_assignment_counts': {str(key): sum(item['backend'] == key for item in run['proxy_requests'])
                                         for key in (0, 1, 'picker')},
        }
        for field in ('time_to_first_token_ms', 'request_latency', 'requests_per_second',
                      'output_tokens_per_second', 'prompt_token_count', 'output_token_count'):
            value = metrics[field]['successful']
            row[field] = {'mean': number(value['mean']), 'p50': number(value['percentiles']['p50']),
                          'p95': number(value['percentiles']['p95'])}
        result['runs'].append(row)
    if not seen or not result['topology']['prefix_cache_scorer_present']:
        raise ValueError('No completed runs or reviewed prefix scorer found')
    result['interpretation'] = ('Functional inference, authentication, two-backend availability, installed prefix scoring, '
                                'and observed cache counters. Short shared-environment end-to-end samples do not '
                                'establish a causal llm-d speedup or four-GPU scalability.')
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    summary = summarize(args.directory)
    # Public export is intentional, but never overwrite a prior result or symlink.
    descriptor = os.open(args.output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, 'w') as stream:
        stream.write(json.dumps(summary, indent=2, allow_nan=False) + '\n')
    for run in summary['runs']:
        print(run['mode'], run['requests'], 'P95 TTFT ms:', round(run['time_to_first_token_ms']['p95'], 2),
              'EPP:', run['epp_request_delta'])
