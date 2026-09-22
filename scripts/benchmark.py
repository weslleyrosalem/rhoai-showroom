#!/usr/bin/env python3
"""Bounded, reproducible Aurora inference measurements; no synthetic performance.

run: measure a streaming OpenAI-compatible endpoint.
compare: reject incomparable runs before calculating ratios.
serve-transformers: optional single-GPU reference server (extra dependencies).
"""
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import datetime as dt
import hashlib
import json
import math
import os
from pathlib import Path
import statistics
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

LIMITS = {'requests': 200, 'concurrency': 16, 'max_tokens': 256, 'duration': 600}
COMMON_FIELDS = ('model_revision', 'tokenizer_revision', 'dtype', 'gpu_product',
                 'gpu_count', 'node_count', 'max_model_len', 'chat_template_sha256',
                 'cache_mode', 'tensor_parallel', 'pipeline_parallel', 'data_parallel')
class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None  # Never forward a benchmark credential to another endpoint.


POLICY = 'Aurora Supply is a fictional distributor. This frozen benchmark snapshot uses synthetic historical data, not live inventory. Recommend a replenishment proposal, never place an order. Target stock is max(reorder_point, ceil(forecast_7d_units * 21 / 7)); quantity is max(0, target_stock - stock). A human must review supplier lead time. Proposals above 5000 demo currency units require operations-manager approval; otherwise assigned-buyer approval. Forecast origin is 2025-12-31.\n'
INVENTORY = '[{"category":"Filters","forecast_7d_units":130.26,"lead_time_days":5,"name":"H20 Hydraulic Filter","reorder_point":80,"sku":"AS-001","stock":45,"unit_price":42.0},{"category":"Sensors","forecast_7d_units":54.75,"lead_time_days":7,"name":"P10 Pressure Sensor","reorder_point":35,"sku":"AS-002","stock":120,"unit_price":125.0},{"category":"Valves","forecast_7d_units":43.47,"lead_time_days":10,"name":"V30 Control Valve","reorder_point":30,"sku":"AS-003","stock":18,"unit_price":210.0},{"category":"Hoses","forecast_7d_units":152.82,"lead_time_days":4,"name":"M15 Industrial Hose","reorder_point":70,"sku":"AS-004","stock":240,"unit_price":32.0},{"category":"Seals","forecast_7d_units":216.83,"lead_time_days":3,"name":"O25 O-ring Seal","reorder_point":100,"sku":"AS-005","stock":75,"unit_price":8.5},{"category":"Connectors","forecast_7d_units":97.47,"lead_time_days":6,"name":"C40 Quick Connector","reorder_point":50,"sku":"AS-006","stock":90,"unit_price":18.0},{"category":"Pumps","forecast_7d_units":22.5,"lead_time_days":14,"name":"B50 Compact Pump","reorder_point":12,"sku":"AS-007","stock":8,"unit_price":650.0},{"category":"Meters","forecast_7d_units":32.12,"lead_time_days":8,"name":"F60 Flow Meter","reorder_point":15,"sku":"AS-008","stock":35,"unit_price":290.0}]'



def digest(value):
    return hashlib.sha256(value.encode()).hexdigest()


def messages(index, mode='repeated-prefix'):
    # Fixed-width control salts make the common-prefix and control cases comparable
    # in characters, but actual token counts must still come from server usage.
    salt = '00000000' if mode == 'repeated-prefix' else f'{index+1:08d}'
    return [{'role':'system','content':f'Synthetic experiment {salt}.\n'+POLICY+INVENTORY},
            {'role':'user','content':f'For SKU AS-{index%8+1:03d}, explain whether stock covers lead time and propose a quantity. Use at most three concise sentences.'}]


def percentile(values, q):
    if not values:
        return None
    vals = sorted(values)
    pos = (len(vals)-1) * q
    low, high = math.floor(pos), math.ceil(pos)
    return vals[low] + (vals[high]-vals[low])*(pos-low)


def summarize(rows, elapsed):
    ok = [r for r in rows if r.get('ok')]
    latencies = [r['latency_ms'] for r in ok]
    ttfts = [r['ttft_ms'] for r in ok if r.get('ttft_ms') is not None]
    exact_usage = bool(ok) and all(r.get('completion_tokens') is not None for r in ok)
    total = sum(r['completion_tokens'] for r in ok) if exact_usage else None
    return {'requests':len(rows), 'successful_requests':len(ok), 'errors':len(rows)-len(ok),
            'elapsed_seconds':elapsed, 'requests_per_second':len(ok)/elapsed if elapsed>0 else None,
            'completion_tokens':total,
            'output_tokens_per_second':total/elapsed if total is not None and elapsed>0 else None,
            'latency_ms':{'p50':percentile(latencies,.5),'p95':percentile(latencies,.95),'p99':percentile(latencies,.99)},
            'ttft_ms':{'p50':percentile(ttfts,.5),'p95':percentile(ttfts,.95),'p99':percentile(ttfts,.99)},
            'usage_complete':exact_usage}


def parse_sse(lines, started, clock=time.monotonic):
    first = None
    usage = {}
    done = False
    chunks = 0
    for raw in lines:
        line = raw.decode('utf-8') if isinstance(raw, bytes) else raw
        if not line.startswith('data:'):
            continue
        data = line[5:].strip()
        if not data:
            continue
        if data == '[DONE]':
            done = True
            break
        event = json.loads(data)
        if event.get('error'):
            raise ValueError('endpoint emitted an SSE error')
        if event.get('usage'):
            usage = event['usage']
        for choice in event.get('choices', []):
            delta = choice.get('delta', {})
            # Role-only chunks are not tokens. A reasoning delta is real generated
            # output and counts towards first content; record this definition.
            if delta.get('content') or delta.get('reasoning_content'):
                chunks += 1
                if first is None:
                    first = (clock()-started)*1000
    if not done:
        raise ValueError('stream ended without [DONE]')
    if first is None:
        raise ValueError('stream completed without generated content')
    for field in ('prompt_tokens','completion_tokens','total_tokens'):
        value = usage.get(field)
        if value is not None and (not isinstance(value,int) or isinstance(value,bool) or value < 0):
            raise ValueError('endpoint emitted invalid token usage')
    return {'ttft_ms':first, 'content_chunks':chunks,
            'prompt_tokens':usage.get('prompt_tokens'), 'completion_tokens':usage.get('completion_tokens'),
            'total_tokens':usage.get('total_tokens')}


def bounded_sse_lines(response, deadline, clock=time.monotonic,
                      max_bytes=4*1024*1024, max_line_bytes=64*1024):
    """Bound bytes and wall time even when an endpoint never finishes a line."""
    pending = bytearray()
    received = 0
    # urllib's HTTPResponse exposes the active socket through its buffered reader.
    # read1 returns after one underlying read, unlike readline/read which may keep
    # accepting trickled data forever without yielding to a deadline check.
    sock = getattr(getattr(getattr(response, 'fp', None), 'raw', None), '_sock', None)
    while True:
        remaining = deadline - clock()
        if remaining <= 0:
            raise TimeoutError('per-request total duration exceeded')
        if sock is not None:
            sock.settimeout(remaining)
        chunk = response.read1(8192)
        if clock() > deadline:
            raise TimeoutError('per-request total duration exceeded')
        if not chunk:
            if pending:
                yield bytes(pending)
            return
        received += len(chunk)
        if received > max_bytes:
            raise ValueError('SSE response exceeded the byte limit')
        pending.extend(chunk)
        while b'\n' in pending:
            end = pending.index(b'\n') + 1
            if end > max_line_bytes:
                raise ValueError('SSE line exceeded the byte limit')
            yield bytes(pending[:end])
            del pending[:end]
        if len(pending) > max_line_bytes:
            raise ValueError('SSE line exceeded the byte limit')


def request_once(url, model, key, index, args):
    started = time.monotonic()
    row = {'index':index, 'started_at':dt.datetime.now(dt.timezone.utc).isoformat(),
           'prompt_sha256':digest(json.dumps(messages(index,args.prefix_mode),sort_keys=True))}
    payload = {'model':model,'messages':messages(index,args.prefix_mode),
               'stream':True,'stream_options':{'include_usage':True},
               'max_tokens':args.max_tokens,'temperature':0,'seed':42,
               'chat_template_kwargs':{'enable_thinking':False}}
    headers = {'Content-Type':'application/json','Accept':'text/event-stream'}
    if key:
        headers['Authorization'] = 'Bearer '+key
    request = urllib.request.Request(url, data=json.dumps(payload).encode(), headers=headers)
    try:
        with urllib.request.build_opener(NoRedirect).open(request, timeout=args.timeout) as response:
            row['http_status'] = response.status
            deadline = started + args.timeout
            row.update(parse_sse(bounded_sse_lines(response, deadline), started))
            row['ok'] = response.status == 200
    except urllib.error.HTTPError as exc:
        row.update(ok=False,http_status=exc.code,error='HTTPError')
    except (OSError, ValueError, TimeoutError) as exc:
        # Never log error bodies/headers; they can contain credentials or payloads.
        row.update(ok=False,error=type(exc).__name__)
    row['latency_ms'] = (time.monotonic()-started)*1000
    if row.get('completion_tokens',0) and row['completion_tokens'] > 1 and row.get('ttft_ms') is not None:
        row['tpot_ms'] = max(0,row['latency_ms']-row['ttft_ms'])/(row['completion_tokens']-1)
    else:
        row['tpot_ms'] = None
    return row


def validate_metadata(meta):
    missing = [k for k in COMMON_FIELDS+('engine','image_digest','scheduling') if k not in meta]
    if missing:
        raise ValueError('Metadata missing: '+', '.join(missing))
    for field in ('model_revision','tokenizer_revision'):
        if len(meta[field]) != 40 or any(c not in '0123456789abcdef' for c in meta[field]):
            raise ValueError(field+' must be an immutable HF commit SHA')
    if len(meta['chat_template_sha256']) != 64:
        raise ValueError('chat_template_sha256 must identify the effective template')
    if '@sha256:' not in meta['image_digest']:
        raise ValueError('image_digest must pin the actual runtime image')
    for field in ('gpu_count','node_count','max_model_len'):
        if not isinstance(meta[field],int) or meta[field] < 1:
            raise ValueError(field+' must be positive')
    if meta['gpu_count'] > 16:
        raise ValueError('benchmark metadata exceeds showroom physical GPU ceiling')


def run(args):
    for field, ceiling in LIMITS.items():
        value = getattr(args, field)
        if value < 1 or value > ceiling:
            raise ValueError(f'{field} must be 1..{ceiling}')
    if not 1 <= args.timeout <= 120 or not 0 <= args.warmup <= 10:
        raise ValueError('timeout must be 1..120 seconds; warmup 0..10')
    url = urllib.parse.urlsplit(args.base_url)
    if url.username or url.password or url.query or url.fragment:
        raise ValueError('URL must not contain credentials, query, or fragment')
    if url.scheme != 'https' and not (url.scheme=='http' and url.hostname in ('127.0.0.1','localhost','::1')):
        raise ValueError('Use HTTPS or an authenticated localhost port-forward; TLS verification is required')
    meta = json.loads(args.metadata.read_text())
    validate_metadata(meta)
    key = os.environ.get(args.key_env)
    endpoint = args.base_url.rstrip('/')+'/chat/completions'
    warmup = [request_once(endpoint,args.model,key,-i-1,args) for i in range(args.warmup)]
    if any(not r['ok'] for r in warmup):
        raise ValueError('Warmup failed; no performance claim can be made')
    start = time.monotonic()
    rows = []
    def bounded_request(i):
        if time.monotonic()-start >= args.duration:
            return {'index':i,'ok':False,'error':'RunDeadline','latency_ms':0}
        return request_once(endpoint,args.model,key,i,args)
    with ThreadPoolExecutor(max_workers=args.concurrency) as executor:
        futures = [executor.submit(bounded_request,i) for i in range(args.requests)]
        for future in as_completed(futures):
            rows.append(future.result())
    elapsed = time.monotonic()-start
    config = {'requests':args.requests,'concurrency':args.concurrency,'max_tokens':args.max_tokens,
              'prefix_mode':args.prefix_mode,'temperature':0,'seed':42,'enable_thinking':False,
              'warmup':args.warmup,'timeout':args.timeout,'duration':args.duration,
              'workload_sha256':digest(json.dumps([messages(i,args.prefix_mode) for i in range(args.requests)],sort_keys=True))}
    result = {'schema_version':1,'status':'MEASURED' if all(r['ok'] for r in rows) else 'FAILED',
              'created_at':dt.datetime.now(dt.timezone.utc).isoformat(), 'metadata':meta,'config':config,
              'measurement_boundary':'HTTP client send to completed SSE; TTFT=first nonempty content/reasoning delta',
              'endpoint_sha256':digest(args.base_url), 'warmup':warmup,
              'summary':summarize(rows,elapsed),'requests':sorted(rows,key=lambda r:r['index'])}
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({'status':result['status'],'output':str(args.output),'summary':result['summary']},indent=2))
    return 0 if result['status']=='MEASURED' else 2


def compare_results(a, b, comparison):
    differences = []
    if a.get('status') != 'MEASURED' or b.get('status') != 'MEASURED':
        differences.append('Both runs must be successfully measured.')
    for field in COMMON_FIELDS:
        if a['metadata'].get(field) != b['metadata'].get(field):
            differences.append('metadata.'+field)
    for field in ('requests','concurrency','max_tokens','prefix_mode','temperature','seed','enable_thinking','warmup','workload_sha256'):
        if a['config'].get(field) != b['config'].get(field):
            differences.append('config.'+field)
    if comparison == 'routing':
        if a['metadata']['engine'] != b['metadata']['engine']:
            differences.append('Routing comparison must keep the inference engine fixed.')
        if a['metadata']['image_digest'] != b['metadata']['image_digest']:
            differences.append('Routing comparison must keep the image digest fixed.')
    elif a['metadata'].get('gpu_count') != 1 or a['metadata'].get('node_count') != 1:
        differences.append('Engine reference comparison requires one GPU on one node.')
    if differences:
        return {'status':'BLOCKED','incomparable':differences}
    at = a['summary'].get('output_tokens_per_second')
    bt = b['summary'].get('output_tokens_per_second')
    return {'status':'COMPARABLE','comparison':comparison,
            'b_over_a_output_tokens_per_second':bt/at if at and bt is not None else None,
            'a_summary':a['summary'],'b_summary':b['summary'],
            'interpretation':'Observed workload only; repeat runs and inspect quality/errors. No universal speedup is implied.'}


def serve_transformers(args):
    # Deliberately lazy imports: the measurement client needs only Python stdlib.
    import threading
    import torch
    from transformers import AutoTokenizer, AutoModelForCausalLM
    from transformers.generation.streamers import BaseStreamer
    import queue
    from fastapi import FastAPI, Request, HTTPException
    from fastapi.responses import StreamingResponse
    import uvicorn
    if args.host not in ('127.0.0.1','localhost','::1') and not os.environ.get(args.key_env):
        raise ValueError('A bound external server requires a benchmark API key in the selected environment variable')
    tokenizer = AutoTokenizer.from_pretrained(args.model_path, revision=args.revision, trust_remote_code=False)
    model = AutoModelForCausalLM.from_pretrained(args.model_path,revision=args.revision,
        torch_dtype=torch.bfloat16,trust_remote_code=False).to('cuda').eval()
    class TokenStreamer(BaseStreamer):
        # Emit decoded token increments, avoiding TextIteratorStreamer's word
        # buffering which would otherwise bias first-content latency.
        def __init__(self):
            self.items = queue.Queue(); self.first = True; self.ids = []; self.text = ''
        def put(self, value):
            if self.first:
                self.first = False; return
            self.ids.extend(value.reshape(-1).tolist())
            decoded = tokenizer.decode(self.ids, skip_special_tokens=True)
            if decoded.endswith('\ufffd'):
                return
            fragment = decoded[len(self.text):]
            self.text = decoded
            if fragment:
                self.items.put(fragment)
        def end(self):
            self.items.put(None)
        def __iter__(self):
            while True:
                item = self.items.get(timeout=90)
                if item is None:
                    return
                yield item
    lock = threading.Lock()
    app = FastAPI()
    # FastAPI resolves annotations against globals; Request is lazily imported.
    globals()['Request'] = Request
    @app.get('/health')
    def health():
        return {'ready':True,'engine':'transformers','batch_size':1}
    @app.post('/v1/chat/completions')
    async def completion(request: Request):
        expected = os.environ.get(args.key_env)
        if expected and request.headers.get('authorization') != 'Bearer '+expected:
            raise HTTPException(401,'Unauthorized')
        body = await request.json()
        if body.get('model') != args.served_model:
            raise HTTPException(400,'Unknown model')
        n = body.get('max_tokens',64)
        if not isinstance(n,int) or not 1 <= n <= 256 or body.get('stream') is not True:
            raise HTTPException(400,'stream=true and max_tokens=1..256 required')
        if body.get('temperature',0) != 0:
            raise HTTPException(400,'Reference server supports deterministic temperature=0 only')
        inputs = tokenizer.apply_chat_template(body['messages'],tokenize=True,
            add_generation_prompt=True,return_tensors='pt',enable_thinking=False)
        if inputs.shape[-1]+n > args.max_model_len:
            raise HTTPException(400,'Context length exceeded')
        def events():
            with lock, torch.inference_mode():
                streamer = TokenStreamer()
                generated = []
                errors = []
                def generate():
                    try:
                        with torch.inference_mode():
                            generated.append(model.generate(inputs.to('cuda'),do_sample=False,
                                max_new_tokens=n,streamer=streamer))
                    except Exception as exc:
                        errors.append(type(exc).__name__)
                        streamer.end()
                worker = threading.Thread(target=generate)
                worker.start()
                for fragment in streamer:
                    if fragment:
                        yield 'data: '+json.dumps({'choices':[{'delta':{'content':fragment}}]})+'\n\n'
                worker.join(timeout=90)
                if errors or not generated:
                    yield 'data: '+json.dumps({'error':{'message':'generation failed'}})+'\n\n'
                    return
                output_tokens = generated[0].shape[-1]-inputs.shape[-1]
                yield 'data: '+json.dumps({'choices':[],'usage':{'prompt_tokens':inputs.shape[-1],
                    'completion_tokens':output_tokens,'total_tokens':inputs.shape[-1]+output_tokens}})+'\n\n'
                yield 'data: [DONE]\n\n'
        return StreamingResponse(events(),media_type='text/event-stream')
    uvicorn.run(app,host=args.host,port=args.port,access_log=False)
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command',required=True)
    p = commands.add_parser('run')
    p.add_argument('--base-url',required=True,help='OpenAI base ending /v1')
    p.add_argument('--model',required=True)
    p.add_argument('--metadata',type=Path,required=True)
    p.add_argument('--key-env',default='SHOWROOM_API_KEY')
    p.add_argument('--requests',type=int,default=12)
    p.add_argument('--concurrency',type=int,default=2)
    p.add_argument('--max-tokens',type=int,default=64)
    p.add_argument('--warmup',type=int,default=2)
    p.add_argument('--duration',type=int,default=300)
    p.add_argument('--timeout',type=int,default=60)
    p.add_argument('--prefix-mode',choices=['repeated-prefix','distinct-prefix'],default='repeated-prefix')
    p.add_argument('--output',type=Path,required=True)
    p = commands.add_parser('compare')
    p.add_argument('a',type=Path); p.add_argument('b',type=Path)
    p.add_argument('--kind',choices=['engine','routing'],required=True)
    p.add_argument('--output',type=Path)
    p = commands.add_parser('serve-transformers')
    p.add_argument('--model-path',required=True)
    p.add_argument('--revision',required=True)
    p.add_argument('--served-model',default='aurora-qwen-4b')
    p.add_argument('--key-env',default='SHOWROOM_BENCHMARK_KEY')
    p.add_argument('--host',default='127.0.0.1')
    p.add_argument('--port',type=int,default=8000)
    p.add_argument('--max-model-len',type=int,default=8192)
    args = parser.parse_args(argv)
    try:
        if args.command == 'run':
            return run(args)
        if args.command == 'serve-transformers':
            return serve_transformers(args)
        a,b = json.loads(args.a.read_text()),json.loads(args.b.read_text())
        result = compare_results(a,b,args.kind)
        rendered = json.dumps(result,indent=2)+'\n'
        print(rendered,end='')
        if args.output:
            args.output.parent.mkdir(parents=True,exist_ok=True); args.output.write_text(rendered)
        return 0 if result['status']=='COMPARABLE' else 2
    except (ValueError,KeyError,OSError,ImportError) as exc:
        print(json.dumps({'status':'BLOCKED','reason':str(exc)}),file=sys.stderr)
        return 2


if __name__ == '__main__':
    sys.exit(main())
