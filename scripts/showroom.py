#!/usr/bin/env python3
"""Bootstrap and inspect Aurora Supply. Credentials are never printed or committed."""
import argparse, base64, json, os, secrets, subprocess, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]

def oc(*args, data=None):
    p=subprocess.run(['oc',*args,'--request-timeout=60s'],input=data,text=True,capture_output=True)
    if p.returncode:
        # Never echo commands or submitted bodies: they may contain credentials.
        raise RuntimeError('OpenShift operation failed: '+p.stderr[:1200])
    return p.stdout

def guard(server):
    if not server.startswith('https://') or oc('whoami','--show-server').strip()!=server:
        raise RuntimeError('Current oc context differs from --expected-server.')

def get(kind,name=None,namespace=None,optional=False):
    args=['get',kind]+([name] if name else [])+(['-n',namespace] if namespace else [])+['-o','json']
    if optional:args+=['--ignore-not-found']
    raw=oc(*args)
    return json.loads(raw) if raw.strip() else None

def apply(obj,server):
    guard(server)
    oc('apply','--server-side','--field-manager=showroom-bootstrap','-f','-',data=json.dumps(obj))

def secret(name,namespace,values,server):
    existing=get('secret',name,namespace,True)
    if existing:return existing['data']
    obj={'apiVersion':'v1','kind':'Secret','metadata':{'name':name,'namespace':namespace,'labels':{'app.kubernetes.io/part-of':'rhoai-showroom'}},'type':'Opaque','data':{k:base64.b64encode(v.encode()).decode() for k,v in values.items()}}
    apply(obj,server)
    return obj['data']

def preflight(server):
    guard(server)
    versions=get('clusterversions','version')['status']['desired']['version']
    csvs=json.loads(oc('get','csv','-A','-o','json'))['items']
    operators={x['metadata']['name']:x.get('status',{}).get('phase') for x in csvs if not x['metadata'].get('annotations',{}).get('olm.copiedFrom')}
    if operators.get('rhods-operator.3.5.1')!='Succeeded':raise RuntimeError('This release is validated against RHOAI 3.5.1; install/verify it first.')
    required=['llminferenceservices.serving.kserve.io','maassubscriptions.maas.opendatahub.io','mcpserverregistrations.mcp.kuadrant.io','nemoguardrails.trustyai.opendatahub.io','mlflows.mlflow.opendatahub.io','rayjobs.ray.io']
    for crd in required:get('crd',crd)
    print(json.dumps({'ocp':versions,'rhoai':'3.5.1','required_apis':'present','gpu_capacity':'requires separate fresh OCM inventory'},indent=2))

def bootstrap(server):
    preflight(server)
    guard(server);oc('apply','-k',str(ROOT/'gitops/components/foundation'))
    s3data=secret('showroom-s3-credentials','ai-showroom',{'AWS_ACCESS_KEY_ID':'aurora-'+secrets.token_hex(8),'AWS_SECRET_ACCESS_KEY':secrets.token_urlsafe(36)},server)
    values={k:base64.b64decode(v).decode() for k,v in s3data.items()}
    secret('showroom-s3-credentials','redhat-ods-applications',values,server)
    secret('mlflow-artifact-connection','ai-showroom',{**values,'AWS_S3_BUCKET':'aurora-artifacts','AWS_S3_ENDPOINT':'http://showroom-s3.ai-showroom.svc:8333','AWS_DEFAULT_REGION':'us-east-1'},server)
    secret('aurora-pgvector-credentials','ai-showroom',{'POSTGRESQL_USER':'vectoruser','POSTGRESQL_DATABASE':'vectordb','POSTGRESQL_PASSWORD':secrets.token_urlsafe(36)},server)
    password=secrets.token_urlsafe(36)
    secret('aurora-evaldb-credentials','redhat-ods-applications',{'POSTGRESQL_USER':'evalhub','POSTGRESQL_DATABASE':'evalhub','POSTGRESQL_PASSWORD':password,'db-url':f'postgres://evalhub:{password}@aurora-evaldb.redhat-ods-applications.svc:5432/evalhub?sslmode=disable'},server)
    for kind,filename in [('dsc','rhoai-features.json'),('dsci','tracing.json')]:
        items=get(kind)['items']
        if len(items)!=1:raise RuntimeError(f'Expected exactly one {kind}; review existing platform first.')
        current=items[0]
        backup=ROOT/'local/backups'/f'{kind}-before.json';backup.parent.mkdir(parents=True,exist_ok=True)
        if not backup.exists():
            fd=os.open(backup,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
            with os.fdopen(fd,'w') as f:json.dump(current,f,indent=2)
        guard(server);oc('patch',kind,current['metadata']['name'],'--type=merge','--patch-file',str(ROOT/'gitops/bootstrap'/filename))
    dash=get('odhDashboardConfig',namespace='redhat-ods-applications')['items']
    if len(dash)!=1:raise RuntimeError('Expected one OdhDashboardConfig.')
    guard(server);oc('patch','odhDashboardConfig',dash[0]['metadata']['name'],'-n','redhat-ods-applications','--type=merge','-p',json.dumps({'spec':{'dashboardConfig':{'mcpCatalog':True}}}))
    print('Bootstrap complete. Secrets stayed in Kubernetes. Configure MaaS key and MCP audience before public ingress.')

def status(server):
    guard(server)
    for kind in ['deployments','pods','notebooks','datasciencepipelinesapplications','rayjobs']:
        try:
            items=get(kind,namespace='ai-showroom')['items']
            print(json.dumps({'kind':kind,'items':[{'name':x['metadata']['name'],'phase':x.get('status',{}).get('phase'), 'readyReplicas':x.get('status',{}).get('readyReplicas'), 'conditions':[{'type':c.get('type'),'status':c.get('status'),'reason':c.get('reason')} for c in x.get('status',{}).get('conditions',[])]} for x in items]},ensure_ascii=False))
        except RuntimeError as e:print(json.dumps({'kind':kind,'error':str(e)}))

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('action',choices=['preflight','bootstrap','status']);p.add_argument('--expected-server',required=True);a=p.parse_args()
    try:globals()[a.action](a.expected_server)
    except (RuntimeError,KeyError,ValueError) as e:print('BLOCKED: '+str(e),file=sys.stderr);return 2
    return 0
if __name__=='__main__':sys.exit(main())
