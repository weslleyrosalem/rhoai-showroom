"""Offline publication-boundary tests; no cluster calls or inference."""
import copy
import json
from pathlib import Path
import tempfile
import unittest

from ahead_llmd import MODEL, PUBLIC_ROOT, bounded_generation, private_output_path
from summarize_ahead_llmd import MODES, MODEL_URI, summarize


def fixture(root):
    evidence = {
        'status': 'MEASURED', 'started_at': '2026-09-22T06:10:00+00:00',
        'finished_at': '2026-09-22T06:11:30+00:00',
        'topology': {'ready_backends': 2, 'distinct_gpu_nodes': 2, 'gpu_type': 'NVIDIA L40S',
                     'model': {'name': 'aurora-qwen-4b', 'uri': MODEL_URI},
                     'runtime_image': 'registry.redhat.io/rhaii/vllm@sha256:' + 'a' * 64,
                     'scheduler_image': 'registry.redhat.io/rhoai/epp@sha256:' + 'b' * 64,
                     'scheduler_config': 'prefix-cache-scorer'},
        'workload': {'seconds_per_mode': 30, 'concurrency': {mode: 1 if mode == 'single' else 2 for mode in MODES},
                     'output_tokens': 32, 'guidellm_version': '0.6.0', 'prompt_rows': 16, 'unique_questions': 4},
        'authentication': {'anonymous_status': 401, 'authorized_status': 200},
        'limitations': [],
        'runs': [{'mode': 'single', 'exit_code': 0, 'prompt_sha256': 'c' * 64, 'proxy_errors': 0,
                  'proxy_requests': [{'status': 200, 'backend': 0}], 'picker_delta': {},
                  'backend_delta': [{'vllm:prefix_cache_queries_total': 10, 'vllm:prefix_cache_hits_total': 8}, {}]}],
    }
    metrics = {'request_totals': {'successful': 1, 'errored': 0, 'incomplete': 0, 'total': 1}}
    for key in ('time_to_first_token_ms', 'request_latency', 'requests_per_second',
                'output_tokens_per_second', 'prompt_token_count', 'output_token_count'):
        metrics[key] = {'successful': {'mean': 1.0, 'percentiles': {'p50': 1.0, 'p95': 2.0}}}
    report = {'benchmarks': [{'duration': 30, 'metrics': metrics}]}
    (root / 'single').mkdir()
    (root / 'single/benchmarks.json').write_text(json.dumps(report))
    (root / 'evidence.json').write_text(json.dumps(evidence))
    return evidence, report


class PublicationBoundaries(unittest.TestCase):
    def test_both_token_limit_aliases_are_bounded(self):
        self.assertTrue(bounded_generation({'model': MODEL, 'max_tokens': 32}))
        self.assertTrue(bounded_generation({'model': MODEL, 'max_completion_tokens': 64}))
        for values in ({'max_tokens': 32, 'max_completion_tokens': 65},
                       {'max_tokens': 65, 'max_completion_tokens': 32},
                       {'max_tokens': True}, {'max_tokens': 1.5}, {}):
            self.assertFalse(bounded_generation(dict(values, model=MODEL)))

    def test_private_output_rejects_repo_existing_and_alias(self):
        with self.assertRaises(ValueError):
            private_output_path(PUBLIC_ROOT / 'raw-evidence')
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with self.assertRaises(ValueError):
                private_output_path(root)
            (root / 'alias').symlink_to(PUBLIC_ROOT, target_is_directory=True)
            with self.assertRaises(ValueError):
                private_output_path(root / 'alias/raw-evidence')
            self.assertEqual(private_output_path(root / 'new'), root.resolve() / 'new')

    def test_nested_private_values_are_never_exported(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            evidence, report = fixture(root)
            marker = 'PRIVATE_CONFIG_SENTINEL'
            evidence['topology']['model']['credentials'] = marker
            evidence['topology']['scheduler_config'] += '\napi-key: ' + marker
            evidence['authentication']['bearer'] = marker
            evidence['workload']['endpoint'] = marker
            evidence['limitations'].append(marker)
            evidence['runs'][0]['proxy_requests'][0]['prompt'] = marker
            report['benchmarks'][0]['metrics']['request_totals']['private'] = marker
            (root / 'evidence.json').write_text(json.dumps(evidence))
            (root / 'single/benchmarks.json').write_text(json.dumps(report))
            result = summarize(root)
            self.assertNotIn(marker, json.dumps(result))
            self.assertEqual(result['runs'][0]['observed_cache_hit_fraction'], 0.8)

    def test_rejects_traversal_and_symlinked_reports(self):
        with tempfile.TemporaryDirectory() as directory, tempfile.TemporaryDirectory() as outside:
            root = Path(directory)
            evidence, _ = fixture(root)
            altered = copy.deepcopy(evidence)
            altered['runs'][0]['mode'] = '../outside'
            (root / 'evidence.json').write_text(json.dumps(altered))
            with self.assertRaises(ValueError):
                summarize(root)
            (root / 'evidence.json').write_text(json.dumps(evidence))
            report = root / 'single/benchmarks.json'
            report.unlink()
            report.symlink_to(Path(outside) / 'report.json')
            with self.assertRaises(ValueError):
                summarize(root)

    def test_rejects_nonfinite_or_failed_measurement(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            evidence, report = fixture(root)
            report['benchmarks'][0]['metrics']['request_latency']['successful']['mean'] = float('nan')
            (root / 'single/benchmarks.json').write_text(json.dumps(report))
            with self.assertRaises(ValueError):
                summarize(root)
            evidence['status'] = 'INCOMPLETE'
            (root / 'evidence.json').write_text(json.dumps(evidence))
            with self.assertRaises(ValueError):
                summarize(root)


if __name__ == '__main__':
    unittest.main()
