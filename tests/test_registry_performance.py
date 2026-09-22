"""Reject misleading or conflicting reference evidence without changing a cluster."""
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
MODELS = ROOT / 'gitops/components/models'
sys.path.insert(0, str(MODELS))
spec = importlib.util.spec_from_file_location('record_performance', MODELS / 'record_performance.py')
performance = importlib.util.module_from_spec(spec)
spec.loader.exec_module(performance)
registry = performance.registry
CANDIDATE = json.loads((MODELS / 'registry/qwen-4b-candidate.json').read_text())
REPORT = json.loads((ROOT / performance.REPORT_PATH).read_text())


def candidate_properties():
    return registry.properties({
        'showroom.owner': registry.OWNER, 'showroom.lifecycle': 'candidate',
        'showroom.performance_evaluation': 'NOT_RUN', 'showroom.safety_evaluation': 'FAILED',
        'showroom.runtime_validation': 'PASSED_PROTOCOL_TOOL_AND_ROUTING',
        'showroom.runtime_evidence_sha256': 'a' * 64,
        'showroom.deployment_manifest': 'gitops/components/models/qwen-4b',
    })


class ReferenceEvidenceTests(unittest.TestCase):
    def test_retained_public_report_has_comparable_runs(self):
        resolved = performance.validate_report(REPORT, CANDIDATE)
        self.assertEqual(resolved, REPORT['runs'][0]['metadata']['resolved_image'])

    def test_rejects_changed_and_missing_measurement_constraints(self):
        cases = [('cpu_limit', '8'), ('memory_limit', '64Gi'), ('max_model_len', None),
                 ('chat_template_sha256', None), ('tensor_parallel', None), ('pipeline_parallel', 2),
                 ('data_parallel', None), ('model_revision', 'a' * 40), ('cache_mode', 'on'),
                 ('image_digest', 'runtime:latest'), ('resolved_image', 'runtime:latest'),
                 ('scheduling', 'unverified')]
        for key, value in cases:
            with self.subTest(field=key), self.assertRaises(ValueError):
                report = copy.deepcopy(REPORT)
                for row in report['runs']:
                    if value is None:
                        row['metadata'].pop(key, None)
                    else:
                        row['metadata'][key] = value
                performance.validate_report(report, CANDIDATE)

    def test_failed_or_incomplete_requests_cannot_be_published_as_measured(self):
        for field, value in [('ok', False), ('http_status', 429)]:
            with self.subTest(field=field), self.assertRaises(ValueError):
                report = copy.deepcopy(REPORT)
                report['runs'][0]['requests'][0][field] = value
                performance.validate_report(report, CANDIDATE)

    def test_template_or_workload_changes_between_concurrency_levels_are_rejected(self):
        for section, key in [('metadata', 'chat_template_sha256'), ('config', 'workload_sha256')]:
            with self.subTest(field=key), self.assertRaises(ValueError):
                report = copy.deepcopy(REPORT)
                for row in report['runs']:
                    if row['config']['concurrency'] == 2:
                        row[section][key] = 'b' * 64
                performance.validate_report(report, CANDIDATE)

    def test_original_hash_and_same_physical_host_are_required(self):
        report = copy.deepcopy(REPORT)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            originals = []
            for row in report['runs']:
                original = {k: v for k, v in row.items() if k != 'private_original_sha256'}
                original['metadata'] = {**row['metadata'], 'node': 'one-physical-host', 'pod_uid': 'one-pod'}
                name = f"{row['metadata']['engine']}-c{row['config']['concurrency']}.json"
                raw = json.dumps(original).encode()
                (path / name).write_bytes(raw)
                row['private_original_sha256'] = hashlib.sha256(raw).hexdigest()
                originals.append((name, original))
            performance.verify_originals(report, path)
            name, original = originals[-1]
            original['metadata']['node'] = 'different-host'
            raw = json.dumps(original).encode()
            (path / name).write_bytes(raw)
            with self.assertRaisesRegex(ValueError, 'hash differs'):
                performance.verify_originals(report, path)
            report['runs'][-1]['private_original_sha256'] = hashlib.sha256(raw).hexdigest()
            with self.assertRaisesRegex(ValueError, 'same physical host'):
                performance.verify_originals(report, path)


class MetadataUpdateTests(unittest.TestCase):
    def test_preserves_failed_safety_candidate_runtime_and_immutable_provenance(self):
        before = candidate_properties()
        original = copy.deepcopy(before)
        after = performance.performance_properties(before, 'b' * 64, 'https://example.com/evidence', 'measured-time')
        self.assertEqual(before, original)
        for key in before:
            if key != 'showroom.performance_evaluation':
                self.assertEqual(after[key], before[key])
        self.assertEqual(after['showroom.performance_evaluation']['string_value'], 'MEASURED_REFERENCE_ONLY')
        self.assertEqual(after['showroom.runtime_manifest']['string_value'], performance.RUNTIME_MANIFEST)
        self.assertEqual(performance.performance_properties(after, 'b' * 64,
            'https://example.com/evidence', 'measured-time'), after)

    def test_foreign_promoted_or_already_decided_candidate_is_rejected(self):
        for key, value in [('showroom.owner', 'someone-else'), ('showroom.lifecycle', 'approved'),
                           ('showroom.performance_evaluation', 'PASSED'),
                           ('showroom.performance_evidence_sha256', 'c' * 64)]:
            with self.subTest(property=key), self.assertRaises(ValueError):
                before = candidate_properties()
                before.update(registry.properties({key: value}))
                performance.performance_properties(before, 'b' * 64, 'https://example.com/evidence', 'measured-time')

    def test_observed_concurrent_change_aborts_before_patch(self):
        class Client:
            writes = 0
            def request(self, path, body=None, method=None):
                if body is not None:
                    self.writes += 1
                return {'customProperties': {'concurrent': 'change'}}
        client = Client()
        with self.assertRaisesRegex(ValueError, 'changed during review'):
            performance.update_if_unchanged(client, '2', {'customProperties': candidate_properties()}, {})
        self.assertEqual(client.writes, 0)

    def test_audit_file_is_exclusive_and_private_from_creation(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            old_umask = os.umask(0)
            try:
                performance.save(path, 'evidence.json', {'safe': 'metadata'})
            finally:
                os.umask(old_umask)
            self.assertEqual((path / 'evidence.json').stat().st_mode & 0o777, 0o600)
            with self.assertRaises(FileExistsError):
                performance.save(path, 'evidence.json', {})


if __name__ == '__main__':
    unittest.main()
