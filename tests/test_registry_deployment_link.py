"""Mismatch guards for metadata-only association with an existing deployment."""
import copy
import importlib.util
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
DIRECTORY = ROOT / 'gitops/components/models'
sys.path.insert(0, str(DIRECTORY))
spec = importlib.util.spec_from_file_location('registry_deployment_link', DIRECTORY / 'link_registry_deployment.py')
link = importlib.util.module_from_spec(spec)
spec.loader.exec_module(link)


class DeploymentLinkGuards(unittest.TestCase):
    def setUp(self):
        self.candidate = json.loads((DIRECTORY / 'registry/qwen-4b-candidate.json').read_text())
        self.desired = link.association(self.candidate, 'example-registry', {
            'registered_model': {'id': '17'}, 'model_version': {'id': '23'}})
        self.model = {'metadata': {'labels': {'app.kubernetes.io/part-of': 'rhoai-showroom'}},
                      'spec': {'model': {'uri': self.candidate['uri']}},
                      'status': {'conditions': [{'type': 'Ready', 'status': 'True'}]}}

    def test_different_revision_is_refused(self):
        self.model['spec']['model']['uri'] = 'hf://Qwen/Qwen3-4B-Instruct-2507:another-revision'
        with self.assertRaisesRegex(ValueError, 'URI differs'):
            link.validate_deployment(self.model, self.candidate, self.desired)

    def test_foreign_owner_is_refused(self):
        self.model['metadata']['labels']['app.kubernetes.io/part-of'] = 'another-project'
        with self.assertRaisesRegex(ValueError, 'not owned'):
            link.validate_deployment(self.model, self.candidate, self.desired)

    def test_conflicting_registry_and_version_are_refused(self):
        for key, existing in [('name', 'another-registry'), ('registered-model-id', '18'), ('model-version-id', '24')]:
            with self.subTest(key=key):
                model = copy.deepcopy(self.model)
                model['metadata']['labels'][link.PREFIX + key] = existing
                with self.assertRaisesRegex(ValueError, 'Conflicting existing'):
                    link.validate_deployment(model, self.candidate, self.desired)

    def test_matching_partial_association_is_preserved(self):
        self.model['metadata']['labels'][link.PREFIX + 'registered-model-id'] = '17'
        link.validate_deployment(self.model, self.candidate, self.desired)


if __name__ == '__main__':
    unittest.main()
