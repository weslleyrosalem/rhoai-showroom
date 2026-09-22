"""Credential destination and projected-token rotation guards for OTLP indexing."""
import importlib.util
from pathlib import Path
from types import SimpleNamespace
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('trace_export', ROOT / 'apps/aurora-rag/trace_export.py')
export = importlib.util.module_from_spec(spec)
spec.loader.exec_module(export)


class TraceExportGuards(unittest.TestCase):
    def test_endpoint_preserves_authenticated_origin(self):
        self.assertEqual(export.otlp_endpoint('https://mlflow.example.svc:8443/mlflow'),
                         'https://mlflow.example.svc:8443/v1/traces')
        for bad in ('http://mlflow.example/mlflow', 'https://user:password@mlflow.example/mlflow',
                    'https://mlflow.example/other', 'https://mlflow.example/mlflow?target=elsewhere',
                    'https://mlflow.example/mlflow#fragment'):
            with self.subTest(uri=bad), self.assertRaises(ValueError):
                export.otlp_endpoint(bad)

    def test_each_export_uses_the_current_projected_token(self):
        values = iter(['first-synthetic-token', 'rotated-synthetic-token'])
        auth = export.RotatingServiceAccountAuth(lambda: next(values))
        first = auth(SimpleNamespace(headers={}));second = auth(SimpleNamespace(headers={}))
        self.assertEqual(first.headers['Authorization'], 'Bearer first-synthetic-token')
        self.assertEqual(second.headers['Authorization'], 'Bearer rotated-synthetic-token')

    def test_missing_or_injected_token_fails_closed(self):
        for value in ('', None, 'token\nInjected: header', 'token\rInjected: header'):
            with self.subTest(value=value), self.assertRaises(RuntimeError):
                export.RotatingServiceAccountAuth(lambda: value)(SimpleNamespace(headers={}))


if __name__ == '__main__':
    unittest.main()
