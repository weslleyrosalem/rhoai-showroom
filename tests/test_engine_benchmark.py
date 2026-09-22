import copy
import importlib.util
from pathlib import Path
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('engine_benchmark', ROOT / 'scripts/engine_benchmark.py')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


def fixture():
    model = {'metadata': {'labels': {'app.kubernetes.io/part-of': 'rhoai-showroom'}},
             'spec': {'replicas': 2, 'model': {'uri': 'hf://Qwen/Qwen3-4B-Instruct-2507:' + m.REVISION},
                      'template': {'containers': [{'image': m.IMAGE}]}}}
    pods = [{'metadata': {'name': str(i), 'creationTimestamp': str(i)},
             'spec': {'nodeName': 'node' + str(i)},
             'status': {'conditions': [{'type': 'Ready', 'status': 'True'}]}} for i in [1, 2]]
    nodes = [{'metadata': {'name': 'node' + str(i), 'labels': {
                'node.kubernetes.io/instance-type': 'g6e.2xlarge',
                'nvidia.com/gpu.product': 'NVIDIA-L40S',
                'showroom.openshift.ai/gpu-pool': 'true'}},
              'status': {'capacity': {'nvidia.com/gpu': '1'}, 'allocatable': {'nvidia.com/gpu': '1'}}}
             for i in [1, 2]]
    return model, pods, nodes


class EngineRehearsalGuards(unittest.TestCase):
    def test_reuses_newest_existing_replica(self):
        model, pods, nodes = fixture()
        victim, count = m.inspect_capacity(model, pods, nodes)
        self.assertEqual(victim['metadata']['name'], '2')
        self.assertEqual(count, 2)

    def test_requires_other_ready_replica(self):
        model, pods, nodes = fixture()
        pods[0]['status']['conditions'][0]['status'] = 'False'
        with self.assertRaises(ValueError):
            m.inspect_capacity(model, pods, nodes)

    def test_refuses_same_host(self):
        model, pods, nodes = fixture()
        pods[1]['spec']['nodeName'] = pods[0]['spec']['nodeName']
        with self.assertRaises(ValueError):
            m.inspect_capacity(model, pods, nodes)

    def test_refuses_argocd_reconciliation_conflict(self):
        model, pods, nodes = fixture()
        model['metadata']['annotations'] = {'argocd.argoproj.io/tracking-id': 'another-app'}
        with self.assertRaises(ValueError):
            m.inspect_capacity(model, pods, nodes)

    def test_refuses_over_ceiling_and_different_hardware(self):
        for change in ['ceiling', 'hardware']:
            model, pods, nodes = fixture()
            if change == 'ceiling':
                extra = copy.deepcopy(nodes[0])
                extra['metadata']['name'] = 'third'
                extra['status']['capacity']['nvidia.com/gpu'] = '15'
                nodes.append(extra)
            else:
                nodes[0]['metadata']['labels']['nvidia.com/gpu.product'] = 'NVIDIA-H100'
            with self.assertRaises(ValueError):
                m.inspect_capacity(model, pods, nodes)

    def test_requires_identical_immutable_model_and_image(self):
        for field in ['model', 'image']:
            model, pods, nodes = fixture()
            if field == 'model':
                model['spec']['model']['uri'] = 'hf://Qwen/Qwen3-4B-Instruct-2507:main'
            else:
                model['spec']['template']['containers'][0]['image'] = 'image:latest'
            with self.assertRaises(ValueError):
                m.inspect_capacity(model, pods, nodes)

    def test_cache_disabled_and_loopback_bound(self):
        command = m.engine_command('vllm')
        self.assertIn('--no-enable-prefix-caching', command)
        self.assertEqual(command[command.index('--host') + 1], '127.0.0.1')

    def test_reconciles_successful_scale_with_lost_response(self):
        original = {'metadata': {'uid': 'original'}}
        live = {'metadata': {'uid': 'original'}, 'spec': {'replicas': 1}}
        with mock.patch.object(m, 'get', return_value=live), mock.patch.object(m, 'scale') as scale:
            m.restore_model(original)
            scale.assert_called_once_with(original, 1, 2)

    def test_does_not_rewrite_already_restored_or_replaced_model(self):
        original = {'metadata': {'uid': 'original'}}
        live = {'metadata': {'uid': 'original'}, 'spec': {'replicas': 2}}
        with mock.patch.object(m, 'get', return_value=live), mock.patch.object(m, 'scale') as scale:
            m.restore_model(original)
            scale.assert_not_called()
        for changed in [dict(live, metadata={'uid': 'replacement'}),
                        dict(live, spec={'replicas': 3})]:
            with mock.patch.object(m, 'get', return_value=changed), mock.patch.object(m, 'scale') as scale:
                with self.assertRaises(RuntimeError):
                    m.restore_model(original)
                scale.assert_not_called()


if __name__ == '__main__':
    unittest.main()
