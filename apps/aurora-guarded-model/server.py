"""Private, bounded OpenAI-compatible NeMo comparison adapter; no tools or side effects."""
import hmac
import json
import os
from pathlib import Path
import ssl
import threading
import time
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

MAX_BODY = 65536
TOKEN = Path('/var/run/secrets/kubernetes.io/serviceaccount/token')
NEMO = 'https://showroom-rails.ai-showroom.svc/v1/guardrail/checks'
SLOT = threading.BoundedSemaphore(1)
REFUSAL = 'Aurora Supply safety policy withheld this content. No tools or purchases were executed.'


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args):
        raise ValueError('Authenticated redirects are forbidden')


def post(url, body, token, ca=None):
    context = ssl.create_default_context(cafile=ca)
    opener = urllib.request.build_opener(NoRedirect(), urllib.request.HTTPSHandler(context=context))
    request = urllib.request.Request(url, data=json.dumps(body).encode(), headers={
        'Authorization': 'Bearer ' + token, 'Content-Type': 'application/json',
        'X-MaaS-Subscription': 'showroom-standard'})
    with opener.open(request, timeout=45) as response:
        raw = response.read(1024 * 1024 + 1)
        if len(raw) > 1024 * 1024:
            raise ValueError('Response exceeds evaluation limit')
        return json.loads(raw)


def validate(body, model):
    if not isinstance(body, dict) or body.get('model') != model or body.get('stream', False):
        raise ValueError('Only the configured model and nonstreaming requests are supported')
    allowed = {'model', 'messages', 'temperature', 'max_tokens', 'stream', 'n', 'seed', 'top_p', 'frequency_penalty', 'presence_penalty', 'stop'}
    if set(body) - allowed or body.get('n', 1) != 1:
        raise ValueError('Unsupported evaluation parameters')
    messages = body.get('messages')
    if not isinstance(messages, list) or not 1 <= len(messages) <= 16:
        raise ValueError('One to sixteen text messages are required')
    for message in messages:
        if not isinstance(message, dict) or set(message) != {'role', 'content'}:
            raise ValueError('Only text message fields are supported')
        if message['role'] not in ('user', 'assistant', 'system') or not isinstance(message['content'], str):
            raise ValueError('Invalid text message')
    if body.get('max_tokens', 128) != 128 or body.get('temperature', 0) != 0:
        raise ValueError('Matched evaluation requires max_tokens128 and temperature0')
    return dict(body, max_tokens=128, temperature=0, stream=False)


def check(text, role):
    result = post(NEMO, {'model': 'aurora-assistant', 'messages': [{'role': role, 'content': text}],
        'guardrails': {'config_id': 'showroom-safety'}}, TOKEN.read_text().strip(), '/etc/service-ca/service-ca.crt')
    if result.get('status') not in ('success', 'blocked'):
        raise ValueError('Unknown guardrail verdict')
    return result['status'] == 'success'


def completion(model, text):
    return {'id': 'aurora-guarded-evaluation', 'object': 'chat.completion', 'created': int(time.time()),
        'model': model, 'choices': [{'index': 0, 'message': {'role': 'assistant', 'content': text}, 'finish_reason': 'stop'}],
        'usage': {'prompt_tokens': 0, 'completion_tokens': 0, 'total_tokens': 0}}


def evaluate(body, model, upstream, key):
    body = validate(body, model)
    # Separate checks preserve the same messages and context sent in the baseline.
    for message in body['messages']:
        if not check(message['content'], 'user'):
            return completion(model, REFUSAL), 'input-blocked'
    result = post(upstream + '/chat/completions', body, key)
    choices = result.get('choices', [])
    if len(choices) != 1 or not isinstance(choices[0].get('message', {}).get('content'), str):
        raise ValueError('Unexpected model response')
    if not check(choices[0]['message']['content'], 'assistant'):
        return completion(model, REFUSAL), 'output-blocked'
    return result, 'allowed'


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass  # Never log credentials, prompts, or model output.

    def setup(self):
        super().setup()
        self.connection.settimeout(60)

    def reply(self, code, body, verdict=None):
        payload = json.dumps(body).encode()
        self.send_response(code)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(payload)))
        if verdict:
            self.send_header('X-Aurora-Guardrail', verdict)
        self.end_headers()
        self.wfile.write(payload)

    def do_GET(self):
        if self.path == '/health':
            self.reply(200, {'status': 'ready'})
        else:
            self.reply(404, {'error': 'Unknown endpoint'})

    def do_POST(self):
        if self.path != '/v1/chat/completions':
            return self.reply(404, {'error': 'Unknown endpoint'})
        expected = 'Bearer ' + os.environ['MODEL_KEY']
        if not hmac.compare_digest(self.headers.get('Authorization', ''), expected):
            return self.reply(401, {'error': 'Authentication required'})
        if not SLOT.acquire(blocking=False):
            return self.reply(429, {'error': 'One evaluation request at a time'})
        verdict = 'unavailable'
        try:
            length = int(self.headers.get('Content-Length', '0'))
            if not 0 < length <= MAX_BODY or self.headers.get('Transfer-Encoding'):
                return self.reply(413, {'error': 'Invalid request size'})
            raw = self.rfile.read(length)
            if len(raw) != length:
                raise ValueError('Incomplete request body')
            body = json.loads(raw)
            try:
                validate(body, os.environ['MODEL_ID'])
            except ValueError:
                return self.reply(400, {'error': 'Unsupported evaluation request'})
            result, verdict = evaluate(body, os.environ['MODEL_ID'], os.environ['MODEL_BASE'].rstrip('/'), os.environ['MODEL_KEY'])
            self.reply(200, result, verdict)
        except (OSError, ValueError, KeyError, TypeError):
            self.reply(503, {'error': 'Safety or inference dependency unavailable; request denied'})
        finally:
            print(json.dumps({'event': 'evaluation_request', 'verdict': verdict}), flush=True)
            SLOT.release()


def main():
    from urllib.parse import urlparse
    base = urlparse(os.environ['MODEL_BASE'])
    if base.scheme != 'https' or base.username or base.password or base.query or base.fragment or base.path.rstrip('/') != '/v1':
        raise SystemExit('The fixed upstream must be an authenticated HTTPS /v1 endpoint')
    server = ThreadingHTTPServer(('0.0.0.0', 8443), Handler)
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.minimum_version = ssl.TLSVersion.TLSv1_2
    context.load_cert_chain('/etc/tls/tls.crt', '/etc/tls/tls.key')
    server.socket = context.wrap_socket(server.socket, server_side=True)
    server.serve_forever()


if __name__ == '__main__':
    main()
