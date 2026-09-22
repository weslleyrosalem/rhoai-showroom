"""Offline security checks; no cluster credential, endpoint, or model is used."""
import asyncio
import importlib.util
import json
from pathlib import Path
import ssl
import sys
import unittest
from unittest.mock import patch

import httpx

spec = importlib.util.spec_from_file_location('aurora_compare_security_server', Path(__file__).with_name('server.py'))
server = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = server
spec.loader.exec_module(server)

ORIGIN = 'https://compare.example.test'
HEADERS = {'X-Forwarded-User': 'synthetic-presenter', 'Origin': ORIGIN}
BODY = {'system': 'Synthetic context only.', 'message': 'Explain the proposal.', 'max_tokens': 32}


class SecurityTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.environment = patch.dict(server.os.environ, {'PUBLIC_ORIGIN': ORIGIN})
        self.environment.start()
        self.addCleanup(self.environment.stop)
        server.state = server.SessionState()
        self.http = httpx.AsyncClient(transport=httpx.ASGITransport(app=server.app), base_url=ORIGIN)
        self.addAsyncCleanup(self.http.aclose)

    async def test_proxy_identity_and_host_are_required(self):
        self.assertEqual((await self.http.get('/api/status')).status_code, 401)
        result = await self.http.get('/api/status', headers={**HEADERS,
            'Host': 'wrong.example.test', 'X-Forwarded-Host': 'compare.example.test'})
        self.assertEqual(result.status_code, 403)
        result = await self.http.get('/api/status', headers=HEADERS)
        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.json()['remaining_runs'], server.USER_LIMIT)

    async def test_origin_and_json_required_before_any_upstream(self):
        with patch.object(server, 'discover', side_effect=AssertionError('No upstream expected')):
            for origin in (None, 'null', 'https://other.example.test'):
                headers = dict(HEADERS)
                if origin is None:
                    headers.pop('Origin')
                else:
                    headers['Origin'] = origin
                for path in ('/api/compare', '/api/cancel'):
                    response = await self.http.post(path, headers=headers, json=BODY)
                    self.assertEqual(response.status_code, 403)
            response = await self.http.post('/api/compare', headers={**HEADERS,
                'Content-Type': 'text/plain'}, content=json.dumps(BODY))
            self.assertEqual(response.status_code, 415)
        self.assertEqual(server.state.attempts, 0)

    async def test_invalid_fields_tokens_and_oversized_body_do_not_reserve(self):
        invalid = [dict(BODY, max_tokens=value) for value in (True, 0, 129, 3.0, '32')]
        invalid += [dict(BODY, model='another-model'), dict(BODY, url='https://other.example.test'),
                    dict(BODY, message='   '), dict(BODY, system='x' * 12001)]
        with patch.object(server, 'discover', side_effect=AssertionError('No upstream expected')):
            for payload in invalid:
                response = await self.http.post('/api/compare', headers=HEADERS, json=payload)
                self.assertEqual(response.status_code, 400)
                self.assertNotIn('another-model', response.text)
            async def chunks():
                yield b'{' + b' ' * 40000
                yield b' ' * 40000 + b'}'
            response = await self.http.post('/api/compare', headers={**HEADERS,
                'Content-Type': 'application/json'}, content=chunks())
            self.assertEqual(response.status_code, 413)
        self.assertEqual(server.state.attempts, 0)

    async def test_only_initiating_user_can_cancel(self):
        active = server.state.reserve('synthetic-presenter')
        response = await self.http.post('/api/cancel', headers={**HEADERS,
            'X-Forwarded-User': 'another-user'}, json={'comparison_id': active.identifier})
        self.assertEqual(response.status_code, 403)
        self.assertFalse(active.cancelled)
        response = await self.http.post('/api/cancel', headers=HEADERS,
                                       json={'comparison_id': active.identifier})
        self.assertEqual(response.status_code, 200)
        self.assertTrue(active.cancelled)
        server.state.release(active)

    async def test_cancel_running_asgi_stream_closes_upstream_and_releases_slot(self):
        entered, closed = asyncio.Event(), asyncio.Event()
        clients = []

        class SlowStream(httpx.AsyncByteStream):
            async def __aiter__(self):
                entered.set()
                await asyncio.sleep(30)
                yield b'data: [DONE]\n\n'

            async def aclose(self):
                closed.set()

        def fake_client(verify=True):
            upstream = httpx.AsyncClient(transport=httpx.MockTransport(lambda request:
                httpx.Response(200, headers={'content-type': 'text/event-stream'}, stream=SlowStream())),
                trust_env=False, follow_redirects=False)
            clients.append(upstream)
            return upstream

        async def discover():
            return ['https://10.128.1.2:8000/v1/chat/completions',
                    'https://10.128.2.3:8000/v1/chat/completions']

        context = ssl.create_default_context()
        with patch.object(server, 'discover', discover), patch.object(server, 'client', fake_client), \
                patch.object(server.ssl, 'create_default_context', return_value=context):
            pending = asyncio.create_task(self.http.post('/api/compare', headers=HEADERS, json=BODY))
            try:
                await asyncio.wait_for(entered.wait(), 2)
                identifier = server.state.active.identifier
                result = await self.http.post('/api/cancel', headers=HEADERS,
                                              json={'comparison_id': identifier})
                self.assertEqual(result.status_code, 200)
                await asyncio.wait_for(closed.wait(), 2)
                # A cancelled HTTP stream may finish with an incomplete body or
                # a transport error; neither may leave work running upstream.
                await asyncio.wait_for(asyncio.gather(pending, return_exceptions=True), 2)
                self.assertIsNone(server.state.active)
                self.assertEqual(len(clients), 1)
                self.assertTrue(clients[0].is_closed)
                status = await self.http.get('/api/status', headers=HEADERS)
                self.assertFalse(status.json()['busy'])
            finally:
                pending.cancel()
                await asyncio.gather(pending, return_exceptions=True)

    async def test_endpoint_discovery_rejects_arbitrary_destinations(self):
        def fixture():
            return {'metadata': {'name': server.ENDPOINT_NAME, 'namespace': server.NAMESPACE},
                    'subsets': [{'ports': [{'port': 8000, 'protocol': 'TCP', 'appProtocol': 'https'}],
                                 'addresses': [{'ip': ip, 'targetRef': {'kind': 'Pod',
                                    'namespace': server.NAMESPACE, 'name': server.MODEL + '-kserve-' + suffix}}
                                    for ip, suffix in [('10.128.1.2', 'a'), ('10.128.2.3', 'b')]]}]}
        expected = ['https://10.128.1.2:8000/v1/chat/completions',
                    'https://10.128.2.3:8000/v1/chat/completions']
        self.assertEqual(server.endpoint_addresses(fixture()), expected)
        for ip in ('127.0.0.1', '169.254.169.254', '0.0.0.0', '8.8.8.8', 'https://example.test'):
            value = fixture()
            value['subsets'][0]['addresses'][0]['ip'] = ip
            with self.assertRaises(server.SafeFailure):
                server.endpoint_addresses(value)
        value = fixture()
        value['subsets'][0]['notReadyAddresses'] = value['subsets'][0].pop('addresses')
        with self.assertRaises(server.SafeFailure):
            server.endpoint_addresses(value)
        value = fixture()
        value['subsets'][0]['ports'][0]['appProtocol'] = 'http'
        with self.assertRaises(server.SafeFailure):
            server.endpoint_addresses(value)
        value = fixture()
        value['metadata']['namespace'] = 'another-project'
        with self.assertRaises(server.SafeFailure):
            server.endpoint_addresses(value)

    async def test_baseline_has_no_credential_and_gateway_reads_rotating_token(self):
        first, second = 'SYNTHETIC_TOKEN_ONE', 'SYNTHETIC_TOKEN_TWO'
        observed, contexts = [], []
        context = ssl.create_default_context()

        def upstream(request):
            observed.append((str(request.url), request.headers.get('authorization'), request.content))
            text = 'Synthetic answer.'
            if request.headers.get('authorization'):
                text = request.headers['authorization'].removeprefix('Bearer ')
            # Split an echoed credential across two valid SSE events.
            pieces = [text[:5], text[5:]]
            records = [{'choices': [{'delta': {'content': piece}, 'finish_reason': None}]} for piece in pieces]
            records += [{'choices': [{'delta': {}, 'finish_reason': 'stop'}],
                         'usage': {'prompt_tokens': 3, 'completion_tokens': 2, 'total_tokens': 5}}]
            raw = ''.join('data: ' + json.dumps(value) + '\n\n' for value in records) + 'data: [DONE]\n\n'
            return httpx.Response(200, headers={'content-type': 'text/event-stream'}, content=raw)

        def fake_client(verify=True):
            contexts.append(verify)
            return httpx.AsyncClient(transport=httpx.MockTransport(upstream), verify=verify,
                                     trust_env=False, follow_redirects=False)

        body = b'{"synthetic":"same bytes for both paths"}'
        events = []
        with patch.object(server, 'client', fake_client), patch.object(server.ssl, 'create_default_context', return_value=context), \
                patch.object(server, 'token', side_effect=[first, second]) as credential:
            for side, url in [('vllm', 'https://10.128.1.2:8000/v1/chat/completions'),
                              ('llmd', server.GATEWAY), ('llmd', server.GATEWAY)]:
                events += [event async for event in server.run_side(side, url, body)]
            self.assertEqual(credential.call_count, 2)
        self.assertIsNone(observed[0][1])
        self.assertEqual([row[1] for row in observed[1:]], ['Bearer ' + first, 'Bearer ' + second])
        self.assertTrue(all(row[2] == body for row in observed))
        self.assertIsInstance(contexts[0], ssl.SSLContext)
        self.assertTrue(contexts[0].check_hostname)
        self.assertEqual(contexts[0].verify_mode, ssl.CERT_REQUIRED)
        self.assertNotIn(first, json.dumps(events))
        self.assertNotIn(second, json.dumps(events))
        self.assertEqual([e['status'] for e in events if e['type'] == 'side_end'], ['completed'] * 3)


if __name__ == '__main__':
    unittest.main(verbosity=2)
