#!/usr/bin/env python3
"""Bounded native Qwen inference/EPP rehearsal using authenticated oc port-forwards.

Reads the current token in memory; no Secrets, tokens, or response text are
printed. Creates no cluster resources and closes every local port-forward.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor
import datetime as dt
import json
from pathlib import Path
import re
import select
import subprocess
import sys
import time
import urllib.error
import urllib.request


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


def oc(*args):
    run = subprocess.run(['oc', '--request-timeout=30s', *args], capture_output=True, text=True, timeout=40)
    if run.returncode:
        raise RuntimeError('OpenShift inspection failed; credential-bearing output suppressed')
    return run.stdout.strip()


def forward(resource, remote, processes):
    process = subprocess.Popen(['oc', 'port-forward', '-n', 'ai-showroom', resource,
                                ':' + str(remote), '--address', '127.0.0.1'],
                               stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    processes.append(process)
    end = time.monotonic() + 15
    while time.monotonic() < end and process.poll() is None:
        if select.select([process.stdout], [], [], .25)[0]:
            line = process.stdout.readline()
            match = re.search(r'Forwarding from 127\.0\.0\.1:(\d+) ->', line)
            if match:
                return int(match.group(1))
    raise RuntimeError('Authenticated port-forward did not establish an allocated loopback port')


def request(port, path, token, body=None):
    headers = {'Authorization': 'Bearer ' + token} if token else {}
    if body is not None:
        headers['Content-Type'] = 'application/json'
    req = urllib.request.Request('http://127.0.0.1:' + str(port) + path,
                                 data=json.dumps(body).encode() if body else None, headers=headers)
    start = time.monotonic()
    try:
        with urllib.request.build_opener(NoRedirect).open(req, timeout=30) as response:
            return response.status, response.read(4000000).decode(), time.monotonic() - start
    except urllib.error.HTTPError as error:
        return error.code, '', time.monotonic() - start


def picker_metrics(port, token):
    status, body, _ = request(port, '/metrics', token)
    if status != 200:
        raise RuntimeError('Authorized picker metrics request did not return 200')
    return {line.rsplit(' ', 1)[0]: float(line.rsplit(' ', 1)[1]) for line in body.splitlines()
            if line.startswith('llm_d_epp_request_total{')}


def backend_metrics(pods):
    code = """import urllib.request,ssl,json
context=ssl.create_default_context(cafile='/var/run/kserve/tls/ca.crt')
with urllib.request.urlopen('https://localhost:8000/metrics',context=context,timeout=10) as response:
    raw=response.read(4000000).decode()
prefixes=('vllm:request_success_total{','vllm:prefix_cache_hits_total{',
          'vllm:prefix_cache_queries_total{','vllm:generation_tokens_total{','vllm:prompt_tokens_total{')
print(json.dumps({line.rsplit(' ',1)[0]:float(line.rsplit(' ',1)[1])
                 for line in raw.splitlines() if line.startswith(prefixes)}))
"""
    return {pod['metadata']['name']: json.loads(oc('exec', '-n', 'ai-showroom',
            pod['metadata']['name'], '-c', 'main', '--', 'python', '-c', code)) for pod in pods}


def measure_placement(pods, gateway_port, picker_port, token):
    before = backend_metrics(pods)
    picker_before = picker_metrics(picker_port, token)
    nonce = dt.datetime.now(dt.timezone.utc).strftime('%Y%m%dT%H%M%S')
    def call(item):
        section, repeated = item
        prompt = (f'Aurora Supply routing rehearsal {nonce}, policy section {section}. '
                  + ('Inventory recommendations require human approval. Tools return synthetic data, exact SKU, '
                     'stock, forecast provenance, and an approval role. No purchase is executed. ' * 16)
                  + f'Analyze policy section {section} for AS-001. Explain the safe recommendation workflow in a concise paragraph.')
        body = {'model': 'aurora-qwen-4b', 'messages': [{'role': 'user', 'content': prompt}],
                'max_tokens': 128, 'temperature': 0}
        status, raw, latency = request(gateway_port, '/ai-showroom/aurora-qwen-4b/v1/chat/completions', token, body)
        response = json.loads(raw) if status == 200 and raw else {}
        return {'section': section, 'repeated': repeated, 'http_status': status,
                'usage': response.get('usage'), 'latency_seconds': latency}
    rows = []
    for batch in range(3):
        with ThreadPoolExecutor(max_workers=2) as pool:
            rows.extend(pool.map(call, [(batch, False), (batch + 100, False)]))
        time.sleep(3)
    with ThreadPoolExecutor(max_workers=2) as pool:
        rows.extend(pool.map(call, [(0, True), (100, True)]))
    after = backend_metrics(pods)
    picker_after = picker_metrics(picker_port, token)
    delta = {pod: {key: value - before[pod].get(key, 0) for key, value in values.items()}
             for pod, values in after.items()}
    active = sum(any(key.startswith('vllm:request_success_total{') and value > 0
                     and ('finished_reason="stop"' in key or 'finished_reason="length"' in key)
                     for key, value in values.items()) for values in delta.values())
    return {'requests': rows, 'backend_counter_delta': delta,
            'backends_with_successful_requests': active,
            'picker_request_delta': sum(picker_after.values()) - sum(picker_before.values()),
            'interpretation': 'Per-backend counters show measured serving and local cache activity. '
                              'Concurrent traffic can contribute; this is not a routing algorithm comparison, '
                              'a speedup claim, or cross-node KV transfer.'}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--expected-server', required=True)
    p.add_argument('--expected-user', required=True)
    p.add_argument('--require-backends', type=int, choices=(1, 2), default=1)
    p.add_argument('--output', required=True, type=Path)
    p.add_argument('--measure-placement', action='store_true',
                   help='Send eight additional bounded requests and read per-backend metrics; requires two nodes')
    args = p.parse_args()
    if args.output.exists():
        raise ValueError('Choose a new output filename; prior evidence must remain intact')
    if oc('whoami', '--show-server') != args.expected_server or oc('whoami') != args.expected_user:
        raise ValueError('Unexpected cluster or identity')
    llm = json.loads(oc('get', 'llminferenceservice', 'aurora-qwen-4b', '-n', 'ai-showroom', '-o', 'json'))
    if llm['metadata'].get('labels', {}).get('app.kubernetes.io/part-of') != 'rhoai-showroom':
        raise ValueError('The Qwen model must be showroom-owned')
    pods = json.loads(oc('get', 'pods', '-n', 'ai-showroom', '-l',
                        'app.kubernetes.io/name=aurora-qwen-4b,kserve.io/component=workload', '-o', 'json'))['items']
    ready = [pod for pod in pods if not pod['metadata'].get('deletionTimestamp') and any(c['type'] == 'Ready' and c['status'] == 'True'
                                       for c in pod.get('status', {}).get('conditions', []))]
    nodes = {pod['spec']['nodeName'] for pod in ready}
    required = 2 if args.measure_placement else args.require_backends
    if len(ready) < required or len(nodes) < required:
        raise ValueError('Required Ready backends on distinct nodes are not available')
    token = oc('whoami', '-t')
    processes = []
    try:
        gateway_port = forward('service/showroom-inference-maas-gateway-class', 8080, processes)
        picker_port = forward('deployment/aurora-qwen-4b-kserve-router-scheduler', 9090, processes)
        path = '/ai-showroom/aurora-qwen-4b/v1/chat/completions'
        body = {'model': 'aurora-qwen-4b', 'messages': [{'role': 'user', 'content':
                'Aurora Supply policy: recommendations require human review before a purchase. Restate the policy in one sentence.'}],
                'max_tokens': 32, 'temperature': 0}
        rows = []
        for identity in ('anonymous', 'authorized', 'authorized'):
            before = picker_metrics(picker_port, token)
            status, raw, latency = request(gateway_port, path, '' if identity == 'anonymous' else token, body)
            after = picker_metrics(picker_port, token)
            response = json.loads(raw) if status == 200 and raw else {}
            rows.append({'identity': identity, 'http_status': status, 'latency_seconds': latency,
                         'usage': response.get('usage'), 'response_model': response.get('model'),
                         'picker_request_delta': sum(after.values()) - sum(before.values())})
        valid = rows[0]['http_status'] == 401 and all(row['http_status'] == 200 and row['usage']
                and row['picker_request_delta'] >= 1 for row in rows[1:])
        result = {'status': 'MEASURED' if valid else 'FAILED', 'timestamp': dt.datetime.now(dt.timezone.utc).isoformat(),
                  'ready_backend_count': len(ready), 'distinct_node_count': len(nodes), 'requests': rows,
                  'interpretation': 'Picker counters include rejected requests and concurrent traffic. Successful inference requires 200 plus response usage; this is not a placement-efficiency or quality benchmark.'}
        if args.measure_placement:
            placement = measure_placement(ready, gateway_port, picker_port, token)
            result['placement'] = placement
            valid = valid and all(row['http_status'] == 200 and row['usage'] for row in placement['requests'])
            result['status'] = 'MEASURED' if valid else 'FAILED'
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open('x') as output:
            json.dump(result, output, indent=2)
        print(json.dumps(result))
        return 0 if valid else 2
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
        sys.exit(main())
    except (ValueError, KeyError, OSError, RuntimeError, subprocess.TimeoutExpired) as error:
        print(json.dumps({'status': 'BLOCKED', 'reason': str(error)}), file=sys.stderr)
        sys.exit(2)
