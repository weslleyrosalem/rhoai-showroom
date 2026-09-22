#!/usr/bin/env python3
"""Administrator-led, loopback-only GuideLLM lab on two existing Qwen backends.

Creates no model, changes no shared workload, and closes its own forwards.
GuideLLM receives no cluster credential. Reports include every material limit.
"""
import argparse
import base64
import csv
import datetime as dt
import hashlib
import http.client
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import re
import select
import signal
import ssl
import subprocess
import sys
import threading
import time

NS = 'ai-showroom'
MODEL = 'aurora-qwen-4b'
LABEL = 'app.kubernetes.io/name=aurora-qwen-4b,kserve.io/component=workload'
GUIDELLM_VERSION = '0.6.0'
PUBLIC_ROOT = Path(__file__).resolve().parents[2]


def private_output_path(path):
    """Reject public, existing, or symlink-aliased output before any workload."""
    destination = path.expanduser().resolve()
    if destination == PUBLIC_ROOT or PUBLIC_ROOT in destination.parents:
        raise ValueError('Raw evidence must be outside the public repository')
    if destination.exists():
        raise ValueError('Choose a new output directory; evidence is never overwritten')
    return destination


def bounded_generation(data):
    """Both token-limit aliases must be safe when a caller supplies both."""
    if not isinstance(data, dict) or data.get('model') != MODEL:
        return False
    limits = [data[key] for key in ('max_tokens', 'max_completion_tokens') if key in data]
    return bool(limits) and all(type(value) is int and 1 <= value <= 64 for value in limits)


def oc(*args):
    p = subprocess.run(['oc', '--request-timeout=30s', *args], capture_output=True, timeout=40)
    if p.returncode:
        raise RuntimeError('OpenShift operation failed; output suppressed to protect access details')
    return p.stdout


def get(kind, name=None):
    return json.loads(oc('get', kind, *([name] if name else []), '-n', NS, '-o', 'json'))


def forward(resource, remote, procs):
    p = subprocess.Popen(['oc', 'port-forward', '-n', NS, resource, ':' + str(remote), '--address', '127.0.0.1'],
                         stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    procs.append(p)
    end = time.monotonic() + 20
    while time.monotonic() < end and p.poll() is None:
        if select.select([p.stdout], [], [], .25)[0]:
            m = re.search(r'Forwarding from 127\.0\.0\.1:(\d+) ->', p.stdout.readline())
            if m:
                return int(m.group(1))
    raise RuntimeError('Loopback port-forward did not become ready')


def request(port, path, context=None, token=None, body=None):
    conn = (http.client.HTTPSConnection('localhost', port, context=context, timeout=30)
            if context else http.client.HTTPConnection('127.0.0.1', port, timeout=30))
    headers = {'Content-Type': 'application/json'}
    if token:
        headers['Authorization'] = 'Bearer ' + token
    try:
        conn.request('POST' if body else 'GET', path, body=json.dumps(body).encode() if body else None, headers=headers)
        r = conn.getresponse()
        return r.status, r.read(8_000_000)
    finally:
        conn.close()


def metrics(port, context=None, token=None):
    status, raw = request(port, '/metrics', context, token)
    if status != 200:
        raise RuntimeError('Metrics read failed')
    prefixes = ('vllm:request_success_total', 'vllm:prefix_cache_hits_total',
                'vllm:prefix_cache_queries_total', 'vllm:prompt_tokens_total',
                'vllm:generation_tokens_total', 'vllm:num_requests_running',
                'vllm:num_requests_waiting', 'llm_d_epp_request_total')
    result = {}
    for line in raw.decode().splitlines():
        if line.startswith(prefixes):
            name = line.split('{')[0].split(' ')[0]
            result[name] = result.get(name, 0) + float(line.rsplit(' ', 1)[-1])
    return result


def delta(after, before):
    return {k: v - before.get(k, 0) for k, v in after.items() if 'total' in k}


class Broker(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = False


class Handler(BaseHTTPRequestHandler):
    protocol_version = 'HTTP/1.0'

    def log_message(self, *_):
        pass

    def do_GET(self):
        self.relay()

    def do_POST(self):
        self.relay()

    def relay(self):
        s = self.server
        path = self.path
        if path not in ('/health', '/v1/models', '/v1/chat/completions', '/v1/completions'):
            self.send_error(404)
            return
        if path == '/health':
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b'{"status":"ok"}')
            return
        if time.monotonic() > s.deadline:
            self.send_error(503)
            return
        raw = None
        if self.command == 'POST':
            size = int(self.headers.get('Content-Length', '0'))
            if not 1 <= size <= 65536:
                self.send_error(413)
                return
            raw = self.rfile.read(size)
            data = json.loads(raw)
            if not bounded_generation(data):
                self.send_error(400)
                return
        with s.lock:
            backend = 0 if s.mode == 'single' else s.index % 2
            if self.command == 'POST':
                s.index += 1
        with s.semaphore:
            if s.mode == 'llmd':
                conn = http.client.HTTPConnection('127.0.0.1', s.gateway, timeout=25)
                target = '/' + NS + '/' + MODEL + path
                headers = {'Authorization': 'Bearer ' + s.token}
            else:
                conn = http.client.HTTPSConnection('localhost', s.backends[backend], context=s.context, timeout=25)
                target = path
                headers = {}
            headers.update({'Content-Type': 'application/json', 'Connection': 'close'})
            started = time.monotonic()
            status = 502
            try:
                conn.request(self.command, target, body=raw, headers=headers)
                r = conn.getresponse()
                status = r.status
                self.send_response(status)
                self.send_header('Content-Type', r.getheader('Content-Type', 'application/json'))
                self.send_header('Connection', 'close')
                self.end_headers()
                while True:
                    chunk = r.read1(8192)
                    if not chunk:
                        break
                    self.wfile.write(chunk)
                    self.wfile.flush()
            except (BrokenPipeError, ConnectionResetError):
                s.client_disconnects += 1
            except (OSError, http.client.HTTPException):
                s.errors += 1
            finally:
                conn.close()
                if self.command == 'POST':
                    with s.lock:
                        s.rows.append({'mode': s.mode, 'backend': ('picker' if s.mode == 'llmd' else backend),
                                       'status': status, 'elapsed_seconds': time.monotonic() - started})


def prompts(path, salt):
    prefix = ('Aurora Supply measurement ' + salt + '. Recommendations require human approval. '
              'Use synthetic inventory facts only. Never execute a purchase. ')
    prefix += '\n'.join(f'SKU-{i:03d}: stock={30+i}; daily_demand={2+i%5}; supplier=Northstar; lead_time_days=7.' for i in range(20))
    with path.open('w') as f:
        w = csv.writer(f)
        w.writerow(['prompt', 'output_tokens_count'])
        for i in range(16):
            w.writerow([prefix + f'\nFor SKU-{i%4:03d}, state the approval requirement briefly.', 32])
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--expected-server', required=True)
    p.add_argument('--expected-user', required=True)
    p.add_argument('--guidellm', required=True, type=Path)
    p.add_argument('--tokenizer', required=True, type=Path)
    p.add_argument('--output', required=True, type=Path)
    p.add_argument('--check-only',action='store_true',help='Validate identity, topology, versions, and tokenizer without requests or resources')
    p.add_argument('--seconds', type=int, default=30, choices=range(5,31))
    p.add_argument('--requests', type=int, default=30, choices=range(1,31))
    p.add_argument('--modes', nargs='+', choices=('single','round-robin','llmd'), default=['single','round-robin','llmd'])
    a = p.parse_args()
    a.output = private_output_path(a.output)
    if len(set(a.modes)) != len(a.modes):
        raise ValueError('Each benchmark mode can appear only once')
    if oc('whoami','--show-server').decode().strip()!=a.expected_server or oc('whoami').decode().strip()!=a.expected_user:
        raise ValueError('Unexpected cluster or identity')
    pods = json.loads(oc('get','pods','-n',NS,'-l',LABEL,'-o','json'))['items']
    pods = sorted([x for x in pods if not x['metadata'].get('deletionTimestamp') and any(c['type']=='Ready' and c['status']=='True' for c in x['status'].get('conditions',[]))],key=lambda x:x['metadata']['name'])
    if len(pods)!=2 or len({x['spec']['nodeName'] for x in pods})!=2:
        raise ValueError('Require exactly two Ready Qwen backends on distinct nodes')
    model = get('llminferenceservice',MODEL)
    picker = get('deployment',MODEL+'-kserve-router-scheduler')['spec']['template']['spec']['containers'][0]
    config = picker['args'][picker['args'].index('--config-text')+1]
    if 'prefix-cache-scorer' not in config:
        raise ValueError('Installed picker lacks the workshop prefix scorer')
    expected_uri='hf://Qwen/Qwen3-4B-Instruct-2507:cdbee75f17c01a7cc42f958dc650907174af0554'
    if model['spec']['model']['uri']!=expected_uri:
        raise ValueError('Model revision differs from the pinned workshop tokenizer')
    from prepare_tokenizer import FILES
    if any(hashlib.sha256((a.tokenizer/name).read_bytes()).hexdigest()!=sha for name,sha in FILES.items()):
        raise ValueError('Tokenizer files do not match the serving revision')
    images={x['spec']['containers'][0]['image'] for x in pods}
    if len(images)!=1:
        raise ValueError('Backend runtime images differ')
    gpu_types={json.loads(oc('get','node',x['spec']['nodeName'],'-o','json'))['metadata']['labels'].get('nvidia.com/gpu.product') for x in pods}
    if gpu_types!={'NVIDIA-L40S'}:
        raise ValueError('This recorded workshop profile requires two L40S GPUs')
    version=subprocess.run([str(a.guidellm.resolve()),'--version'],capture_output=True,text=True,timeout=30,check=True).stdout
    if not re.search(r'(?<![0-9])0\.6\.0(?![0-9])',version):
        raise ValueError('GuideLLM version differs from the recorded workshop version')
    if a.check_only:
        print(json.dumps({'status':'PREFLIGHT_PASS','ready_backends':2,'distinct_nodes':2,'guidellm_version':GUIDELLM_VERSION,'tokenizer_checksums':'verified'}))
        return 0
    # GuideLLM is a child process and inherits this restrictive file-creation mask.
    os.umask(0o077)
    a.output.mkdir(parents=True, mode=0o700, exist_ok=False)
    result = {'schema_version':1,'started_at':dt.datetime.now(dt.timezone.utc).isoformat(),
      'status':'INCOMPLETE','topology':{'ready_backends':2,'distinct_gpu_nodes':2,'gpu_type':'NVIDIA L40S',
      'model':model['spec']['model'],'runtime_image':pods[0]['spec']['containers'][0]['image'],
      'scheduler_image':picker['image'],'scheduler_config':config},
      'workload':{'seconds_per_mode':a.seconds,'concurrency':{'single':1,'round-robin':2,'llmd':2},'output_tokens':32,
                  'guidellm_version':GUIDELLM_VERSION,'prompt_rows':16,'unique_questions':4,'request_cap_per_mode':a.requests},
      'limitations':['Administrator-only loopback port-forwards bypass normal backend network access for baseline measurements.',
        'The llm-d path includes native Gateway authentication and scheduling; baseline bypasses both.',
        'Shared live backends, short windows, and no cache flush preclude causal routing-speedup or statistically robust tail claims.',
        'Distinct fresh prefix salts reduce cross-mode carryover; workload shapes match, prompt bytes differ.',
        'Two existing Qwen3 4B L40S backends replace the source lab four Llama 8B GPUs.',
        'Local prefix caching is not cross-node KV transfer or prefill/decode disaggregation.'], 'runs':[]}
    procs=[]
    servers=[]
    try:
        token=oc('whoami','-t').decode().strip()
        ca=base64.b64decode(get('secret',MODEL+'-kserve-self-signed-certs')['data']['ca.crt']).decode()
        context=ssl.create_default_context(cadata=ca)
        backends=[forward('pod/'+x['metadata']['name'],8000,procs) for x in pods]
        gateway=forward('service/showroom-inference-maas-gateway-class',8080,procs)
        epp=forward('deployment/'+MODEL+'-kserve-router-scheduler',9090,procs)
        body={'model':MODEL,'messages':[{'role':'user','content':'Aurora policy requires human approval. Restate it briefly.'}],'max_tokens':16,'temperature':0}
        path='/'+NS+'/'+MODEL+'/v1/chat/completions'
        result['authentication']={'anonymous_status':request(gateway,path,body=body)[0],
                                  'authorized_status':request(gateway,path,token=token,body=body)[0]}
        if result['authentication']!={'anonymous_status':401,'authorized_status':200}:
            raise RuntimeError('Native authentication rehearsal failed')
        deadline=time.monotonic()+300
        for mode in a.modes:
            if time.monotonic()>deadline-60:
                raise RuntimeError('Absolute rehearsal deadline reached')
            out=a.output/mode
            out.mkdir()
            data=out/'prompts.csv'
            prompt_hash=prompts(data,hashlib.sha256((result['started_at']+mode).encode()).hexdigest()[:16])
            s=Broker(('127.0.0.1',0),Handler)
            servers.append(s)
            s.mode,s.backends,s.gateway,s.context,s.token=mode,backends,gateway,context,token
            s.lock,s.semaphore,s.index,s.rows,s.errors=threading.Lock(),threading.BoundedSemaphore(2),0,[],0
            s.client_disconnects=0
            s.deadline=deadline
            threading.Thread(target=s.serve_forever,daemon=True).start()
            before=[metrics(b,context) for b in backends]
            picker_before=metrics(epp, token=token)
            concurrency=1 if mode=='single' else 2
            command=[str(a.guidellm.resolve()),'benchmark','run','--target',f'http://127.0.0.1:{s.server_port}',
              '--model',MODEL,'--request-type','chat_completions','--profile','concurrent','--rate',str(concurrency),
              '--max-seconds',str(a.seconds),'--data',str(data.resolve()),'--processor',str(a.tokenizer.resolve()),
              '--output-dir',str(out.resolve()),'--outputs','json,csv','--max-errors','2',
              '--max-requests',str(a.requests),'--warmup','0','--cooldown','0','--data-num-workers','0',
              '--random-seed','42','--disable-console-interactive',
              '--processor-args',json.dumps({'local_files_only':True,'trust_remote_code':False}),
              '--backend-kwargs',json.dumps({'http2':False,'follow_redirects':False,'timeout':25,'max_tokens':32,
                 'extras':{'body':{'temperature':0,'seed':42}}})]
            with (out/'console.log').open('w') as f:
                child=subprocess.Popen(command,stdout=f,stderr=subprocess.STDOUT,start_new_session=True,
                    env=dict(os.environ,TOKENIZERS_PARALLELISM='false',HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',
                             GUIDELLM__MP_CONTEXT_TYPE='spawn',GUIDELLM__MAX_WORKER_PROCESSES='1'))
                try:
                    child.wait(timeout=min(100,deadline-time.monotonic()))
                except BaseException:
                    os.killpg(child.pid,signal.SIGTERM)
                    try:child.wait(timeout=5)
                    except subprocess.TimeoutExpired:os.killpg(child.pid,signal.SIGKILL);child.wait(timeout=5)
                    raise
                run=child
            # Engine counters are published periodically; preserve actual snapshots.
            time.sleep(6)
            after=[metrics(b,context) for b in backends]
            picker_after=metrics(epp, token=token)
            record={'mode':mode,'exit_code':run.returncode,'prompt_sha256':prompt_hash,
                 'backend_before':before,'backend_after':after,'backend_delta':[delta(x,y) for x,y in zip(after,before)],
                 'picker_delta':delta(picker_after,picker_before),'proxy_requests':s.rows,'proxy_errors':s.errors,'client_disconnects':s.client_disconnects}
            report=json.loads((out/'benchmarks.json').read_text()) if (out/'benchmarks.json').exists() else {}
            totals=[b['metrics']['request_totals'] for b in report.get('benchmarks',[])]
            record['guidellm_request_totals']=totals
            result['runs'].append(record)
            s.shutdown();s.server_close();servers.remove(s)
            print(json.dumps({'mode':mode,'exit_code':run.returncode,'requests':len(s.rows),'proxy_errors':s.errors}),flush=True)
            if run.returncode!=0 or s.errors or not s.rows or any(r['status']!=200 for r in s.rows) or not totals or any(t.get('errored',0) or not t.get('successful',0) for t in totals):
                raise RuntimeError('A benchmark failed; inspect retained local console log')
        result['status']='MEASURED'
    finally:
        for s in servers:
            s.shutdown();s.server_close()
        for proc in procs:
            proc.terminate()
            try:proc.wait(timeout=5)
            except subprocess.TimeoutExpired:proc.kill();proc.wait(timeout=5)
        result['finished_at']=dt.datetime.now(dt.timezone.utc).isoformat()
        (a.output/'evidence.json').write_text(json.dumps(result,indent=2)+'\n')
    return 0 if result['status']=='MEASURED' else 2


if __name__=='__main__':
    try:sys.exit(main())
    except (ValueError,RuntimeError,OSError,subprocess.SubprocessError) as e:
        print(f'BLOCKED: {type(e).__name__}: {e}',file=sys.stderr)
        sys.exit(2)
