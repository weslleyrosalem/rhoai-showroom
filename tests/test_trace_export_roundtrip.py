"""Native parser round trip with the application's pinned MLflow/OTel dependencies.

Run in the app image, or after installing apps/aurora-rag/requirements.txt.
No tracking server, credentials, trace persistence, or model request is used.
"""
import copy
import importlib.util
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('trace_export_roundtrip', ROOT / 'apps/aurora-rag/trace_export.py')
export = importlib.util.module_from_spec(spec)
spec.loader.exec_module(export)

HAS_DEPENDENCIES = importlib.util.find_spec('mlflow') is not None


@unittest.skipUnless(HAS_DEPENDENCIES, 'Install the pinned app dependencies for the native parser round trip')
class NativeSpanRoundTrip(unittest.TestCase):
    def test_tool_and_usage_survive_native_parser_without_mutating_originals(self):
        import requests
        from mlflow.entities.span import Span
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
        from opentelemetry.proto.collector.trace.v1.trace_service_pb2 import ExportTraceServiceRequest
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import Event, ReadableSpan
        from opentelemetry.sdk.trace.export import SpanExportResult
        from opentelemetry.sdk.util.instrumentation import InstrumentationScope
        from opentelemetry.trace import Link, SpanContext, SpanKind, Status, StatusCode, TraceFlags

        class CaptureSession(requests.Session):
            def post(self, url, data, **kwargs):
                self.body = data
                response = requests.Response()
                response.status_code = 200
                response._content = b''
                return response

        trace_id = 0x123456789ABCDEF123456789ABCDEF12
        parent = SpanContext(trace_id=trace_id, span_id=1, is_remote=False, trace_flags=TraceFlags(1))
        usage = {'input_tokens': 1580, 'output_tokens': 301, 'total_tokens': 1881}
        source_spans = []
        for number, kind in ((2, 'TOOL'), (3, 'LLM')):
            # This is MLflow 3.14's actual underlying SDK attribute representation.
            attributes = {'mlflow.spanType': json.dumps(kind),
                          'mlflow.traceRequestId': json.dumps('tr-' + format(trace_id, '032x'))}
            if kind == 'TOOL':
                attributes['mlflow.spanInputs'] = json.dumps({'sku': 'AS-001'})
            else:
                attributes['mlflow.chat.tokenUsage'] = json.dumps(usage)
            source_spans.append(ReadableSpan(
                name='aurora_get_stock' if kind == 'TOOL' else 'maas_inference',
                context=SpanContext(trace_id=trace_id, span_id=number, is_remote=False, trace_flags=TraceFlags(1)),
                parent=parent, resource=Resource({'service.name': 'aurora-rag'}),
                attributes=attributes, events=(Event('safe-event', {'status': 'completed'}, 110),),
                links=(Link(parent, {'purpose': 'synthetic-test'}),),
                kind=SpanKind.INTERNAL, status=Status(StatusCode.OK), start_time=100, end_time=200,
                instrumentation_scope=InstrumentationScope('mlflow', '3.14.0')))
        original_attributes = [copy.deepcopy(dict(span.attributes)) for span in source_spans]
        session = CaptureSession()
        standard = OTLPSpanExporter(endpoint='https://unused.example/v1/traces', session=session)
        wrapper = export.DecodedAttributeExporter(standard)
        try:
            self.assertEqual(wrapper.export(source_spans), SpanExportResult.SUCCESS)
            payload = ExportTraceServiceRequest.FromString(session.body)
            wire_spans = [span for resource in payload.resource_spans
                          for scope in resource.scope_spans for span in scope.spans]
            self.assertEqual(len(wire_spans), 2)
            parsed = [Span.from_otel_proto(span) for span in wire_spans]
            self.assertEqual([span.span_type for span in parsed], ['TOOL', 'LLM'])
            self.assertEqual(parsed[0].inputs, {'sku': 'AS-001'})
            self.assertEqual(parsed[1].attributes['mlflow.chat.tokenUsage'], usage)
            self.assertEqual(sum('mlflow.chat.tokenUsage' in span.attributes for span in parsed), 1)
            self.assertTrue(all(type(count) is int for count in parsed[1].attributes['mlflow.chat.tokenUsage'].values()))
            for source, wire, recovered, before in zip(source_spans, wire_spans, parsed, original_attributes):
                self.assertEqual(dict(source.attributes), before)
                self.assertEqual(wire.trace_id, trace_id.to_bytes(16, 'big'))
                self.assertEqual(wire.span_id, source.context.span_id.to_bytes(8, 'big'))
                self.assertEqual(wire.parent_span_id, parent.span_id.to_bytes(8, 'big'))
                self.assertEqual((wire.start_time_unix_nano, wire.end_time_unix_nano), (100, 200))
                self.assertEqual(wire.events[0].name, 'safe-event')
                self.assertEqual(wire.events[0].time_unix_nano, 110)
                self.assertEqual(wire.links[0].span_id, parent.span_id.to_bytes(8, 'big'))
                self.assertEqual(recovered.attributes, Span(source).attributes)
            self.assertEqual(len({span.span_id for span in parsed}), 2)
        finally:
            wrapper.shutdown()


if __name__ == '__main__':
    unittest.main()
