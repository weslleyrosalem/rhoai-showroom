import base64
import importlib.util
from pathlib import Path
import unittest
from unittest.mock import patch
spec=importlib.util.spec_from_file_location('showroom',Path(__file__).resolve().parents[1]/'scripts/showroom.py')
mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)

def obj(values,owned=True):
    return {'metadata':{'labels':{'app.kubernetes.io/part-of':'rhoai-showroom'} if owned else {}},'data':{k:base64.b64encode(v.encode()).decode() for k,v in values.items()}}

class SecretAdoption(unittest.TestCase):
    def test_foreign_secret_fails_closed_without_write(self):
        with patch.object(mod,'get',return_value=obj({'key':'synthetic'},False)),patch.object(mod,'apply') as apply:
            with self.assertRaisesRegex(RuntimeError,'ownership'):mod.secret('connection','ai-showroom',{'key':'unused'},'https://expected')
            apply.assert_not_called()
    def test_missing_required_key_fails_closed(self):
        with patch.object(mod,'get',return_value=obj({'unrelated':'synthetic'})):
            with self.assertRaisesRegex(RuntimeError,'required'):mod.secret('connection','ai-showroom',{'key':'unused'},'https://expected')
    def test_existing_primary_is_reused_without_rotation(self):
        existing=obj({'key':'synthetic-current'})
        with patch.object(mod,'get',return_value=existing),patch.object(mod,'apply') as apply:
            self.assertEqual(existing['data'],mod.secret('connection','ai-showroom',{'key':'synthetic-generated'},'https://expected'))
            apply.assert_not_called()
    def test_inconsistent_s3_copies_are_rejected(self):
        with patch.object(mod,'get',return_value=obj({'key':'synthetic-other'})):
            with self.assertRaisesRegex(RuntimeError,'diverges'):mod.secret('connection','ai-showroom',{'key':'synthetic-primary'},'https://expected',match_keys=('key',))
    def test_context_mismatch_prevents_mutation(self):
        with patch.object(mod,'oc',return_value='https://different') as oc:
            with self.assertRaisesRegex(RuntimeError,'context'):mod.apply({'kind':'Secret'},'https://expected')
            self.assertEqual(oc.call_count,1)

if __name__=='__main__':unittest.main()
