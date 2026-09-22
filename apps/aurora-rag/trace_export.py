"""Authenticated OTLP span indexing for the native MLflow static-prefix layout.

MLflow's REST/artifact API is under /mlflow; its installed native OTLP handler is
at /v1/traces. A standard OpenTelemetry processor targets that handler without
changing the singleton server or rewriting the MLflow REST client's endpoints.
"""
import os
from pathlib import Path
from threading import Lock
from urllib.parse import urlsplit, urlunsplit

_LOCK = Lock()
_CONFIGURATION = None


def otlp_endpoint(tracking_uri):
    uri = urlsplit(tracking_uri)
    if (uri.scheme != 'https' or not uri.hostname or uri.username or uri.password
        or uri.query or uri.fragment or uri.path.rstrip('/') != '/mlflow'):
        raise ValueError('Span indexing requires the verified HTTPS MLflow /mlflow endpoint')
    return urlunsplit((uri.scheme, uri.netloc, '/v1/traces', '', ''))


class RotatingServiceAccountAuth:
    """Requests authentication hook: read the current projected token per export."""
    def __init__(self, reader):
        self.reader = reader

    def __call__(self, request):
        token = self.reader()
        if not isinstance(token, str) or not token or '\n' in token or '\r' in token:
            raise RuntimeError('A valid workload identity is required for span export')
        request.headers['Authorization'] = 'Bearer ' + token
        return request


def decoded_export_span(span):
    """Copy one MLflow SDK span into the native OTLP attribute representation.

    MLflow 3.14 stores JSON-encoded values in its underlying OTel span. Its
    documented Span.attributes property decodes them. A generic OTLP exporter
    must receive those decoded values, or the native receiver encodes them a
    second time (for example, TOOL becomes a string containing quote marks).
    The original span remains owned by MLflow's normal artifact exporter.
    """
    from mlflow.entities.span import Span
    from opentelemetry.sdk.trace import ReadableSpan

    return ReadableSpan(name=span.name, context=span.context, parent=span.parent,
        resource=span.resource, attributes=Span(span).attributes,
        events=span.events, links=span.links, kind=span.kind,
        status=span.status, start_time=span.start_time, end_time=span.end_time,
        instrumentation_scope=span.instrumentation_scope)


class DecodedAttributeExporter:
    """Delegate copied spans to the standard exporter without a second trace tree."""
    def __init__(self, delegate):
        self.delegate = delegate

    def export(self, spans):
        return self.delegate.export(tuple(decoded_export_span(span) for span in spans))

    def shutdown(self):
        return self.delegate.shutdown()

    def force_flush(self, timeout_millis=30000):
        return self.delegate.force_flush(timeout_millis=timeout_millis)


def configure_span_metrics(mlflow, experiment_id, token_reader):
    global _CONFIGURATION
    endpoint = otlp_endpoint(os.environ['MLFLOW_TRACKING_URI'])
    workspace = os.environ['MLFLOW_WORKSPACE']
    certificate = os.environ.get('MLFLOW_TRACKING_SERVER_CERT_PATH', '/etc/service-ca/service-ca.crt')
    if not Path(certificate).is_file():
        raise ValueError('The injected service CA is required for OTLP export')
    configuration = (endpoint, str(experiment_id), workspace, certificate)
    with _LOCK:
        if _CONFIGURATION is not None:
            if _CONFIGURATION != configuration:
                raise RuntimeError('Trace export destination changed; restart the app after reviewing configuration')
            return
        import requests
        from opentelemetry import trace
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
        from opentelemetry.sdk.trace.export import BatchSpanProcessor

        class ExactEndpointSession(requests.Session):
            def request(self, method, url, **kwargs):
                if method.upper() != 'POST' or url != endpoint:
                    raise RuntimeError('Unexpected span export destination')
                kwargs['allow_redirects'] = False
                response = super().request(method, url, **kwargs)
                if 300 <= response.status_code < 400:
                    response.close()
                    raise RuntimeError('Span export redirects are disabled')
                return response

        session = ExactEndpointSession()
        session.trust_env = False
        session.auth = RotatingServiceAccountAuth(token_reader)
        exporter = OTLPSpanExporter(endpoint=endpoint, certificate_file=certificate,
            headers={'x-mlflow-experiment-id': str(experiment_id), 'X-MLFLOW-WORKSPACE': workspace},
            session=session, timeout=10)
        # Documented MLflow global-provider mode permits standard OTel processors.
        # The existing MLflow processor still persists the full trace and artifact metadata.
        os.environ['MLFLOW_USE_DEFAULT_TRACER_PROVIDER'] = 'false'
        mlflow.tracing.enable()
        provider = trace.get_tracer_provider()
        provider.add_span_processor(BatchSpanProcessor(DecodedAttributeExporter(exporter), schedule_delay_millis=1000,
                                                       export_timeout_millis=10000))
        _CONFIGURATION = configuration
