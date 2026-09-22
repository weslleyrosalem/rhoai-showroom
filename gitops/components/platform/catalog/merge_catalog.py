#!/usr/bin/env python3
"""Merge one owned catalog entry using an optimistic-concurrency JSON patch.

Default is read-only. Requires PyYAML for the shared sources.yaml document.
Never replaces the ConfigMap or other catalog entries. No restart is performed.
"""
import argparse
import json
from pathlib import Path
import subprocess
import sys


def merge_document(document, entry):
    if not isinstance(document,dict) or not isinstance(document.get('catalogs',[]),list):
        raise ValueError('Unexpected catalog source document shape')
    result = dict(document)
    catalogs = list(result.get('catalogs',[]))
    matches = [i for i,c in enumerate(catalogs) if c.get('id')==entry['id']]
    if len(matches)>1:
        raise ValueError('Duplicate owned catalog id; resolve ambiguity before merging')
    if matches:
        current = catalogs[matches[0]]
        if current.get('name') != entry['name']:
            raise ValueError('Catalog id already belongs to a differently named source')
        catalogs[matches[0]]=entry
    else:
        catalogs.append(entry)
    result['catalogs']=catalogs
    return result


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--expected-server',required=True)
    parser.add_argument('--namespace',default='rhoai-model-registries')
    parser.add_argument('--configmap',default='model-catalog-sources')
    parser.add_argument('--apply',action='store_true')
    args=parser.parse_args()
    try:
        import yaml
        actual=subprocess.check_output(['oc','whoami','--show-server'],text=True).strip()
        if actual!=args.expected_server:
            raise ValueError('oc server differs from expected server')
        cm=json.loads(subprocess.check_output(['oc','get','configmap',args.configmap,'-n',args.namespace,'-o','json','--request-timeout=30s'],text=True))
        raw=cm.get('data',{}).get('sources.yaml')
        if raw is None:
            raise ValueError('Shared ConfigMap has no sources.yaml; do not invent/replace it')
        document=yaml.safe_load(raw) or {}
        entry=json.loads(Path(__file__).with_name('source.json').read_text())
        merged=merge_document(document,entry)
        changed=document!=merged
        result={'status':'PLAN','catalog_id':entry['id'],'included_models':entry['includedModels'],
                'other_sources_preserved':len(document.get('catalogs',[]))-(1 if any(c.get('id')==entry['id'] for c in document.get('catalogs',[])) else 0),'changed':changed}
        if args.apply and changed:
            # JSON Patch test prevents a concurrent dashboard/GitOps edit from
            # being silently overwritten. On conflict, rerun from fresh state.
            patch=[{'op':'test','path':'/metadata/resourceVersion','value':cm['metadata']['resourceVersion']},
                   {'op':'replace','path':'/data/sources.yaml','value':yaml.safe_dump(merged,sort_keys=False,allow_unicode=True)}]
            subprocess.run(['oc','patch','configmap',args.configmap,'-n',args.namespace,
                '--type=json','--patch-file=/dev/stdin','--request-timeout=30s'],input=json.dumps(patch),text=True,check=True,capture_output=True)
            result['status']='APPLIED'
        elif args.apply:
            result['status']='UNCHANGED'
        print(json.dumps(result,indent=2))
        return 0
    except (ImportError,ValueError,KeyError,subprocess.CalledProcessError,OSError) as exc:
        print(json.dumps({'status':'BLOCKED','reason':str(exc)}),file=sys.stderr)
        return 2


if __name__=='__main__':
    sys.exit(main())
