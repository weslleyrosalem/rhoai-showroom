#!/usr/bin/env python3
"""Opt-in same-GPU engine rehearsal. PLAN by default; never calls a cloud API.

Temporarily replaces one of two existing Ready Qwen replicas with a bounded
benchmark Pod, keeps the other replica serving, and restores both in finally.
Requires oc, PyYAML, independently supplied identity, and an exclusive private
output directory. Do not run during a customer session.
"""
import argparse
import datetime as dt
import json
import os
from pathlib import Path
import re
import select
import signal
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
NS = 'ai-showroom-bench'
MODEL_NS = 'ai-showroom'
MODEL = 'aurora-qwen-4b'
NAME = 'showroom-engine-benchmark'
REVISION = 'cdbee75f17c01a7cc42f958dc650907174af0554'
IMAGE = 'registry.redhat.io/rhaii/vllm-cuda-rhel9@sha256:c056e61672b6aea489ad5dde0bd2f8497230f5333e87f7cf6c494eba3bfdc808'
LABELS = {'app.kubernetes.io/part-of': 'rhoai-showroom',
          'app.kubernetes.io/component': 'engine-benchmark'}
SELECTOR = 'app.kubernetes.io/name=aurora-qwen-4b,kserve.io/component=workload'


def oc(*args, data=None, timeout=45):
    result = subprocess.run(['oc', '--request-timeout=30s', *args], input=data,
                            capture_output=True, text=True, timeout=timeout)
    if result.returncode:
        raise RuntimeError('OpenShift operation failed; command output suppressed')
    return result.stdout.strip()


def get(*args):
    return json.loads(oc('get', *args, '-o', 'json'))


def ready(pod):
    return not pod['metadata'].get('deletionTimestamp') and any(
        c['type'] == 'Ready' and c['status'] == 'True'
        for c in pod.get('status', {}).get('conditions', []))


def inspect_capacity(model, pods, nodes):
    """Only reuse an existing Ready GPU; do not authorize new cloud capacity."""
    if model['metadata'].get('labels', {}).get('app.kubernetes.io/part-of') != 'rhoai-showroom':
        raise ValueError('Model is not showroom-owned')
    if model['metadata'].get('annotations', {}).get('argocd.argoproj.io/tracking-id'):
        raise ValueError('Argo manages this model; coordinate a maintenance overlay first')
    if model['spec']['model']['uri'] != 'hf://Qwen/Qwen3-4B-Instruct-2507:' + REVISION:
        raise ValueError('The model revision does not match the benchmark')
    if model['spec']['template']['containers'][0]['image'] != IMAGE:
        raise ValueError('The runtime image does not match the benchmark')
    if model['spec'].get('replicas') != 2 or len(pods) != 2 or not all(ready(p) for p in pods):
        raise ValueError('Exactly two Ready Qwen replicas are required')
    hosts = {p['spec']['nodeName'] for p in pods}
    if len(hosts) != 2:
        raise ValueError('Qwen replicas must use distinct hosts')
    by_name = {n['metadata']['name']: n for n in nodes}
    physical = sum(int(n['status'].get('capacity', {}).get('nvidia.com/gpu', 0)) for n in nodes)
    if not 2 <= physical <= 16:
        raise ValueError('Observed physical GPU count must be within the fixed 16-GPU ceiling')
    for host in hosts:
        node = by_name[host]
        labels = node['metadata']['labels']
        if (labels.get('node.kubernetes.io/instance-type') != 'g6e.2xlarge'
                or labels.get('nvidia.com/gpu.product') != 'NVIDIA-L40S'
                or labels.get('showroom.openshift.ai/gpu-pool') != 'true'
                or node['status']['allocatable'].get('nvidia.com/gpu') != '1'):
            raise ValueError('Both existing hosts must be approved single-GPU L40S workers')
    victim = max(pods, key=lambda p: p['metadata']['creationTimestamp'])
    return victim, physical


def save(directory, name, value):
    path = directory / name
    with os.fdopen(os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), 'w') as stream:
        stream.write(json.dumps(value, indent=2) + '\n')


def wait_for(predicate, seconds, message):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(4)
    raise RuntimeError(message)


def execute(code, timeout=60):
    return oc('exec', '-n', NS, NAME, '-c', 'benchmark', '--', 'python', '-c', code, timeout=timeout)


def runtime_up():
    try:
        return execute("import urllib.request; print(urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=2).status)", 8) == '200'
    except RuntimeError:
        return False


def scale(model, before, after):
    oc('patch', 'llminferenceservice', MODEL, '-n', MODEL_NS, '--type=json', '-p', json.dumps([
        {'op': 'test', 'path': '/metadata/uid', 'value': model['metadata']['uid']},
        {'op': 'test', 'path': '/spec/replicas', 'value': before},
        {'op': 'replace', 'path': '/spec/replicas', 'value': after},
    ]))


def restore_model(model):
    current = get('llminferenceservice', MODEL, '-n', MODEL_NS)
    if current['metadata']['uid'] != model['metadata']['uid']:
        raise RuntimeError('The model was replaced; refuse to modify it')
    replicas = current['spec'].get('replicas')
    if replicas == 1:
        scale(model, 1, 2)
    elif replicas != 2:
        raise RuntimeError('Replica intent changed concurrently; operator review required')


def interrupted(signum, frame):
    raise KeyboardInterrupt('Termination requested; restoring owned resources')


def engine_command(engine):
    common = ['--served-model-name', MODEL, '--host', '127.0.0.1', '--port', '8000']
    if engine == 'transformers':
        return ['python', '/opt/benchmark/benchmark.py', 'serve-transformers',
                '--model-path', '/mnt/models', '--revision', REVISION,
                '--served-model', MODEL, '--host', '127.0.0.1', '--port', '8000',
                '--max-model-len', '8192']
    return ['python', '-m', 'vllm.entrypoints.openai.api_server', '--model', '/mnt/models',
            *common, '--dtype', 'bfloat16', '--max-model-len', '8192', '--max-num-seqs', '8',
            '--gpu-memory-utilization', '0.85', '--no-enable-prefix-caching',
            '--generation-config', 'vllm', '--seed', '42']


def measure(directory, pod, port):
    runtime = json.loads(execute("import torch,transformers,json,hashlib; from transformers import AutoTokenizer; t=AutoTokenizer.from_pretrained('/mnt/models',local_files_only=True,trust_remote_code=False); print(json.dumps({'torch':torch.__version__,'transformers':transformers.__version__,'chat_template_sha256':hashlib.sha256(t.chat_template.encode()).hexdigest(),'gpu':torch.cuda.get_device_name(0)}))"))
    save(directory, 'runtime.json', runtime)
    for engine in ['transformers', 'vllm']:
        command = engine_command(engine)
        execute('import subprocess,pathlib; log=open(' + repr('/tmp/' + engine + '.log') + ',"w"); p=subprocess.Popen(' + repr(command) + ',stdout=log,stderr=subprocess.STDOUT,start_new_session=True); pathlib.Path("/tmp/engine.pid").write_text(str(p.pid))')
        wait_for(runtime_up, 240, engine + ' failed bounded startup')
        metadata = {'engine': engine, 'image_digest': IMAGE, 'model_revision': REVISION,
                    'tokenizer_revision': REVISION, 'dtype': 'bfloat16', 'gpu_product': runtime['gpu'],
                    'gpu_count': 1, 'node_count': 1, 'max_model_len': 8192,
                    'chat_template_sha256': runtime['chat_template_sha256'], 'cache_mode': 'off',
                    'tensor_parallel': 1, 'pipeline_parallel': 1, 'data_parallel': 1,
                    'scheduling': 'serialized-batch-one-reference' if engine == 'transformers' else 'vllm-continuous-batching',
                    'runtime_versions': runtime, 'node': pod['spec']['nodeName'],
                    'pod_uid': pod['metadata']['uid'], 'resolved_image': pod['status']['containerStatuses'][0]['imageID'],
                    'cpu_limit': '4', 'memory_limit': '32Gi'}
        save(directory, engine + '-metadata.json', metadata)
        for concurrency in [1, 2]:
            report = directory / f'{engine}-c{concurrency}.json'
            command = [sys.executable, str(ROOT / 'scripts/benchmark.py'), 'run',
                       '--base-url', f'http://127.0.0.1:{port}/v1', '--model', MODEL,
                       '--metadata', str(directory / (engine + '-metadata.json')),
                       '--requests', '12', '--concurrency', str(concurrency), '--max-tokens', '64',
                       '--warmup', '2', '--duration', '300', '--timeout', '60', '--output', str(report)]
            result = subprocess.run(command, capture_output=True, text=True, timeout=440)
            save(directory, f'{engine}-c{concurrency}-execution.json', {'returncode': result.returncode})
            if result.returncode:
                raise RuntimeError('Measurement failed; retained report is not a successful benchmark')
            print(json.dumps({'engine': engine, 'concurrency': concurrency,
                              'summary': json.loads(report.read_text())['summary']}), flush=True)
        execute('import os,signal,pathlib,time; pid=int(pathlib.Path("/tmp/engine.pid").read_text()); os.killpg(pid,signal.SIGTERM); time.sleep(10)')
        execute('import os,signal,pathlib; pid=int(pathlib.Path("/tmp/engine.pid").read_text())\ntry: os.killpg(pid,signal.SIGKILL)\nexcept ProcessLookupError: pass')
    for concurrency in [1, 2]:
        result = subprocess.run([sys.executable, str(ROOT / 'scripts/benchmark.py'), 'compare',
                                 str(directory / f'transformers-c{concurrency}.json'),
                                 str(directory / f'vllm-c{concurrency}.json'), '--kind', 'engine',
                                 '--output', str(directory / f'comparison-c{concurrency}.json')],
                                capture_output=True, text=True, timeout=10)
        if result.returncode:
            raise RuntimeError('Comparison rejected; do not claim comparable performance')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--expected-server', required=True)
    parser.add_argument('--expected-user', required=True)
    parser.add_argument('--output-dir', type=Path, required=True)
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    directory = args.output_dir.resolve()
    if directory.exists() or directory == ROOT or ROOT in directory.parents:
        raise ValueError('Choose a new private output directory outside the repository')
    if oc('whoami') != args.expected_user or oc('whoami', '--show-server') != args.expected_server:
        raise ValueError('Unexpected cluster or identity')
    model = get('llminferenceservice', MODEL, '-n', MODEL_NS)
    pods = get('pods', '-n', MODEL_NS, '-l', SELECTOR)['items']
    victim, physical = inspect_capacity(model, pods, get('nodes')['items'])
    for kind in ['pod', 'serviceaccount', 'configmap', 'networkpolicy']:
        if get(kind, '-n', NS, '-l', 'app.kubernetes.io/component=engine-benchmark')['items']:
            raise ValueError('Existing benchmark resources require manual review')
    plan = {'mode': 'APPLY' if args.apply else 'PLAN', 'physical_gpus_observed': physical,
            'cloud_calls': False, 'additional_gpu_capacity': 0, 'temporary_qwen_replicas': 1,
            'restore_qwen_replicas': 2, 'reuse_node': victim['spec']['nodeName'],
            'engine_order': ['transformers', 'vllm'], 'requests_per_engine': 24,
            'pod_deadline_seconds': 3600, 'output': str(directory)}
    print(json.dumps(plan, indent=2), flush=True)
    if not args.apply:
        return
    import yaml
    directory.mkdir(parents=True, mode=0o700)
    os.chmod(directory, 0o700)
    save(directory, 'plan.json', plan)
    save(directory, 'before.json', {'timestamp': dt.datetime.now(dt.timezone.utc).isoformat(),
                                    'model': model, 'pods': pods})
    created, process, scale_attempted = [], None, False
    old_deletion_cost = victim['metadata'].get('annotations', {}).get('controller.kubernetes.io/pod-deletion-cost')
    previous_sigterm = signal.signal(signal.SIGTERM, interrupted)
    cleanup = {'resource_deletions': [], 'qwen_restored': False}
    try:
        oc('annotate', 'pod', victim['metadata']['name'], '-n', MODEL_NS,
           'controller.kubernetes.io/pod-deletion-cost=-100', '--overwrite')
        # A lost API response can follow a successful mutation. Reconcile actual
        # owned state in finally even when this call raises or times out.
        scale_attempted = True
        scale(model, 2, 1)
        resources = [{'apiVersion': 'v1', 'kind': 'ConfigMap',
                      'metadata': {'name': NAME + '-code', 'namespace': NS, 'labels': LABELS},
                      'data': {'benchmark.py': (ROOT / 'scripts/benchmark.py').read_text()}}]
        resources.extend(yaml.safe_load_all((ROOT / 'gitops/components/platform/engine-benchmark/resources.yaml').read_text()))
        for resource in resources:
            if resource['kind'] == 'Pod':
                # A hostname selector cannot create new matching workers via autoscaling.
                resource['spec']['nodeSelector']['kubernetes.io/hostname'] = victim['spec']['nodeName']
            live = json.loads(oc('create', '-f', '-', '-o', 'json', data=json.dumps(resource)))
            created.append((resource['kind'].lower(), resource['metadata']['name'], live['metadata']['uid']))
        wait_for(lambda: ready(get('pod', NAME, '-n', NS)), 420, 'Benchmark Pod failed bounded startup')
        pod = get('pod', NAME, '-n', NS)
        if pod['spec']['nodeName'] != victim['spec']['nodeName']:
            raise RuntimeError('Benchmark landed on an unexpected host')
        remaining = [p for p in get('pods', '-n', MODEL_NS, '-l', SELECTOR)['items'] if ready(p)]
        if len(remaining) != 1 or remaining[0]['spec']['nodeName'] == pod['spec']['nodeName']:
            raise RuntimeError('The other Qwen replica must remain Ready on its original host')
        process = subprocess.Popen(['oc', 'port-forward', '-n', NS, 'pod/' + NAME,
                                    ':8000', '--address', '127.0.0.1'], stdout=subprocess.PIPE,
                                   stderr=subprocess.STDOUT, text=True)
        port, deadline = None, time.monotonic() + 15
        while time.monotonic() < deadline and process.poll() is None:
            if select.select([process.stdout], [], [], .2)[0]:
                match = re.search(r'Forwarding from 127\.0\.0\.1:(\d+) ->', process.stdout.readline())
                if match:
                    port = int(match.group(1))
                    break
        if not port:
            raise RuntimeError('Authenticated loopback port-forward failed')
        measure(directory, pod, port)
    finally:
        if process:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
        for engine in ['transformers', 'vllm']:
            try:
                log = execute('import pathlib; p=pathlib.Path(' + repr('/tmp/' + engine + '.log') + '); print(p.read_text() if p.exists() else "not started")')
                save(directory, engine + '-log.json', {'text': log})
            except Exception:
                pass
        for kind, name, uid in reversed(created):
            try:
                live = get(kind, name, '-n', NS)
                if live['metadata']['uid'] != uid:
                    raise RuntimeError('Resource replaced; refuse deletion')
                oc('delete', kind, name, '-n', NS, '--wait=false')
                cleanup['resource_deletions'].append({'kind': kind, 'name': name, 'delete_requested': True})
            except Exception:
                cleanup['resource_deletions'].append({'kind': kind, 'name': name, 'delete_requested': False})
        try:
            current_victim = get('pod', victim['metadata']['name'], '-n', MODEL_NS)
            if current_victim['metadata']['uid'] == victim['metadata']['uid']:
                annotation = 'controller.kubernetes.io/pod-deletion-cost'
                value = annotation + '-' if old_deletion_cost is None else annotation + '=' + old_deletion_cost
                oc('annotate', 'pod', victim['metadata']['name'], '-n', MODEL_NS, value, '--overwrite')
        except Exception:
            pass  # The removed replica normally no longer exists.
        if scale_attempted:
            try:
                restore_model(model)
                wait_for(lambda: len([p for p in get('pods', '-n', MODEL_NS, '-l', SELECTOR)['items'] if ready(p)]) == 2,
                         420, 'Qwen replica restoration needs operator attention')
                cleanup['qwen_restored'] = True
            except Exception:
                cleanup['qwen_restored'] = False
        save(directory, 'cleanup.json', cleanup)
        signal.signal(signal.SIGTERM, previous_sigterm)
        if scale_attempted and not cleanup['qwen_restored']:
            raise RuntimeError('Qwen restoration incomplete; inspect cleanup.json immediately')
        if any(not row['delete_requested'] for row in cleanup['resource_deletions']):
            raise RuntimeError('Some owned resources remain; inspect cleanup.json immediately')


if __name__ == '__main__':
    main()
