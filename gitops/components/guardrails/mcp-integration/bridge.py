"""Private NeMo TLS/auth adapter for IPP. Fixed destination; no payload logging."""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import ssl
import urllib.request

SERVICEACCOUNT = Path('/var/run/secrets/kubernetes.io/serviceaccount')
UPSTREAM = 'https://showroom-rails.ai-showroom.svc/v1/guardrail/checks'


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *_):
        pass

    def send(self, code, data):
        body = json.dumps(data).encode()
        self.send_response(code)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        self.send(200 if self.path == '/health' else 404, {'service': 'private-nemo-adapter'})

    def do_POST(self):
        if self.path != '/v1/guardrail/checks':
            return self.send(404, {'status': 'error'})
        try:
            length = int(self.headers.get('Content-Length', '0'))
            if not 0 < length <= 262144 or self.headers.get('Transfer-Encoding'):
                return self.send(413, {'status': 'error'})
            self.connection.settimeout(12)
            payload = json.loads(self.rfile.read(length))
            if not isinstance(payload, dict) or not isinstance(payload.get('messages'), list):
                return self.send(400, {'status': 'error'})
            # The caller cannot select a weaker configuration or a different upstream.
            payload['guardrails'] = {'config_id': 'showroom-safety'}
            token = (SERVICEACCOUNT / 'token').read_text().strip()
            request = urllib.request.Request(UPSTREAM, json.dumps(payload).encode(),
                {'Authorization': 'Bearer ' + token, 'Content-Type': 'application/json'})
            context = ssl.create_default_context(cafile=str(SERVICEACCOUNT / 'service-ca.crt'))
            opener = urllib.request.build_opener(NoRedirect(), urllib.request.HTTPSHandler(context=context))
            with opener.open(request, timeout=8) as response:
                result = json.loads(response.read(1048576))
            # IPP upstream currently permits 'modified' without applying redaction.
            # Tighten adapter to fail closed for anything except success or blocked.
            decision = result.get('status')
            if decision not in {'success', 'blocked'}:
                return self.send(503, {'status': 'error'})
            self.send(200, {'status': decision, 'rails_status': result.get('rails_status', {})})
        except Exception:
            self.send(503, {'status': 'error'})


if __name__ == '__main__':
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.minimum_version = ssl.TLSVersion.TLSv1_2
    context.load_cert_chain('/tls/tls.crt', '/tls/tls.key')
    server = ThreadingHTTPServer(('0.0.0.0', 9443), Handler)
    server.socket = context.wrap_socket(server.socket, server_side=True)
    server.serve_forever()
