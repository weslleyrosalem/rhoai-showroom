"""Authenticated, bounded two-path Qwen comparison; no prompts or results logged."""
from __future__ import annotations

import asyncio
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
import ipaddress
import json
import math
import os
from pathlib import Path
import ssl
import time
from urllib.parse import urlsplit
import uuid

import anyio
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
import httpx
from pydantic import BaseModel, ConfigDict, Field, StrictInt, StrictStr, ValidationError

MODEL = 'aurora-qwen-4b'
NAMESPACE = 'ai-showroom'
ENDPOINT_NAME = MODEL + '-kserve-workload-svc'
API_URL = 'https://kubernetes.default.svc/api/v1/namespaces/ai-showroom/endpoints/' + ENDPOINT_NAME
GATEWAY = 'http://showroom-inference-maas-gateway-class.ai-showroom.svc.cluster.local:8080/ai-showroom/aurora-qwen-4b/v1/chat/completions'
TOKEN_FILE = Path('/var/run/secrets/kubernetes.io/serviceaccount/token')
API_CA = '/var/run/secrets/kubernetes.io/serviceaccount/ca.crt'
ROOT = Path(__file__).resolve().parent
PAIR_SECONDS, COOLDOWN_SECONDS, PROCESS_LIMIT, USER_LIMIT = 90, 5, 60, 20
MAX_BODY, MAX_UPSTREAM = 65536, 1048576
app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)


class CompareInput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    system: StrictStr = Field(default='', max_length=12000)
    message: StrictStr = Field(min_length=1, max_length=2000)
    max_tokens: StrictInt = Field(default=64, ge=1, le=128)


class SafeFailure(Exception):
    def __init__(self, code):
        self.code = code
        super().__init__('Comparison upstream unavailable')


@dataclass
class Active:
    identifier: str
    user: str
    order: tuple
    backend_index: int
    task: asyncio.Task | None = None
    cancelled: bool = False


class SessionState:
    def __init__(self):
        self.active = None
        self.attempts = 0
        self.users = Counter()
        self.last_finished = -math.inf

    def remaining(self, user):
        return max(0, min(PROCESS_LIMIT - self.attempts, USER_LIMIT - self.users[user]))

    def cooldown(self):
        return max(0, COOLDOWN_SECONDS - (time.monotonic() - self.last_finished))

    def reserve(self, user):
        # One uvicorn worker, one event loop: no await between check/reservation.
        if self.active is not None:
            raise HTTPException(409, 'A comparison is already running')
        if self.cooldown() > 0:
            raise HTTPException(429, 'Comparison cooldown is active')
        if not self.remaining(user):
            raise HTTPException(429, 'Comparison session budget exhausted')
        index = self.attempts
        self.attempts += 1
        self.users[user] += 1
        order = ('vllm', 'llmd') if index % 2 == 0 else ('llmd', 'vllm')
        self.active = Active(str(uuid.uuid4()), user, order, index % 2)
        return self.active

    def release(self, active):
        if self.active is active:
            self.active = None
            self.last_finished = time.monotonic()


state = SessionState()


def timestamp():
    return datetime.now(timezone.utc).isoformat()


def origin():
    value = os.environ.get('PUBLIC_ORIGIN', '')
    parsed = urlsplit(value)
    if (parsed.scheme != 'https' or not parsed.hostname or parsed.username is not None or parsed.password is not None
            or parsed.path or parsed.query or parsed.fragment or value != 'https://' + parsed.netloc):
        raise HTTPException(503, 'Public origin is not configured')
    return value, parsed.netloc


def identity(request):
    _, host = origin()
    if request.headers.get('host') != host:
        raise HTTPException(403, 'Unexpected request host')
    user = request.headers.get('x-forwarded-user', '')
    if not user or len(user) > 256 or any(ord(char) < 32 for char in user):
        raise HTTPException(401, 'Authenticated proxy identity required')
    return user


async def input_json(request):
    user = identity(request)
    expected, _ = origin()
    if request.headers.get('origin') != expected:
        raise HTTPException(403, 'Same-origin request required')
    if request.headers.get('content-type', '').split(';')[0].strip().lower() != 'application/json':
        raise HTTPException(415, 'JSON content required')
    chunks, size = [], 0
    try:
        async with asyncio.timeout(5):
            async for chunk in request.stream():
                size += len(chunk)
                if size > MAX_BODY:
                    raise HTTPException(413, 'Request exceeds the size limit')
                chunks.append(chunk)
    except TimeoutError:
        raise HTTPException(408, 'Request body deadline exceeded') from None
    try:
        value = json.loads(b''.join(chunks))
    except (ValueError, UnicodeError):
        raise HTTPException(400, 'Invalid JSON payload') from None
    return user, value


def token():
    value = TOKEN_FILE.read_text().strip()
    if not value or len(value) > 32768 or any(char.isspace() for char in value):
        raise SafeFailure('WORKLOAD_CREDENTIAL_UNAVAILABLE')
    return value


def client(verify=True):
    return httpx.AsyncClient(verify=verify, trust_env=False, follow_redirects=False,
        timeout=httpx.Timeout(40, connect=5), limits=httpx.Limits(max_connections=2))


async def bounded_json(response):
    chunks, size = [], 0
    async for chunk in response.aiter_bytes():
        size += len(chunk)
        if size > MAX_UPSTREAM:
            raise SafeFailure('UPSTREAM_RESPONSE_LIMIT')
        chunks.append(chunk)
    try:
        return json.loads(b''.join(chunks))
    except (ValueError, UnicodeError):
        raise SafeFailure('UPSTREAM_PROTOCOL_ERROR') from None


def endpoint_addresses(value):
    if not isinstance(value, dict) or value.get('metadata', {}).get('name') != ENDPOINT_NAME or value.get('metadata', {}).get('namespace') != NAMESPACE:
        raise SafeFailure('BACKEND_DISCOVERY_INVALID')
    found = []
    for subset in value.get('subsets', []):
        ports = [port for port in subset.get('ports', []) if port.get('port') == 8000
                 and port.get('protocol', 'TCP') == 'TCP' and port.get('appProtocol') == 'https']
        if not ports:
            continue
        for address in subset.get('addresses', []):
            reference = address.get('targetRef', {})
            name = reference.get('name', '')
            try:
                ip = ipaddress.ip_address(address['ip'])
            except (KeyError, ValueError):
                raise SafeFailure('BACKEND_DISCOVERY_INVALID') from None
            if (not ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_multicast or ip.is_unspecified
                    or reference.get('kind') != 'Pod' or reference.get('namespace') != NAMESPACE
                    or not isinstance(name, str) or not name.startswith(MODEL + '-kserve-')):
                raise SafeFailure('BACKEND_DISCOVERY_INVALID')
            host = '[' + str(ip) + ']' if ip.version == 6 else str(ip)
            found.append((name, 'https://' + host + ':8000/v1/chat/completions'))
    if len(found) != 2 or len({item[0] for item in found}) != 2 or len({item[1] for item in found}) != 2:
        raise SafeFailure('REQUIRE_TWO_READY_BACKENDS')
    return [url for _, url in sorted(found)]


async def discover():
    context = ssl.create_default_context(cafile=API_CA)
    async with client(context) as api:
        async with api.stream('GET', API_URL, headers={'Authorization': 'Bearer ' + token()}, timeout=8) as response:
            if response.status_code != 200:
                raise SafeFailure('BACKEND_DISCOVERY_UNAVAILABLE')
            return endpoint_addresses(await bounded_json(response))


class CredentialRedactor:
    """Withhold only possible credential prefixes, preserving incremental output."""
    def __init__(self, credential):
        self.credential, self.pending = credential, ''

    def feed(self, value, final=False):
        self.pending += value
        if self.credential:
            self.pending = self.pending.replace(self.credential, '[REDACTED_CREDENTIAL]')
        keep = 0
        if not final and self.credential:
            for length in range(min(len(self.pending), len(self.credential)-1), 0, -1):
                if self.pending.endswith(self.credential[:length]):
                    keep = length
                    break
        result = self.pending[:-keep] if keep else self.pending
        self.pending = self.pending[-keep:] if keep else ''
        return result


async def sse_events(response):
    pending, data, size = '', [], 0
    import codecs
    decoder = codecs.getincrementaldecoder('utf-8')('strict')
    async for chunk in response.aiter_bytes():
        size += len(chunk)
        if size > MAX_UPSTREAM:
            raise SafeFailure('UPSTREAM_RESPONSE_LIMIT')
        pending += decoder.decode(chunk)
        if len(pending) > 65536:
            raise SafeFailure('UPSTREAM_EVENT_LIMIT')
        while '\n' in pending:
            line, pending = pending.split('\n', 1)
            line = line.rstrip('\r')
            if line.startswith('data:'):
                data.append(line[5:].lstrip(' '))
                if sum(map(len, data)) > 65536:
                    raise SafeFailure('UPSTREAM_EVENT_LIMIT')
            elif not line and data:
                content = '\n'.join(data); data = []
                if content == '[DONE]':
                    return
                try:
                    event = json.loads(content)
                except ValueError:
                    raise SafeFailure('UPSTREAM_PROTOCOL_ERROR') from None
                if not isinstance(event, dict):
                    raise SafeFailure('UPSTREAM_PROTOCOL_ERROR')
                yield event
    # An orderly EOF alone is not a completed OpenAI event stream. The [DONE]
    # branch above must terminate the parser, even after a finish_reason event.
    raise SafeFailure('UPSTREAM_TRUNCATED_STREAM')


def usage_counts(value):
    if not isinstance(value, dict):
        return None
    values = [value.get(key) for key in ('prompt_tokens', 'completion_tokens', 'total_tokens')]
    if all(type(item) is int and item >= 0 for item in values) and values[0] + values[1] == values[2]:
        return dict(zip(('input_tokens', 'output_tokens', 'total_tokens'), values))
    return None


async def run_side(side, url, payload, backend_alias=None):
    started = time.monotonic()
    first, counts, content_seen, terminal = None, None, False, False
    finish_reason = None
    status, error = 'completed', None
    credential = token() if side == 'llmd' else ''
    redactor = CredentialRedactor(credential)
    headers = {'Content-Type': 'application/json', 'Accept': 'text/event-stream'}
    if side == 'llmd':
        headers['Authorization'] = 'Bearer ' + credential
    context = ssl.create_default_context(cafile=os.environ.get('QWEN_CA_FILE', '/etc/qwen-ca/ca.crt')) if side == 'vllm' else True
    yield {'type': 'side_start', 'side': side, 'started_at': timestamp(), 'backend_alias': backend_alias}
    upstream = client(context)
    try:
        async with upstream.stream('POST', url, content=payload, headers=headers) as response:
            if response.status_code != 200:
                raise SafeFailure('UPSTREAM_HTTP_' + str(response.status_code))
            if not response.headers.get('content-type', '').lower().startswith('text/event-stream'):
                raise SafeFailure('UPSTREAM_NOT_EVENT_STREAM')
            async for event in sse_events(response):
                if 'error' in event:
                    raise SafeFailure('UPSTREAM_STREAM_ERROR')
                found_usage = usage_counts(event.get('usage'))
                if found_usage is not None:
                    counts = found_usage
                choices = event.get('choices', [])
                if not isinstance(choices, list):
                    raise SafeFailure('UPSTREAM_PROTOCOL_ERROR')
                for choice in choices:
                    if not isinstance(choice, dict):
                        raise SafeFailure('UPSTREAM_PROTOCOL_ERROR')
                    reason = choice.get('finish_reason')
                    if reason is not None:
                        if not isinstance(reason, str) or reason not in ('stop', 'length', 'content_filter', 'tool_calls', 'function_call'):
                            raise SafeFailure('UPSTREAM_FINISH_REASON_INVALID')
                        finish_reason = reason
                        terminal = True
                    delta = choice.get('delta', {}).get('content')
                    if delta is not None and not isinstance(delta, str):
                        raise SafeFailure('UPSTREAM_PROTOCOL_ERROR')
                    if delta:
                        if first is None:
                            first = (time.monotonic() - started) * 1000
                        content_seen = True
                        safe = redactor.feed(delta)
                        if safe:
                            yield {'type': 'delta', 'side': side, 'text': safe}
            if not content_seen or not terminal:
                raise SafeFailure('UPSTREAM_INCOMPLETE_RESPONSE')
            remaining = redactor.feed('', final=True)
            if remaining:
                yield {'type': 'delta', 'side': side, 'text': remaining}
    except SafeFailure as failure:
        status, error = 'error', failure.code
    except httpx.TimeoutException:
        status, error = 'timeout', 'UPSTREAM_TIMEOUT'
    except Exception:
        status, error = 'error', 'UPSTREAM_UNAVAILABLE'
    finally:
        with anyio.CancelScope(shield=True):
            await upstream.aclose()
    yield {'type': 'side_end', 'side': side, 'status': status, 'error_code': error,
           'finish_reason': finish_reason,
           'ttft_ms': round(first, 3) if first is not None else None,
           'elapsed_ms': round((time.monotonic()-started)*1000, 3), 'usage': counts,
           'backend_alias': backend_alias, 'finished_at': timestamp()}


def encoded(value):
    return json.dumps(value, ensure_ascii=False, allow_nan=False) + '\n'


class ComparisonResponse(StreamingResponse):
    """Release reservations even if the client leaves before iteration starts."""
    def __init__(self, active, value):
        self.active = active
        super().__init__(pair_events(active, value), media_type='application/x-ndjson',
                         headers={'X-Accel-Buffering': 'no', 'Cache-Control': 'no-store'})

    async def __call__(self, scope, receive, send):
        try:
            async with asyncio.timeout(PAIR_SECONDS):
                await super().__call__(scope, receive, send)
        except TimeoutError:
            self.active.cancelled = True
        finally:
            try:
                with anyio.CancelScope(shield=True):
                    await self.body_iterator.aclose()
            finally:
                state.release(self.active)


async def pair_events(active, value):
    active.task = asyncio.current_task()
    payload = json.dumps({'model': MODEL, 'messages': [{'role': 'system', 'content': value.system},
        {'role': 'user', 'content': value.message}], 'temperature': 0, 'seed': 42,
        'max_tokens': value.max_tokens, 'stream': True, 'stream_options': {'include_usage': True}},
        ensure_ascii=False, separators=(',', ':')).encode()
    try:
        async with asyncio.timeout(PAIR_SECONDS):
            yield encoded({'type': 'start', 'comparison_id': active.identifier, 'model': MODEL,
                'order': list(active.order), 'temperature': 0, 'seed': 42, 'max_tokens': value.max_tokens,
                'same_payload': True, 'started_at': timestamp()})
            if active.cancelled:
                return
            addresses = await discover()
            for side in active.order:
                if active.cancelled:
                    return
                url = addresses[active.backend_index] if side == 'vllm' else GATEWAY
                alias = ('A', 'B')[active.backend_index] if side == 'vllm' else None
                side_stream = run_side(side, url, payload, alias)
                try:
                    async for event in side_stream:
                        yield encoded(event)
                finally:
                    with anyio.CancelScope(shield=True):
                        await side_stream.aclose()
            yield encoded({'type': 'complete', 'comparison_id': active.identifier, 'finished_at': timestamp()})
    except TimeoutError:
        yield encoded({'type': 'error', 'error_code': 'PAIR_DEADLINE', 'comparison_id': active.identifier})
    except SafeFailure as failure:
        yield encoded({'type': 'error', 'error_code': failure.code, 'comparison_id': active.identifier})
    except asyncio.CancelledError:
        raise
    except Exception:
        yield encoded({'type': 'error', 'error_code': 'COMPARISON_UNAVAILABLE', 'comparison_id': active.identifier})
    finally:
        state.release(active)


@app.middleware('http')
async def headers(request, call_next):
    response = await call_next(request)
    response.headers['Cache-Control'] = 'no-store'
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['Referrer-Policy'] = 'no-referrer'
    response.headers['Content-Security-Policy'] = "default-src 'self'; script-src 'self'; style-src 'self'; connect-src 'self'; img-src 'self' data:; frame-ancestors 'none'; base-uri 'none'; form-action 'self'"
    return response


@app.get('/healthz')
async def health():
    return {'status': 'ok'}


@app.get('/api/status')
async def status(request: Request):
    user = identity(request)
    return {'busy': state.active is not None, 'remaining_runs': state.remaining(user),
            'cooldown_seconds': round(state.cooldown(), 2), 'model': MODEL, 'temperature': 0,
            'max_tokens_default': 64, 'max_tokens_limit': 128, 'pair_deadline_seconds': PAIR_SECONDS}


@app.post('/api/compare')
async def compare(request: Request):
    user, body = await input_json(request)
    try:
        value = CompareInput.model_validate(body)
        if not value.message.strip():
            raise ValueError
    except (ValidationError, ValueError, TypeError):
        raise HTTPException(400, 'Invalid comparison fields or limits') from None
    active = state.reserve(user)
    return ComparisonResponse(active, value)


@app.post('/api/cancel')
async def cancel(request: Request):
    user, body = await input_json(request)
    if not isinstance(body, dict) or set(body) != {'comparison_id'} or not isinstance(body['comparison_id'], str):
        raise HTTPException(400, 'Invalid cancellation request')
    active = state.active
    if active is None or active.identifier != body['comparison_id']:
        return {'status': 'not_active'}
    if active.user != user:
        raise HTTPException(403, 'Only the initiating user can cancel this comparison')
    active.cancelled = True
    if active.task is not None:
        active.task.cancel()
    return {'status': 'cancelling'}


@app.get('/')
async def index(request: Request):
    identity(request)
    return FileResponse(ROOT / 'index.html')


@app.get('/{filename}')
async def static_file(filename: str, request: Request):
    identity(request)
    if filename not in ('styles.css', 'app.js'):
        raise HTTPException(404, 'Not found')
    return FileResponse(ROOT / filename)
