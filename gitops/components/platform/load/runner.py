#!/usr/bin/env python3
"""Run bounded GuideLLM segments until an absolute UTC deadline; keep real reports."""
import datetime as dt
import json
import os
from pathlib import Path
import signal
import subprocess
import threading
import time
import urllib.parse

UTC = dt.timezone.utc
ROOT = Path('/results')
STOP = dt.datetime.fromisoformat(os.environ['STOP_AT'].replace('Z', '+00:00'))
WINDOW_START = dt.datetime.fromisoformat(os.environ['DEMO_START'].replace('Z', '+00:00'))
WINDOW_END = dt.datetime.fromisoformat(os.environ['DEMO_END'].replace('Z', '+00:00'))
TERMINATING = False
CHILD = None


def now():
    return dt.datetime.now(UTC)


def stop_signal(*_):
    global TERMINATING
    TERMINATING = True
    if CHILD and CHILD.poll() is None:
        os.killpg(CHILD.pid, signal.SIGTERM)


def emit(event):
    event['timestamp'] = now().isoformat()
    print(json.dumps(event), flush=True)
    with (ROOT / 'history.jsonl').open('a') as f:
        f.write(json.dumps(event) + '\n')
        f.flush()
        os.fsync(f.fileno())


def sleep_bounded(seconds):
    end = min(time.monotonic() + seconds, time.monotonic() + max(0, (STOP - now()).total_seconds()))
    while not TERMINATING and time.monotonic() < end:
        time.sleep(max(0, min(1, end - time.monotonic())))


def metrics_summary(path):
    report = json.loads(path.read_text())
    result = []
    for benchmark in report.get('benchmarks', []):
        metrics = benchmark.get('metrics', {})
        summary = {'request_totals': metrics.get('request_totals')}
        for key in ('request_latency', 'time_to_first_token_ms', 'requests_per_second',
                    'prompt_tokens_per_second', 'output_tokens_per_second',
                    'prompt_token_count', 'output_token_count'):
            value = metrics.get(key, {})
            successful = value.get('successful', {}) if isinstance(value, dict) else {}
            summary[key] = {name: successful.get(name) for name in ('mean', 'total_sum')}
            summary[key]['p95'] = successful.get('percentiles', {}).get('p95')
        result.append(summary)
    return result


def main():
    global CHILD
    if STOP.tzinfo is None or WINDOW_START.tzinfo is None or WINDOW_END.tzinfo is None:
        raise ValueError('Every deadline must include a timezone')
    ROOT.mkdir(exist_ok=True)
    signal.signal(signal.SIGTERM, stop_signal)
    signal.signal(signal.SIGINT, stop_signal)
    emit({'event': 'starting', 'stop_at': STOP.isoformat(), 'guidellm_version': '0.7.4', 'tokenizer_ready': False})
    while not (ROOT / 'tokenizer/.ready').exists() and now() < STOP and not TERMINATING:
        sleep_bounded(2)
    if now() >= STOP or TERMINATING:
        emit({'event': 'stopped', 'reason': 'absolute deadline or termination'})
        return
    key = Path('/credentials/api-key').read_text().strip()
    base = Path('/credentials/base-url').read_text().strip().removesuffix('/v1').rstrip('/')
    parsed = urllib.parse.urlsplit(base)
    if parsed.scheme != 'https' or parsed.username or parsed.password or parsed.path or not parsed.hostname:
        raise ValueError('Credential endpoint must be an HTTPS origin without userinfo')
    model = Path('/credentials/model-id').read_text().strip()
    backend = {'kind': 'openai_http', 'target': base, 'model': model, 'api_key': key,
               'request_format': '/v1/chat/completions', 'api_routes': {'/health': 'v1/models'},
               'timeout': 30, 'timeout_connect': 10,
               'verify': True, 'follow_redirects': False, 'http2': False, 'max_tokens': 128,
               'extras': {'headers': {'X-Showroom-Client': 'guidellm-sustained'}, 'body': {'temperature': 0}}}
    env = dict(os.environ, GUIDELLM__SPEC__BACKEND=json.dumps(backend),
               HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1', TOKENIZERS_PARALLELISM='false')
    sequence = 0
    failures = 0
    while now() < STOP and not TERMINATING:
        clock = now()
        protected = WINDOW_START <= clock < WINDOW_END
        cap = 0.1
        control = ROOT / 'control.json'
        if control.exists():
            cap = json.loads(control.read_text()).get('max_rate', 0.1)
        if cap not in (0.05, 0.1, 0.25, 0.5):
            raise ValueError('max_rate must be one of 0.05, 0.1, 0.25, or 0.5')
        rate = 0.05 if protected else min(cap, (0.1, 0.25, 0.5)[sequence % 3])
        concurrency = 1 if protected else 2
        boundary = min([STOP] + [value for value in (WINDOW_START, WINDOW_END) if value > clock])
        available = (boundary - clock).total_seconds()
        duration = min(60 if sequence == 0 else 600, int(available - 45))
        if duration < 20:
            sleep_bounded(available)
            continue
        stamp = clock.strftime('%Y%m%dT%H%M%S')
        segment = ROOT / ('segment-' + stamp)
        segment.mkdir(exist_ok=False)
        command = ['guidellm', 'run', '--profile', f'kind=constant,rate={rate},max_concurrency={concurrency}',
                   '--constraint', f'kind=max_duration,seconds={duration}', '--constraint', 'kind=max_errors,count=5',
                   '--data', 'kind=synthetic_text,prompt_tokens=256,output_tokens=128',
                   '--tokenizer', json.dumps({'kind': 'huggingface_auto', 'model': '/results/tokenizer',
                                              'load_kwargs': {'local_files_only': True, 'trust_remote_code': False}}),
                   '--metrics', 'kind=generative,sample_size=0', '--disable-console-interactive',
                   '--output', f'kind=json,path={segment}/benchmarks.json',
                   '--output', f'kind=csv,path={segment}/benchmarks.csv',
                   '--output', f'kind=html,path={segment}/benchmarks.html']
        emit({'event': 'segment_started', 'segment': segment.name, 'requested_rps': rate,
              'max_concurrency': concurrency, 'duration_seconds': duration, 'protected_demo_window': protected})
        with (segment / 'console.log').open('w') as log:
            CHILD = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, env=env,
                                     text=True, start_new_session=True)
            def capture():
                for line in CHILD.stdout:
                    log.write(line.replace(key, '[REDACTED]'))
                    log.flush()
            reader = threading.Thread(target=capture, daemon=True)
            reader.start()
            timeout = min(duration + 90, max(0.1, (STOP - now()).total_seconds()))
            try:
                code = CHILD.wait(timeout=timeout)
            except subprocess.TimeoutExpired:
                os.killpg(CHILD.pid, signal.SIGKILL if now() >= STOP else signal.SIGTERM)
                try:
                    code = CHILD.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    os.killpg(CHILD.pid, signal.SIGKILL)
                    code = CHILD.wait(timeout=5)
            reader.join(timeout=5)
        # Defense in depth: never retain the secret in serialized backend metadata.
        for path in segment.iterdir():
            if path.is_file():
                raw = path.read_bytes()
                if key.encode() in raw:
                    path.write_bytes(raw.replace(key.encode(), b'[REDACTED]'))
        report = segment / 'benchmarks.json'
        summary = metrics_summary(report) if report.exists() else []
        emit({'event': 'segment_finished', 'segment': segment.name, 'exit_code': code,
              'elapsed_seconds': (now() - clock).total_seconds(), 'metrics': summary})
        failed_requests = sum((row.get('request_totals') or {}).get('errored', 0) for row in summary)
        successful_requests = sum((row.get('request_totals') or {}).get('successful', 0) for row in summary)
        failures = failures + 1 if code != 0 or not summary or failed_requests >= 5 or successful_requests == 0 else 0
        if failures >= 3:
            emit({'event': 'blocked', 'reason': 'three consecutive failed segments; inspect retained console logs'})
            raise SystemExit(2)
        sequence += 1
        sleep_bounded(30 if failures else 3)
    emit({'event': 'stopped', 'reason': 'absolute deadline or termination', 'stop_at': STOP.isoformat()})


if __name__ == '__main__':
    main()
