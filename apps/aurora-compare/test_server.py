"""Offline streaming/lifecycle tests; no Kubernetes or model requests."""
import asyncio
import importlib.util
import json
from pathlib import Path
import ssl
import unittest
from unittest.mock import AsyncMock, patch

import httpx

spec = importlib.util.spec_from_file_location('compare_server', Path(__file__).with_name('server.py'))
server = importlib.util.module_from_spec(spec)
import sys
sys.modules[spec.name] = server
spec.loader.exec_module(server)


def wire(content=None, finish=None, usage=None):
    value = {'choices': [] if content is None and finish is None else [
        {'delta': {'content': content}, 'finish_reason': finish}]}
    if usage:
        value['usage'] = usage
    return ('data: ' + json.dumps(value) + '\n\n').encode()


class Stream(httpx.AsyncByteStream):
    def __init__(self, chunks, delay=0):
        self.chunks, self.delay, self.closed = chunks, delay, False

    async def __aiter__(self):
        for chunk in self.chunks:
            if self.delay:
                await asyncio.sleep(self.delay)
            yield chunk

    async def aclose(self):
        self.closed = True


class StreamingTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        server.state = server.SessionState()
        self.requests, self.streams, self.clients = [], [], []
        self.token = 'SYNTHETIC_ACTIVE_CREDENTIAL'
        self.context = ssl.create_default_context()
        self.patches = [
            patch.object(server, 'discover', AsyncMock(return_value=[
                'https://10.0.0.11:8000/v1/chat/completions',
                'https://10.0.0.12:8000/v1/chat/completions'])),
            patch.object(server, 'token', return_value=self.token),
            patch.object(server.ssl, 'create_default_context', return_value=self.context),
            patch.object(server, 'client', side_effect=self.client),
        ]
        for item in self.patches:
            item.start()
        self.handler = self.good

    def tearDown(self):
        for item in reversed(self.patches):
            item.stop()

    def client(self, verify=True):
        item = httpx.AsyncClient(transport=httpx.MockTransport(self.dispatch),
                                trust_env=False, follow_redirects=False)
        self.clients.append(item)
        return item

    async def dispatch(self, request):
        self.requests.append(request)
        return await self.handler(request)

    async def good(self, request):
        stream = Stream([wire(''), wire('Hello'), wire(' world', 'stop'),
                         wire(usage={'prompt_tokens': 20, 'completion_tokens': 2, 'total_tokens': 22}),
                         b'data: [DONE]\n\n'], delay=.002)
        self.streams.append(stream)
        return httpx.Response(200, headers={'Content-Type': 'text/event-stream'}, stream=stream)

    async def collect(self):
        active = server.state.reserve('test-presenter')
        data = server.CompareInput(system='Synthetic policy', message='Explain the proposal', max_tokens=32)
        return [json.loads(item) async for item in server.pair_events(active, data)]

    async def test_identical_payload_alternating_paths_and_actual_metrics(self):
        events = await self.collect()
        self.assertEqual(self.requests[0].content, self.requests[1].content)
        payload = json.loads(self.requests[0].content)
        self.assertEqual((payload['model'], payload['temperature'], payload['seed'], payload['max_tokens']),
                         (server.MODEL, 0, 42, 32))
        self.assertNotIn('authorization', self.requests[0].headers)
        self.assertEqual(self.requests[1].headers['authorization'], 'Bearer ' + self.token)
        self.assertEqual(events[0]['order'], ['vllm', 'llmd'])
        ends = [item for item in events if item['type'] == 'side_end']
        self.assertEqual([item['status'] for item in ends], ['completed', 'completed'])
        self.assertEqual(ends[0]['backend_alias'], 'A')
        for end in ends:
            self.assertEqual(end['finish_reason'], 'stop')
            self.assertGreater(end['ttft_ms'], 0)
            self.assertGreaterEqual(end['elapsed_ms'], end['ttft_ms'])
            self.assertEqual(end['usage']['total_tokens'], 22)
        self.assertIsNone(server.state.active)
        self.assertTrue(all(item.closed for item in self.streams))
        self.assertTrue(all(item.is_closed for item in self.clients))
        server.state.last_finished = -float('inf')
        second = await self.collect()
        self.assertEqual(second[0]['order'], ['llmd', 'vllm'])
        self.assertEqual(self.requests[-1].url.host, '10.0.0.12')
        self.assertNotIn('authorization', self.requests[-1].headers)

    async def test_incomplete_stream_and_raw_errors_are_not_success(self):
        async def incomplete(request):
            return httpx.Response(200, headers={'Content-Type': 'text/event-stream'},
                                  content=wire('Partial', 'stop'))
        self.handler = incomplete
        events = await self.collect()
        ends = [item for item in events if item['type'] == 'side_end']
        self.assertTrue(all(item['error_code'] == 'UPSTREAM_TRUNCATED_STREAM' for item in ends))
        server.state.last_finished = -float('inf')
        async def denied(request):
            return httpx.Response(503, text=self.token)
        self.handler = denied
        events = await self.collect()
        self.assertNotIn(self.token, json.dumps(events))
        self.assertTrue(all(item['ttft_ms'] is None for item in events if item['type'] == 'side_end'))

    async def test_token_limit_is_exposed_without_relabeling_it_as_full_answer(self):
        async def limited(request):
            return httpx.Response(200, headers={'Content-Type': 'text/event-stream'},
                                  content=wire('Partial answer', 'length') + b'data: [DONE]\n\n')
        self.handler = limited
        events = await self.collect()
        ends = [item for item in events if item['type'] == 'side_end']
        self.assertTrue(all(item['finish_reason'] == 'length' for item in ends))
        self.assertTrue(all(item['status'] == 'completed' for item in ends))

    async def test_active_credential_echo_split_across_chunks_is_redacted(self):
        async def echo(request):
            text = self.token
            return httpx.Response(200, headers={'Content-Type': 'text/event-stream'}, content=b''.join([
                wire(text[:7]), wire(text[7:16]), wire(text[16:], 'stop'), b'data: [DONE]\n\n']))
        self.handler = echo
        events = await self.collect()
        gateway = [item for item in events if item.get('side') == 'llmd']
        self.assertNotIn(self.token, json.dumps(gateway))
        self.assertIn('[REDACTED_CREDENTIAL]', ''.join(item['text'] for item in gateway if item['type'] == 'delta'))

    async def test_deadline_closes_upstream_and_releases_slot(self):
        async def slow(request):
            stream = Stream([wire('Late')], delay=10)
            self.streams.append(stream)
            return httpx.Response(200, headers={'Content-Type': 'text/event-stream'}, stream=stream)
        self.handler = slow
        with patch.object(server, 'PAIR_SECONDS', .03):
            events = await self.collect()
        self.assertEqual(events[-1]['error_code'], 'PAIR_DEADLINE')
        self.assertTrue(self.streams[0].closed)
        self.assertIsNone(server.state.active)

    async def test_disconnected_consumer_closes_nested_stream_and_releases_slot(self):
        active = server.state.reserve('test-presenter')
        value = server.CompareInput(message='Synthetic request')
        generator = server.pair_events(active, value)
        while True:
            event = json.loads(await anext(generator))
            if event['type'] == 'delta':
                break
        await generator.aclose()
        self.assertTrue(self.streams[0].closed)
        self.assertTrue(self.clients[0].is_closed)
        self.assertIsNone(server.state.active)

    async def test_disconnect_before_first_generator_advance_releases_reservation(self):
        active = server.state.reserve('test-presenter')
        response = server.ComparisonResponse(active, server.CompareInput(message='Synthetic request'))
        async def send(message):
            raise OSError('Synthetic disconnected socket')
        async def receive():
            return {'type': 'http.disconnect'}
        with self.assertRaises(Exception):
            await response({'type': 'http', 'asgi': {'spec_version': '2.4'}}, receive, send)
        self.assertIsNone(server.state.active)
        self.assertEqual(self.requests, [])

    def test_busy_cooldown_and_per_identity_process_budgets(self):
        first = server.state.reserve('test-presenter')
        with self.assertRaises(server.HTTPException) as caught:
            server.state.reserve('another-presenter')
        self.assertEqual(caught.exception.status_code, 409)
        server.state.release(first)
        with self.assertRaises(server.HTTPException) as caught:
            server.state.reserve('test-presenter')
        self.assertEqual(caught.exception.status_code, 429)
        server.state.last_finished = -float('inf')
        server.state.users['test-presenter'] = server.USER_LIMIT
        with self.assertRaises(server.HTTPException):
            server.state.reserve('test-presenter')
        server.state.attempts = server.PROCESS_LIMIT
        with self.assertRaises(server.HTTPException):
            server.state.reserve('new-presenter')


if __name__ == '__main__':
    unittest.main(verbosity=2)
