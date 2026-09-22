"""Hardware mismatch guards: a native association must describe the live spec."""
import copy
import importlib.util
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
DIRECTORY = ROOT / 'gitops/components/models'
sys.path.insert(0, str(DIRECTORY))
spec = importlib.util.spec_from_file_location('hardware_profile_link', DIRECTORY / 'link_hardware_profile.py')
link = importlib.util.module_from_spec(spec)
spec.loader.exec_module(link)


class HardwareProfileGuards(unittest.TestCase):
    def setUp(self):
        self.candidate = json.loads((DIRECTORY / 'registry/qwen-4b-candidate.json').read_text())
        self.profile = json.loads((ROOT / 'gitops/components/platform/base/showroom-l40s-1.yaml').read_text())
        self.profile['metadata']['resourceVersion'] = 'test-version'
        self.model = {'metadata': {'labels': {'app.kubernetes.io/part-of': 'rhoai-showroom'}},
                      'spec': {'model': {'uri': self.candidate['uri']}, 'template': {
                          'containers': [{'name': 'main', 'resources': {
                              'requests': {'cpu': '4', 'memory': '24Gi', 'nvidia.com/gpu': '1'},
                              'limits': {'cpu': '4', 'memory': '24Gi', 'nvidia.com/gpu': '1'}}}],
                          'nodeSelector': copy.deepcopy(self.profile['spec']['scheduling']['node']['nodeSelector']),
                          'tolerations': copy.deepcopy(self.profile['spec']['scheduling']['node']['tolerations'])}}}

    def test_insufficient_resources_are_refused(self):
        self.model['spec']['template']['containers'][0]['resources']['requests']['cpu'] = '2'
        with self.assertRaisesRegex(ValueError, 'resources differ'):
            link.validate(self.model, self.profile, self.candidate)

    def test_missing_gpu_selector_is_refused(self):
        del self.model['spec']['template']['nodeSelector']['nvidia.com/gpu.product']
        with self.assertRaisesRegex(ValueError, 'node selectors'):
            link.validate(self.model, self.profile, self.candidate)

    def test_stricter_node_selection_preserves_compatibility(self):
        self.model['spec']['template']['nodeSelector']['node.kubernetes.io/instance-type'] = 'g6e.2xlarge'
        desired = link.validate(self.model, self.profile, self.candidate)
        self.assertEqual(desired['annotations'][link.PREFIX + 'name'], 'showroom-l40s-1')


if __name__ == '__main__':
    unittest.main()
