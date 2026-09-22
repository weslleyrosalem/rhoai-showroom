import copy
import json
import datetime as dt
import importlib.util
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('capacity',ROOT/'scripts/capacity.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
NOW=dt.datetime(2026,9,22,tzinfo=dt.timezone.utc)

def node(name='existing',instance='g6e.4xlarge',count='1',alloc='1'):
    return {'metadata':{'name':name,'labels':{'node.kubernetes.io/instance-type':instance,'nvidia.com/gpu.count':count}},'status':{'allocatable':{'nvidia.com/gpu':alloc}}}

def inventory(pools=None):
    return {'schema_version':1,'complete':True,'observed_at':NOW.isoformat(),'pools':pools or []}

def pool(ident,kind,current=0,maximum=1,surge=0,names=None):
    return {'id':ident,'instance_type':kind,'current_nodes':current,'desired_nodes':current,
            'max_nodes':maximum,'upgrade_surge_nodes':surge,'node_names':names or []}

def profile(pools=None):
    return {'physical_gpu_limit':16,'pools':pools or []}

class CapacityTests(unittest.TestCase):
    def test_timeslicing_does_not_multiply_physical_devices(self):
        self.assertEqual(m.physical_gpus(node(alloc='8')),1)
    def test_mig_uses_physical_count(self):
        n=node(instance='p4d.24xlarge',count='56',alloc='0')
        n['status']['allocatable']['nvidia.com/mig-1g.5gb']='56'
        self.assertEqual(m.physical_gpus(n),8)
    def test_missing_cloud_inventory_is_blocked(self):
        r=m.assess(profile(),{'items':[node()]},now=NOW)
        self.assertEqual(r['status'],'BLOCKED')
    def test_thirteen_with_no_surge_is_within_limit(self):
        p=profile([{'id':'four','instance_type':'g6e.12xlarge','max_nodes':3,'upgrade_surge_nodes':0}])
        r=m.assess(p,{'items':[node()]},inventory(),NOW)
        self.assertEqual(r['combined_physical_gpu_ceiling'],13)
        self.assertEqual(r['status'],'PASS')
    def test_upgrade_surge_blocks_seventeen(self):
        p=profile([{'id':'four','instance_type':'g6e.12xlarge','max_nodes':3,'upgrade_surge_nodes':0}])
        r=m.assess(p,{'items':[node()]},inventory([pool('four','g6e.12xlarge',surge=1)]),NOW)
        self.assertEqual(r['combined_physical_gpu_ceiling'],17)
        self.assertEqual(r['status'],'BLOCKED')
    def test_old_pool_is_not_assumed_deleted(self):
        p=profile([{'id':'mig','instance_type':'p4d.24xlarge','max_nodes':1,'upgrade_surge_nodes':0}])
        r=m.assess(p,{'items':[node()]},inventory([pool('four','g6e.12xlarge',maximum=2)]),NOW)
        self.assertEqual(r['combined_physical_gpu_ceiling'],17)
        self.assertEqual(r['status'],'BLOCKED')
    def test_pending_and_scaling_down_nodes_remain_counted(self):
        r=m.assess(profile(),{'items':[node()]},inventory([pool('old','g6e.12xlarge',current=4,maximum=0)]),NOW)
        self.assertEqual(r['status'],'BLOCKED')
    def test_node_not_double_counted_when_in_cloud_pool(self):
        r=m.assess(profile(),{'items':[node()]},inventory([pool('old','g6e.4xlarge',1,1,names=['existing'])]),NOW)
        self.assertEqual(r['combined_physical_gpu_ceiling'],1)
    def test_stale_inventory_blocks(self):
        i=inventory();i['observed_at']=(NOW-dt.timedelta(minutes=16)).isoformat()
        self.assertEqual(m.assess(profile(),{'items':[]},i,NOW)['status'],'BLOCKED')
    def test_instance_type_wins_over_gfd_virtual_device_count(self):
        self.assertEqual(m.physical_gpus(node(instance='g6e.12xlarge',count='1')),4)
    def test_cannot_raise_fixed_ceiling(self):
        with self.assertRaises(ValueError):m.assess({'physical_gpu_limit':20,'pools':[]},{'items':[]},inventory(),NOW)
    def test_unknown_accelerator_fails_closed(self):
        n=node();n['metadata']['labels']={'node.kubernetes.io/instance-type':'unknown'}
        with self.assertRaises(ValueError):m.physical_gpus(n)

    def test_active_pool_surge_reaches_exactly_sixteen(self):
        pools=[pool('aiml-node','g6e.4xlarge',3,3,1,['existing']),pool('showroom-l40s4','g6e.12xlarge',2,2,1)]
        i=inventory(pools);i['count_semantics']='upper-bound'
        p=json.loads((ROOT/'gitops/profiles/active-l40s-9/capacity.json').read_text())
        r=m.assess(p,{'items':[node()]},i,NOW)
        self.assertEqual(r['status'],'PASS')
        self.assertEqual(r['combined_physical_gpu_ceiling'],16)
        self.assertIsNone(r['cloud_current_physical_gpus'])
        self.assertEqual(r['cloud_current_physical_gpu_upper_bound'],11)
    def test_active_pool_plus_another_four_gpu_node_is_blocked(self):
        pools=[pool('aiml-node','g6e.4xlarge',3,3,1,['existing']),pool('showroom-l40s4','g6e.12xlarge',2,2,1),pool('extra','g6e.12xlarge',0,1,0)]
        self.assertEqual(m.assess(profile(),{'items':[node()]},inventory(pools),NOW)['status'],'BLOCKED')

if __name__=='__main__':unittest.main()
