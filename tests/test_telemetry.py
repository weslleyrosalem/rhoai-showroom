"""Validate the narrow scope of the optional dashboard compatibility resources."""
from pathlib import Path
import re
import unittest
import yaml

ROOT = Path(__file__).resolve().parents[1]


def relabel(labels, rules):
    labels = dict(labels)
    for rule in rules:
        value = rule.get('separator', ';').join(labels.get(key, '') for key in rule['sourceLabels'])
        match = re.fullmatch(rule.get('regex', '(.*)'), value)
        if rule['action'] == 'keep' and not match:
            return None
        if rule['action'] == 'replace' and match:
            replacement = rule.get('replacement', '$1')
            for index, group in enumerate(match.groups(), 1):
                replacement = replacement.replace('$' + str(index), group)
            labels[rule['targetLabel']] = replacement
    return labels


class TelemetryScopeTests(unittest.TestCase):
    def setUp(self):
        self.monitor = yaml.safe_load((ROOT / 'gitops/components/platform/telemetry/telemetry.yaml').read_text())
        self.rules = self.monitor['spec']['podMetricsEndpoints'][0]['metricRelabelings']

    def test_only_real_utilization_of_explicit_models_passes(self):
        for namespace, model in [('ai-showroom', 'aurora-qwen-4b'),
                                 ('maas-how-to', 'redhataillama-31-8b-instruct')]:
            pod = model + '-kserve-abc-def'
            output = relabel({'__name__': 'DCGM_FI_DEV_GPU_UTIL', 'namespace': namespace, 'pod': pod}, self.rules)
            self.assertEqual(output['__name__'], 'accelerator_gpu_utilization')
            self.assertEqual(output['model_name'], model)
            self.assertEqual(output['workload_pod'], pod)
            self.assertNotIn('k8s_pod_name', output)  # Avoid OTel resource-attribute collision.

    def test_foreign_model_namespace_and_metric_are_excluded(self):
        sample = {'__name__': 'DCGM_FI_DEV_GPU_UTIL', 'namespace': 'ai-showroom', 'pod': 'aurora-qwen-4b-kserve-a-b'}
        for change in [{'namespace': 'foreign'}, {'pod': 'another-model-kserve-a-b'},
                       {'__name__': 'DCGM_FI_DEV_FB_USED'}, {'namespace': 'ai-showroom-extra'}]:
            self.assertIsNone(relabel(dict(sample, **change), self.rules))

    def test_scrape_targets_only_nvidia_exporter_without_credentials(self):
        spec = self.monitor['spec']
        self.assertEqual(spec['namespaceSelector'], {'matchNames': ['nvidia-gpu-operator']})
        self.assertEqual(spec['selector']['matchLabels'], {'app': 'nvidia-dcgm-exporter'})
        endpoint = spec['podMetricsEndpoints'][0]
        self.assertNotIn('authorization', endpoint)
        self.assertEqual(endpoint['interval'], '30s')


if __name__ == '__main__':
    unittest.main()
