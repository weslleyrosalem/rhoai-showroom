#!/usr/bin/env python3
"""Read-only model admission prerequisites. Does not create resources or claim runtime validation."""
import argparse
import importlib.util
import json
from pathlib import Path
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[3]
spec=importlib.util.spec_from_file_location('capacity',ROOT/'scripts/capacity.py')
capacity=importlib.util.module_from_spec(spec);spec.loader.exec_module(capacity)


def get(resource):
    return json.loads(subprocess.check_output(['oc','get',resource,'-A','-o','json','--request-timeout=30s'],text=True))


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--model',required=True,choices=['qwen-4b','qwen-32b-tp4','qwen-32b-multinode','qwen-72b-opt-in','qwen-06b-mig-h100'])
    p.add_argument('--profile',required=True,choices=['interactive','active-l40s-9','mig-h100-single','full-l40s-13','mig-13'])
    p.add_argument('--inventory',type=Path,required=True)
    p.add_argument('--expected-server',required=True)
    args=p.parse_args()
    try:
        actual=subprocess.check_output(['oc','whoami','--show-server'],text=True).strip()
        if actual!=args.expected_server:raise ValueError('Unexpected oc server')
        nodes=get('nodes');pods=get('pods')
        profile=json.loads((ROOT/'gitops/profiles'/args.profile/'capacity.json').read_text())
        result=capacity.assess(profile,nodes,json.loads(args.inventory.read_text()),expected_server=args.expected_server)
        problems=list(result['reasons'])
        model=json.loads((Path(__file__).parent/args.model/'model.yaml').read_text())
        required=int(model['spec']['template']['containers'][0]['resources']['requests']['nvidia.com/gpu'])
        replicas=model['spec']['replicas']
        allocated={}
        for pod in pods['items']:
            if pod.get('status',{}).get('phase') in ('Succeeded','Failed'):continue
            name=pod.get('spec',{}).get('nodeName')
            if not name:continue
            regular=sum(int(c.get('resources',{}).get('requests',{}).get('nvidia.com/gpu',0)) for c in pod['spec'].get('containers',[]))
            init=max([int(c.get('resources',{}).get('requests',{}).get('nvidia.com/gpu',0)) for c in pod['spec'].get('initContainers',[])]+[0])
            allocated[name]=allocated.get(name,0)+max(regular,init)
        free=[]
        for node in nodes['items']:
            labels=node['metadata'].get('labels',{})
            if any(labels.get(k)!=v for k,v in model['spec']['template'].get('nodeSelector',{}).items()):continue
            if node['spec'].get('unschedulable'):continue
            if not any(c['type']=='Ready' and c['status']=='True' for c in node['status'].get('conditions',[])):continue
            amount=int(node['status'].get('allocatable',{}).get('nvidia.com/gpu',0))-allocated.get(node['metadata']['name'],0)
            free.append(amount)
        separate_nodes=bool(model['spec']['template'].get('affinity',{}).get('podAntiAffinity',{}).get('requiredDuringSchedulingIgnoredDuringExecution'))
        if replicas>1 and separate_nodes:
            fit=sum(1 for value in free if value>=required)
        else:
            fit=sum(value//required for value in free)
        if fit<replicas:
            problems.append(f'Need {replicas} ready placement(s) with {required} free matching GPU resources each; found {fit}. Distinct nodes required: {separate_nodes}.')
        result.update(status='BLOCKED' if problems else 'PASS_CAPACITY_ONLY',reasons=problems,
                      model=args.model,required_replicas=replicas,gpus_per_replica=required,
                      runtime_validation='NOT_RUN',next_step='Server dry-run, review/apply, then verify image pull, Ready, exact model revision, MaaS and inference.')
        print(json.dumps(result,indent=2))
        return 2 if problems else 0
    except (ValueError,KeyError,OSError,subprocess.CalledProcessError) as exc:
        print(json.dumps({'status':'BLOCKED','reason':str(exc)}));return 2


if __name__=='__main__':sys.exit(main())
