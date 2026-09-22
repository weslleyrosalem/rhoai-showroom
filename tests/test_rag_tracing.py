"""Trace security and real-usage semantics without network, credentials, or MLflow."""
import importlib.util
import json
from pathlib import Path
import unittest
import traceback
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('rag_tracing', ROOT / 'apps/aurora-rag/rag.py')
rag = importlib.util.module_from_spec(spec)
spec.loader.exec_module(rag)


class FakeSpan:
    def __init__(self, name, span_type):
        self.record = {'name': name, 'type': span_type, 'attributes': {}}
        self.trace_id = 'test-trace'
    def __enter__(self):
        return self
    def __exit__(self, kind, value, tb):
        if value is not None:
            self.record['exception'] = {'message': str(value),
                                        'traceback': ''.join(traceback.format_exception(kind, value, tb))}
        return False
    def set_attribute(self, key, value):
        self.record['attributes'][key] = value
    def set_inputs(self, value):
        self.record['inputs'] = value
    def set_outputs(self, value):
        self.record['outputs'] = value


class FakeMlflow:
    def __init__(self):
        self.spans = []
    def start_span(self, name, span_type):
        span = FakeSpan(name, span_type)
        self.spans.append(span)
        return span
    def serialized(self):
        return json.dumps([span.record for span in self.spans])


class FakeResult:
    isError = False
    def model_dump(self, mode):
        return {'content': [{'type': 'text', 'text': json.dumps({'sku': 'AS-001', 'target_stock': 391,
            'stock': 45, 'recommended_quantity': 346, 'private_extra': 'DO_NOT_CAPTURE_TOOL_PAYLOAD'})}]}


class FakeSession:
    async def call_tool(self, name, arguments):
        return FakeResult()


class RagTracingTest(unittest.TestCase):
    def setUp(self):
        self.mlflow = FakeMlflow()
        self.retriever = rag.Retriever(ROOT / 'data/documents')
        self.result = {'answer': 'Use the tool-calculated proposal and request human approval.',
                       'usage': {'prompt_tokens': 1200, 'completion_tokens': 386, 'total_tokens': 1586},
                       'model': 'example-model'}

    def test_blocked_input_creates_no_trace(self):
        with patch.object(rag, 'guardrail_check', side_effect=rag.GuardrailBlocked('Content blocked')), \
             patch.object(rag, 'configure_tracing') as configure:
            with self.assertRaises(rag.GuardrailBlocked):
                rag.ask('BLOCKED_INPUT_MARKER', self.retriever, False)
        configure.assert_not_called()

    def test_blocked_or_unavailable_output_never_enters_trace(self):
        for error in (rag.GuardrailBlocked('Content blocked'), RuntimeError('Guardrail unavailable')):
            with self.subTest(error=type(error).__name__):
                mlflow = FakeMlflow()
                result = {**self.result, 'answer': 'DO_NOT_CAPTURE_MODEL_ANSWER'}
                with patch.object(rag, 'guardrail_check', side_effect=['success', error]), \
                     patch.object(rag, 'configure_tracing', return_value=mlflow), \
                     patch.object(rag, 'complete', return_value=result):
                    with self.assertRaises(type(error)):
                        rag.ask('What is the return deadline?', self.retriever, False)
                self.assertNotIn('DO_NOT_CAPTURE_MODEL_ANSWER', mlflow.serialized())
                self.assertNotIn('"answer"', mlflow.serialized())

    def test_allowed_trace_has_real_usage_and_two_actual_tool_spans(self):
        async def tools(sku, mlflow):
            return {name: await rag.call_mcp_tool(FakeSession(), name, sku, mlflow)
                    for name in ('aurora_get_stock', 'aurora_get_replenishment_recommendation')}
        with patch.object(rag, 'guardrail_check', return_value='success'), \
             patch.object(rag, 'configure_tracing', return_value=self.mlflow), \
             patch.object(rag, 'tools_for_sku', side_effect=tools), \
             patch.object(rag, 'complete', return_value=self.result) as complete:
            result = rag.ask('Should I replenish AS-001?', self.retriever)
        spans = [span.record for span in self.mlflow.spans]
        llm = next(span for span in spans if span['type'] == 'LLM')
        self.assertEqual(llm['attributes']['mlflow.chat.tokenUsage'],
                         {'input_tokens': 1200, 'output_tokens': 386, 'total_tokens': 1586})
        self.assertEqual(sum(span['type'] == 'TOOL' for span in spans), 2)
        self.assertTrue({'CHAIN', 'RETRIEVER', 'TOOL', 'LLM', 'GUARDRAIL'} <= {span['type'] for span in spans})
        self.assertEqual(sum('mlflow.chat.tokenUsage' in span['attributes'] for span in spans), 1)
        self.assertEqual(result['decision']['recommended_quantity'], 346)
        # Raw tool payloads do not enter tool-span records; the final decision is addressed separately.
        tools_record = json.dumps([span for span in spans if span['type'] == 'TOOL'])
        self.assertNotIn('DO_NOT_CAPTURE_TOOL_PAYLOAD', tools_record)
        self.assertNotIn('DO_NOT_CAPTURE_TOOL_PAYLOAD', self.mlflow.serialized())
        self.assertNotIn('Authorization', self.mlflow.serialized())
        self.assertNotIn('mlflow.llm.cost', self.mlflow.serialized())
        prompt = complete.call_args.args[0][0]['content']
        self.assertIn('max(reorder_point, ceil(forecast_7d_units * 21 / 7))', prompt)
        self.assertIn('max(0, target_stock - stock)', prompt)

    def test_external_exception_events_do_not_capture_upstream_text(self):
        for boundary in ('llm', 'guardrail', 'mcp_connection', 'mcp_tool'):
            with self.subTest(boundary=boundary):
                mlflow = FakeMlflow()
                async def broken_tools(sku, context):
                    if boundary == 'mcp_connection':
                        raise RuntimeError('DO_NOT_CAPTURE_UPSTREAM_TEXT')
                    class BrokenSession:
                        async def call_tool(self, name, arguments):
                            raise RuntimeError('DO_NOT_CAPTURE_UPSTREAM_TEXT')
                    return await rag.call_mcp_tool(BrokenSession(), 'aurora_get_stock', sku, context)
                guardrails = ['success', RuntimeError('DO_NOT_CAPTURE_UPSTREAM_TEXT')] if boundary == 'guardrail' else None
                with patch.object(rag, 'guardrail_check', side_effect=guardrails, return_value='success'), \
                     patch.object(rag, 'configure_tracing', return_value=mlflow), \
                     patch.object(rag, 'complete', side_effect=RuntimeError('DO_NOT_CAPTURE_UPSTREAM_TEXT') if boundary == 'llm' else None,
                                  return_value=self.result), \
                     patch.object(rag, 'tools_for_sku', side_effect=broken_tools):
                    with self.assertRaises(RuntimeError):
                        rag.ask('Should I replenish AS-001?' if boundary.startswith('mcp') else 'What is the return deadline?',
                                self.retriever, boundary.startswith('mcp'))
                self.assertNotIn('DO_NOT_CAPTURE_UPSTREAM_TEXT', mlflow.serialized())
                self.assertTrue(any('exception' in span.record for span in mlflow.spans))

    def test_invalid_usage_is_not_reported_as_measured_tokens(self):
        for value in (True, -1, 1.25, '1200', None):
            with self.subTest(value=value):
                self.assertEqual(rag.token_usage({'prompt_tokens': value, 'completion_tokens': 386, 'total_tokens': 1586}), {})
        self.assertEqual(rag.token_usage({'prompt_tokens': 1200, 'completion_tokens': 386, 'total_tokens': 1}), {})


if __name__ == '__main__':
    unittest.main()
