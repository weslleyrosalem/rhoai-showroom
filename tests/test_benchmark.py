import copy
import importlib.util
import json
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('benchmark',ROOT/'scripts/benchmark.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)

def event(data):return 'data: '+json.dumps(data)+'\n'

def run_fixture():
    meta={'model_revision':'a'*40,'tokenizer_revision':'a'*40,'dtype':'bfloat16',
        'gpu_product':'L40S','gpu_count':1,'node_count':1,'max_model_len':8192,
        'chat_template_sha256':'b'*64,'cache_mode':'off','tensor_parallel':1,
        'pipeline_parallel':1,'data_parallel':1,'engine':'vllm',
        'image_digest':'registry/image@sha256:'+'c'*64,'scheduling':'single-device'}
    config={'requests':10,'concurrency':1,'max_tokens':64,'prefix_mode':'repeated-prefix',
        'temperature':0,'seed':42,'enable_thinking':False,'warmup':2,'workload_sha256':'d'*64}
    return {'status':'MEASURED','metadata':meta,'config':config,'summary':{'output_tokens_per_second':10}}

class BenchmarkTests(unittest.TestCase):
    def test_first_role_chunk_is_not_a_token(self):
        lines=[event({'choices':[{'delta':{'role':'assistant'}}]}),event({'choices':[{'delta':{'content':'hello'}}]}),event({'usage':{'completion_tokens':2,'prompt_tokens':3,'total_tokens':5},'choices':[]}),'data: [DONE]\n']
        r=m.parse_sse(lines,10,clock=lambda:10.25)
        self.assertEqual(r['ttft_ms'],250)
        self.assertEqual(r['completion_tokens'],2)
    def test_missing_done_is_an_error(self):
        with self.assertRaises(ValueError):m.parse_sse([event({'choices':[{'delta':{'content':'hello'}}]})],0)
    def test_missing_usage_does_not_invent_tokens(self):
        rows=[{'ok':True,'latency_ms':5,'ttft_ms':2,'completion_tokens':None}]
        r=m.summarize(rows,1)
        self.assertIsNone(r['output_tokens_per_second'])
        self.assertFalse(r['usage_complete'])
    def test_error_stream_is_not_success(self):
        with self.assertRaises(ValueError):m.parse_sse([event({'error':{'message':'failure'}})],0)
    def test_invalid_usage_rejected(self):
        lines=[event({'choices':[{'delta':{'content':'a'}}],'usage':{'completion_tokens':'100'}}),'data: [DONE]']
        with self.assertRaises(ValueError):m.parse_sse(lines,0)
    def test_different_gpu_count_rejects_speedup_claim(self):
        a=run_fixture();b=copy.deepcopy(a);b['metadata']['gpu_count']=2
        self.assertEqual(m.compare_results(a,b,'routing')['status'],'BLOCKED')
    def test_different_model_revision_rejected(self):
        a=run_fixture();b=copy.deepcopy(a);b['metadata']['model_revision']='f'*40
        self.assertEqual(m.compare_results(a,b,'engine')['status'],'BLOCKED')
    def test_different_precision_rejected(self):
        a=run_fixture();b=copy.deepcopy(a);b['metadata']['dtype']='float16'
        self.assertEqual(m.compare_results(a,b,'engine')['status'],'BLOCKED')
    def test_routing_requires_same_engine_image(self):
        a=run_fixture();b=copy.deepcopy(a);b['metadata']['image_digest']='other@sha256:'+'c'*64
        self.assertEqual(m.compare_results(a,b,'routing')['status'],'BLOCKED')
    def test_ratio_only_from_measured_comparable_results(self):
        a=run_fixture();b=copy.deepcopy(a);b['summary']['output_tokens_per_second']=20
        r=m.compare_results(a,b,'routing');self.assertEqual(r['b_over_a_output_tokens_per_second'],2)
    def test_failed_run_never_claims_comparable(self):
        a=run_fixture();b=copy.deepcopy(a);b['status']='FAILED'
        self.assertEqual(m.compare_results(a,b,'routing')['status'],'BLOCKED')
    def test_repeated_prefix_workload_is_reproducible(self):
        self.assertEqual(m.messages(1)[0],m.messages(2)[0])
        self.assertNotEqual(m.messages(1,'distinct-prefix')[0],m.messages(2,'distinct-prefix')[0])
        self.assertEqual(m.messages(1),m.messages(1))
    def test_metadata_requires_pins(self):
        meta=run_fixture()['metadata'];meta['model_revision']='main'
        with self.assertRaises(ValueError):m.validate_metadata(meta)

if __name__=='__main__':unittest.main()
