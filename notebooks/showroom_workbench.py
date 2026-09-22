"""Bounded, credential-safe traffic for the Aurora Inference Demo kernel.

The same-namespace Gateway hop is HTTP by design; no TLS verification is disabled.
Native Kubernetes token authentication and model authorization still apply.
"""
from __future__ import annotations

import asyncio
import csv
from datetime import datetime, timezone
import getpass
import hashlib
import io
import json
import math
import os
from pathlib import Path
import re
import time
from urllib.parse import urlsplit, urlunsplit
import uuid

BASE_URL = 'http://showroom-inference-maas-gateway-class.ai-showroom.svc.cluster.local:8080/ai-showroom/aurora-qwen-4b/v1'
MODEL = 'aurora-qwen-4b'
_TRUSTED_HOST = 'showroom-inference-maas-gateway-class.ai-showroom.svc.cluster.local'
TOKEN_PATH = Path('/var/run/secrets/kubernetes.io/serviceaccount/token')
NAMESPACE_PATH = TOKEN_PATH.with_name('namespace')
RESULTS_ROOT = Path('/opt/app-root/src/.local/share/aurora-showroom/notebook-results')
MAX_SECONDS, MAX_REQUESTS, MAX_OUTPUT_TOKENS, MAX_CONCURRENCY = 180, 30, 256, 2
PROMPTS = (
    'Aurora Supply is a synthetic inventory demo. A proposal adds 346 units at 42 demo currency units each. '
    'Totals above 5000 require an Operations manager. Explain the approval in two short sentences; no order is executed.',
    'For a synthetic Aurora Supply replenishment proposal, list three facts a human should verify before approval. '
    'Keep the answer short. You have no live inventory tools in this notebook.',
    'Aurora Supply uses a historical seven-day demand forecast. In three short bullets, explain why a forecast '
    'does not by itself authorize a purchase. Do not claim to have created an order.',
)
_SYSTEM = ('You are explaining the synthetic Aurora Supply demonstration. Give concise advisory answers. '
           'Do not claim live tool access, verified facts beyond the supplied prompt, or executed purchases.')


def validate_config(config=None) -> dict:
    """Validate nonsecret target settings before any credential is read or entered."""
    config = {'base_url': BASE_URL, 'model_id': MODEL, 'auth_mode': 'service_account'} if config is None else dict(config)
    if set(config) != {'base_url', 'model_id', 'auth_mode'}:
        raise ValueError('Connection settings must contain only base_url, model_id, and auth_mode.')
    base, model, mode = (config[key] for key in ('base_url', 'model_id', 'auth_mode'))
    if not isinstance(base, str) or not 1 <= len(base) <= 2048 or any(c.isspace() or ord(c) < 32 or ord(c) == 127 or c == '\\' for c in base):
        raise ValueError('Use an explicit OpenAI-compatible base URL without whitespace or backslashes.')
    if not isinstance(model, str) or not 1 <= len(model) <= 200 or any(c.isspace() or ord(c) < 32 or ord(c) == 127 for c in model):
        raise ValueError('MODEL_ID must be the exact nonempty served model ID, without whitespace.')
    if mode not in ('service_account', 'api_key'):
        raise ValueError('AUTH_MODE must be service_account or api_key.')
    try:
        uri = urlsplit(base)
        port = uri.port
    except ValueError:
        raise ValueError('The base URL has an invalid host or port.') from None
    if not uri.hostname or uri.username is not None or uri.password is not None or uri.query or uri.fragment or '?' in base or '#' in base:
        raise ValueError('The base URL must not contain credentials, query parameters, or a fragment.')
    path = uri.path.rstrip('/')
    native = (uri.scheme == 'http' and uri.hostname == _TRUSTED_HOST and port == 8080
              and len(model) <= 63 and re.fullmatch(r'[a-z0-9](?:[a-z0-9-]*[a-z0-9])?', model)
              and path == f'/ai-showroom/{model}/v1')
    if mode == 'service_account' and not native:
        raise ValueError('Workload tokens are allowed only at the exact private Gateway:8080 /ai-showroom/{MODEL_ID}/v1 route. Use api_key mode for another HTTPS endpoint.')
    if mode == 'api_key' and uri.scheme != 'https':
        raise ValueError('API-key mode requires HTTPS. The private HTTP Gateway preset uses service_account mode.')
    if not path.endswith('/v1'):
        raise ValueError('Use the OpenAI-compatible base URL ending in /v1; /models and /chat/completions must be supported.')
    normalized = urlunsplit((uri.scheme, f'{_TRUSTED_HOST}:8080' if native else uri.netloc, path, '', ''))
    return {'base_url': normalized, 'model_id': model, 'auth_mode': mode}


class ApiKeyCredential:
    """In-memory, exact-endpoint binding. Its representation never includes the key."""
    def __init__(self, base_url, value):
        self._base_url, self._value, self._nonce = base_url, value, uuid.uuid4().hex

    def __repr__(self):
        return 'ApiKeyCredential(value=REDACTED, endpoint_bound=True)'


def bind_api_key(config, raw_key):
    """Bind a getpass-entered key, or a child-stdin key, to one validated endpoint."""
    config = validate_config(config)
    if config['auth_mode'] != 'api_key':
        raise ValueError('An entered key is accepted only in api_key mode.')
    if not isinstance(raw_key, str) or not 1 <= len(raw_key) <= 16384 or any(c.isspace() for c in raw_key):
        raise ValueError('Enter a nonempty API key without whitespace.')
    return ApiKeyCredential(config['base_url'], raw_key)


def prompt_api_key(config):
    config = validate_config(config)
    if config['auth_mode'] != 'api_key':
        raise ValueError('Choose api_key mode before entering a key.')
    return bind_api_key(config, getpass.getpass('API key for the configured endpoint (hidden): '))


def connection(config=None, *, api_key=None) -> dict:
    """Return credentials in memory only. Never display or serialize this dictionary."""
    config = validate_config(config)
    if config['auth_mode'] == 'api_key':
        if not isinstance(api_key, ApiKeyCredential) or api_key._base_url != config['base_url']:
            raise ValueError('Enter a new endpoint-bound key for the selected URL; credentials are not reused across endpoints.')
        return {'base_url': config['base_url'], 'model': config['model_id'], 'api_key': api_key._value}
    if api_key is not None:
        raise ValueError('Do not supply an entered API key in service_account mode.')
    if NAMESPACE_PATH.read_text().strip() != 'ai-showroom':
        raise RuntimeError('Use the authorized Aurora workbench in project ai-showroom.')
    token = TOKEN_PATH.read_text().strip()
    if not token or any(char.isspace() for char in token):
        raise RuntimeError('The projected workload credential is unavailable or invalid.')
    return {'base_url': config['base_url'], 'model': config['model_id'], 'api_key': token}


def _target_fingerprint(config, api_key):
    binding = api_key._nonce if isinstance(api_key, ApiKeyCredential) else ''
    return hashlib.sha256((json.dumps(config, sort_keys=True) + binding).encode()).hexdigest()


async def preflight(config=None, *, api_key=None):
    """Check /models and the exact served ID; returns only sanitized diagnostics."""
    import httpx
    config = validate_config(config)
    result = {'ok': False, 'stage': 'models', 'http_status': None, 'model_id': config['model_id'],
              'model_listed': False, 'error_code': None, 'message': ''}
    try:
        cfg = connection(config, api_key=api_key)
        async with httpx.AsyncClient(follow_redirects=False, trust_env=False) as client:
            async with asyncio.timeout(10):
                async with client.stream('GET', cfg['base_url'] + '/models',
                        headers={'Authorization': 'Bearer ' + cfg['api_key']},
                        timeout=httpx.Timeout(8, connect=5)) as response:
                    result['http_status'] = response.status_code
                    if response.status_code != 200:
                        result['error_code'] = f'HTTP_{response.status_code}'
                        result['message'] = {
                            401: 'Credential rejected. Check its validity; do not print or paste it into logs.',
                            403: 'Access denied. The native Workbench preset is authorized only for Qwen; another model needs an operator-approved exact model grant and route. API keys need permission for the selected endpoint/model.',
                            404: 'The selected route or OpenAI-compatible /models endpoint was not found.',
                        }.get(response.status_code, 'The /models preflight failed. Redirects are not followed; inspect endpoint readiness and API compatibility.')
                        return result
                    chunks, size = [], 0
                    async for chunk in response.aiter_bytes():
                        size += len(chunk)
                        if size > 1024 * 1024:
                            raise ValueError('Models response exceeds limit')
                        chunks.append(chunk)
                    models = json.loads(b''.join(chunks)).get('data')
        if not isinstance(models, list):
            raise ValueError('Models response is not OpenAI-compatible')
        result['model_listed'] = any(isinstance(model, dict) and model.get('id') == config['model_id'] for model in models)
        result.update(ok=result['model_listed'], error_code=None if result['model_listed'] else 'MODEL_NOT_LISTED',
                      message='Selected served model is listed and authorized.' if result['model_listed'] else 'MODEL_ID is not listed by this endpoint. Use the exact served ID and confirm that the deployment is Ready.')
    except (TimeoutError, httpx.TimeoutException):
        result.update(error_code='NETWORK_TIMEOUT', message='Endpoint timed out. Check its Route/Service, Workbench network access, and readiness.')
    except httpx.TransportError:
        result.update(error_code='NETWORK_OR_TLS_ERROR', message='Cannot connect securely. Check DNS, network policy, and the endpoint certificate/trust chain; do not disable TLS verification.')
    except Exception:
        result.update(error_code='PREFLIGHT_FAILED', message='Check the credential binding and OpenAI-compatible /models response. No raw error body is recorded.')
    return result


def _integer(name, value, minimum, maximum):
    if type(value) is not int or not minimum <= value <= maximum:
        raise ValueError(f'{name} must be an integer from {minimum} to {maximum}.')


def _number(name, value, minimum, maximum):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or not minimum <= value <= maximum:
        raise ValueError(f'{name} must be a finite number from {minimum} to {maximum}.')


def _prompts(values):
    if isinstance(values, str) or not isinstance(values, (list, tuple)) or not 1 <= len(values) <= 10:
        raise ValueError('prompts must contain between 1 and 10 synthetic strings.')
    if any(not isinstance(value, str) or not value.strip() or len(value) > 2000 for value in values):
        raise ValueError('Each synthetic prompt must contain between 1 and 2000 characters.')
    return tuple(values)


def _utc():
    return datetime.now(timezone.utc).isoformat()


def _row(number):
    return {'request': number, 'started_at_utc': _utc(), 'finished_at_utc': None,
            'elapsed_s': None, 'status': 'started', 'http_status': None,
            'input_tokens': None, 'output_tokens': None, 'total_tokens': None,
            'error_code': None}


def _safe_answer(answer, credential):
    """Prevent an upstream echo of credentials from entering notebook output."""
    answer = answer.replace(credential, '[REDACTED_CREDENTIAL]')
    answer = re.sub(r'(?i)\bbearer\s+[^\s"\'<>]+', 'Bearer [REDACTED_CREDENTIAL]', answer)
    return re.sub(r'\beyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\b', '[REDACTED_JWT]', answer)


async def _request(client, prompt, max_tokens, deadline, row, config, api_key):
    """Keep response text only in memory; persist only the fixed metrics schema."""
    import httpx
    started = time.monotonic()
    answer = None
    try:
        remaining = deadline - started
        if remaining <= 0:
            raise TimeoutError
        cfg = connection(config, api_key=api_key)  # Read a workload token immediately before each request.
        body = {'model': cfg['model'], 'messages': [{'role': 'system', 'content': _SYSTEM},
                {'role': 'user', 'content': prompt}], 'max_tokens': max_tokens,
                'temperature': 0.2, 'stream': False}
        async with client.stream('POST', cfg['base_url'] + '/chat/completions', json=body,
                headers={'Authorization': 'Bearer ' + cfg['api_key'], 'Content-Type': 'application/json'},
                timeout=httpx.Timeout(min(20, remaining), connect=min(5, remaining))) as response:
            row['http_status'] = response.status_code
            if response.status_code != 200:
                row.update(status='error', error_code=f'HTTP_{response.status_code}')
                return None  # Do not record upstream error bodies or follow redirects.
            chunks, size = [], 0
            async for chunk in response.aiter_bytes():
                size += len(chunk)
                if size > 1024 * 1024:
                    raise ValueError('Response size limit exceeded')
                chunks.append(chunk)
            data = json.loads(b''.join(chunks))
        answer = data.get('choices', [{}])[0].get('message', {}).get('content')
        if not isinstance(answer, str) or not answer.strip():
            raise ValueError('No answer in response')
        answer = _safe_answer(answer, cfg['api_key'])
        usage = data.get('usage') or {}
        counts = [usage.get(key) for key in ('prompt_tokens', 'completion_tokens', 'total_tokens')]
        if all(type(value) is int and value >= 0 for value in counts) and counts[0] + counts[1] == counts[2]:
            row.update(input_tokens=counts[0], output_tokens=counts[1], total_tokens=counts[2])
        row['status'] = 'completed'
    except asyncio.CancelledError:
        row.update(status='cancelled', error_code='CLIENT_CANCELLED')
        raise
    except (TimeoutError, httpx.TimeoutException):
        row.update(status='timeout', error_code='REQUEST_TIMEOUT')
    except Exception:
        # Never expose exception strings, request headers, response bodies, or credentials.
        row.update(status='error', error_code='REQUEST_FAILED')
    finally:
        row['elapsed_s'] = round(time.monotonic() - started, 6)
        row['finished_at_utc'] = _utc()
    return answer if row['status'] == 'completed' else None


async def test_call(prompt=PROMPTS[0], max_tokens=64, timeout_s=20, *, config=None, api_key=None):
    """Models preflight plus one bounded inference; return safe metrics and an answer."""
    import httpx
    _prompts((prompt,)); _integer('max_tokens', max_tokens, 1, MAX_OUTPUT_TOKENS)
    _number('timeout_s', timeout_s, 1, 30)
    config = validate_config(config)
    checked = await preflight(config, api_key=api_key)
    row = _row(1)
    answer = None
    if not checked['ok']:
        row.update(status='preflight_failed', error_code=checked['error_code'], http_status=checked['http_status'])
        return {'metrics': row, 'answer': None, 'preflight': checked, 'target_fingerprint': _target_fingerprint(config, api_key)}
    async with httpx.AsyncClient(follow_redirects=False, trust_env=False) as client:
        try:
            async with asyncio.timeout(timeout_s):
                answer = await _request(client, prompt, max_tokens, time.monotonic() + timeout_s, row, config, api_key)
        except TimeoutError:
            row.update(status='timeout', error_code='CELL_DEADLINE')
        except (KeyboardInterrupt, asyncio.CancelledError):
            row.update(status='cancelled', error_code='CELL_INTERRUPTED')
    return {'metrics': row, 'answer': answer, 'preflight': checked, 'target_fingerprint': _target_fingerprint(config, api_key)}


def save_results(report) -> Path:
    """Write allowlisted metrics, without tokens, prompts, answers, or HTTP headers."""
    folder = RESULTS_ROOT / (datetime.now(timezone.utc).strftime('manual-%Y%m%dT%H%M%SZ-') + uuid.uuid4().hex[:8])
    folder.mkdir(parents=True, mode=0o700, exist_ok=False)
    keys = ('request', 'started_at_utc', 'finished_at_utc', 'elapsed_s', 'status', 'http_status',
            'input_tokens', 'output_tokens', 'total_tokens', 'error_code')
    safe = {key: report[key] for key in ('started_at_utc', 'finished_at_utc', 'elapsed_s',
            'stop_reason', 'client_tasks_remaining')}
    configuration = report['configuration']
    safe['configuration'] = {key: configuration[key] for key in
        ('interactions', 'interval_s', 'max_tokens', 'concurrency', 'duration_s')}
    for key, maximum in (('interactions', MAX_REQUESTS), ('max_tokens', MAX_OUTPUT_TOKENS),
                         ('concurrency', MAX_CONCURRENCY)):
        _integer(key, safe['configuration'][key], 1, maximum)
    _number('interval_s', safe['configuration']['interval_s'], 0, 30)
    _number('duration_s', safe['configuration']['duration_s'], 1, MAX_SECONDS)
    safe['rows'] = [{key: row.get(key) for key in keys} for row in report['rows']]
    table = io.StringIO(); writer = csv.DictWriter(table, fieldnames=keys)
    writer.writeheader(); writer.writerows(safe['rows'])
    for name, body in (('metrics.json', json.dumps(safe, indent=2) + '\n'), ('requests.csv', table.getvalue())):
        descriptor = os.open(folder / name, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(descriptor, 'w') as stream:
            stream.write(body)
    return folder


async def manual_load(interactions=6, interval_s=2, max_tokens=96, concurrency=1,
                      duration_s=45, prompts=PROMPTS, progress=True, save=True,
                      *, config=None, api_key=None, test_result=None):
    """Run bounded traffic in this cell; cancel/join workers before returning.

    interval_s spaces request starts globally, not separately for each worker.
    Interrupt the cell to stop. Closing the client does not promise that a server
    instantly stops a request it already accepted. No background load is left.
    """
    import httpx
    _integer('interactions', interactions, 1, MAX_REQUESTS)
    _integer('concurrency', concurrency, 1, MAX_CONCURRENCY)
    _integer('max_tokens', max_tokens, 1, MAX_OUTPUT_TOKENS)
    _number('duration_s', duration_s, 1, MAX_SECONDS)
    _number('interval_s', interval_s, 0, 30)
    prompts = _prompts(prompts)
    config = validate_config(config)
    if (not isinstance(test_result, dict) or test_result.get('metrics', {}).get('status') != 'completed'
            or test_result.get('target_fingerprint') != _target_fingerprint(config, api_key)):
        raise ValueError('Run a successful test_call for the same selected endpoint, model, and credential before manual_load.')
    started, started_at = time.monotonic(), _utc()
    deadline = started + duration_s
    results, tasks = [], []
    state = {'next': 1, 'next_start': started, 'stop_reason': 'completed'}
    lock, stop = asyncio.Lock(), asyncio.Event()

    async def worker(client):
        while not stop.is_set():
            async with lock:
                if stop.is_set() or state['next'] > interactions:
                    return
                await asyncio.sleep(max(0, state['next_start'] - time.monotonic()))
                if stop.is_set() or time.monotonic() >= deadline:
                    return
                number = state['next']; state['next'] += 1
                state['next_start'] = time.monotonic() + interval_s
            row = _row(number)
            try:
                await _request(client, prompts[(number - 1) % len(prompts)], max_tokens, deadline, row, config, api_key)
            finally:
                results.append(row)
                if progress:
                    print(f"Request {number}/{interactions}: {row['status']}; {row['elapsed_s']} s", flush=True)
                if row['status'] != 'completed':
                    state['stop_reason'] = 'stopped_after_error'
                    stop.set()

    async with httpx.AsyncClient(follow_redirects=False, trust_env=False,
            limits=httpx.Limits(max_connections=concurrency, max_keepalive_connections=concurrency)) as client:
        tasks = [asyncio.create_task(worker(client)) for _ in range(concurrency)]
        try:
            async with asyncio.timeout(duration_s):
                await asyncio.gather(*tasks)
        except TimeoutError:
            state['stop_reason'] = 'duration_limit'
        except (KeyboardInterrupt, asyncio.CancelledError):
            state['stop_reason'] = 'interrupted'
        finally:
            stop.set()
            for task in tasks:
                if not task.done():
                    task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)
    if state['next'] <= interactions and time.monotonic() >= deadline:
        state['stop_reason'] = 'duration_limit'
    report = {'started_at_utc': started_at, 'finished_at_utc': _utc(),
              'elapsed_s': round(time.monotonic() - started, 6), 'stop_reason': state['stop_reason'],
              'client_tasks_remaining': sum(not task.done() for task in tasks),
              'configuration': {'interactions': interactions, 'interval_s': interval_s,
                  'max_tokens': max_tokens, 'concurrency': concurrency, 'duration_s': duration_s},
              'rows': sorted(results, key=lambda row: row['request'])}
    if save:
        report['results_directory'] = str(save_results(report))
    return report
