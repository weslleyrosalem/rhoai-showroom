#!/usr/bin/env python3
"""Bootstrap and inspect Aurora Supply. Credentials are never printed or committed."""
import argparse, base64, hashlib, json, os, secrets, subprocess, sys, time
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

def secret(name,namespace,values,server,match_keys=()):
    existing=get('secret',name,namespace,True)
    if existing:
        if existing['metadata'].get('labels',{}).get('app.kubernetes.io/part-of')!='rhoai-showroom':
            raise RuntimeError(f'{namespace}/{name} already exists without showroom ownership; inspect before adoption.')
        if not set(values)<=set(existing.get('data',{})):
            raise RuntimeError(f'{namespace}/{name} lacks required credential keys.')
        for key in match_keys:
            if base64.b64decode(existing['data'][key]).decode()!=values[key]:
                raise RuntimeError(f'{namespace}/{name} diverges from the primary S3 connection; reconcile without exposing credentials.')
        return existing['data']
    obj={'apiVersion':'v1','kind':'Secret','metadata':{'name':name,'namespace':namespace,'labels':{'app.kubernetes.io/part-of':'rhoai-showroom'}},'type':'Opaque','data':{k:base64.b64encode(v.encode()).decode() for k,v in values.items()}}
    apply(obj,server)
    return obj['data']

def preflight(server, require_apis=True):
    guard(server)
    versions=get('clusterversions','version')['status']['desired']['version']
    csvs=json.loads(oc('get','csv','-A','-o','json'))['items']
    operators={x['metadata']['name']:x.get('status',{}).get('phase') for x in csvs if not x['metadata'].get('annotations',{}).get('olm.copiedFrom')}
    if operators.get('rhods-operator.3.5.1')!='Succeeded':raise RuntimeError('This release is validated against RHOAI 3.5.1; install/verify it first.')
    required=['llminferenceservices.serving.kserve.io','maassubscriptions.maas.opendatahub.io','mcpserverregistrations.mcp.kuadrant.io','nemoguardrails.trustyai.opendatahub.io','mlflows.mlflow.opendatahub.io','rayjobs.ray.io','evalhubs.trustyai.opendatahub.io','ogxservers.ogx.io','mcpservers.mcp.x-k8s.io','adminnetworkpolicies.policy.networking.k8s.io','modelregistries.modelregistry.opendatahub.io','notebooks.kubeflow.org','datasciencepipelinesapplications.datasciencepipelinesapplications.opendatahub.io']
    missing=[crd for crd in required if not get('crd',crd,optional=True)]
    if require_apis and missing:raise RuntimeError('Required APIs not yet available: '+', '.join(missing)+'. Bootstrap enables its DSC components; install the other prerequisite operators first.')
    print(json.dumps({'ocp':versions,'rhoai':'3.5.1','required_apis':'present' if not missing else 'pending feature enablement','missing_apis':missing,'gpu_capacity':'requires separate fresh OCM inventory'},indent=2))
    return required

def check_shared(current, patch, kind, allow_changes=False):
    if allow_changes:return
    if kind=='dsc':
        old=current.get('spec',{}).get('components',{}).get('trustyai',{}).get('mcpGuardrailsMode')
        new=patch['spec']['components']['trustyai']['mcpGuardrailsMode']
        if old is not None and old!=new:
            raise RuntimeError('Existing TrustyAI mcpGuardrailsMode differs. Review shared consumers and use --allow-shared-changes only when intentionally adopting this configuration.')
    if kind=='dsci':
        old=current.get('spec',{}).get('monitoring',{}).get('traces',{}) or {}
        new=patch['spec']['monitoring']['traces']
        checks=[('sampleRatio',old.get('sampleRatio'),new.get('sampleRatio'))]
        checks += [('storage.'+key,(old.get('storage') or {}).get(key),value) for key,value in new.get('storage',{}).items()]
        if any(previous is not None and previous!=wanted for _,previous,wanted in checks):
            raise RuntimeError('Existing shared tracing configuration differs. Review storage, retention, and sampling before using --allow-shared-changes.')

def wait_for_apis(required, server, timeout=180):
    deadline=time.monotonic()+timeout
    while True:
        guard(server)
        missing=[name for name in required if not get('crd',name,optional=True)]
        if not missing:return
        if time.monotonic()>=deadline:raise RuntimeError('Feature APIs still unavailable after enablement: '+', '.join(missing))
        time.sleep(3)

def bootstrap(server, allow_shared_changes=False):
    required=preflight(server, require_apis=False)
    shared=[]
    for kind,filename in [('dsc','rhoai-features.json'),('dsci','tracing.json')]:
        items=get(kind)['items']
        if len(items)!=1:raise RuntimeError(f'Expected exactly one {kind}; review existing platform first.')
        current=items[0]
        patch=json.loads((ROOT/'gitops/bootstrap'/filename).read_text())
        check_shared(current,patch,kind,allow_shared_changes)
        shared.append((kind,filename,current))
    guard(server);oc('apply','-k',str(ROOT/'gitops/components/foundation'))
    secret('showroom-web-cookie','ai-showroom',{'cookie-secret':secrets.token_urlsafe(24)},server)
    s3data=secret('showroom-s3-credentials','ai-showroom',{'AWS_ACCESS_KEY_ID':'aurora-'+secrets.token_hex(8),'AWS_SECRET_ACCESS_KEY':secrets.token_urlsafe(36),'AWS_S3_ENDPOINT':'http://showroom-s3.ai-showroom.svc.cluster.local:8333','AWS_DEFAULT_REGION':'us-east-1'},server,match_keys=('AWS_S3_ENDPOINT','AWS_DEFAULT_REGION'))
    values={k:base64.b64decode(v).decode() for k,v in s3data.items()}
    secret('showroom-s3-credentials','redhat-ods-applications',values,server,match_keys=tuple(values))
    secret('mlflow-artifact-connection','ai-showroom',{**values,'AWS_S3_BUCKET':'aurora-artifacts','AWS_S3_ENDPOINT':'http://showroom-s3.ai-showroom.svc.cluster.local:8333','AWS_DEFAULT_REGION':'us-east-1'},server,match_keys=tuple(values))
    secret('aurora-pgvector-credentials','ai-showroom',{'POSTGRESQL_USER':'vectoruser','POSTGRESQL_DATABASE':'vectordb','POSTGRESQL_PASSWORD':secrets.token_urlsafe(36)},server)
    # This internal connection uses network isolation; the placeholder is not an authentication credential.
    secret('aurora-ogx-connection','ai-showroom',{'OGX_CLIENT_BASE_URL':'http://lsd-genai-playground-service.ai-showroom.svc:8321','OGX_CLIENT_API_KEY':'internal-demo-no-external-access'},server,match_keys=('OGX_CLIENT_BASE_URL',))
    password=secrets.token_urlsafe(36)
    secret('aurora-evaldb-credentials','redhat-ods-applications',{'POSTGRESQL_USER':'evalhub','POSTGRESQL_DATABASE':'evalhub','POSTGRESQL_PASSWORD':password,'db-url':f'postgres://evalhub:{password}@aurora-evaldb.redhat-ods-applications.svc:5432/evalhub?sslmode=disable'},server)
    for kind,filename,current in shared:
        cluster_key=hashlib.sha256(server.encode()).hexdigest()[:16]
        backup=ROOT/'local/backups'/cluster_key/f"{kind}-{current['metadata']['uid']}-before.json";backup.parent.mkdir(parents=True,exist_ok=True)
        if not backup.exists():
            fd=os.open(backup,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
            with os.fdopen(fd,'w') as f:json.dump(current,f,indent=2)
        guard(server);oc('patch',kind,current['metadata']['name'],'--type=merge','--patch-file',str(ROOT/'gitops/bootstrap'/filename))
    dash=get('odhDashboardConfig',namespace='redhat-ods-applications')['items']
    if len(dash)!=1:raise RuntimeError('Expected one OdhDashboardConfig.')
    guard(server);oc('patch','odhDashboardConfig',dash[0]['metadata']['name'],'-n','redhat-ods-applications','--type=merge','--patch-file',str(ROOT/'gitops/bootstrap/dashboard-features.json'))
    wait_for_apis(required,server)
    print('Bootstrap complete. Secrets stayed in Kubernetes. Configure MaaS key and MCP audience before public ingress.')

def status(server):
    guard(server)
    for kind in ['deployments','pods','notebooks','datasciencepipelinesapplications','rayjobs']:
        try:
            items=get(kind,namespace='ai-showroom')['items']
            print(json.dumps({'kind':kind,'items':[{'name':x['metadata']['name'],'phase':x.get('status',{}).get('phase'), 'readyReplicas':x.get('status',{}).get('readyReplicas'), 'conditions':[{'type':c.get('type'),'status':c.get('status'),'reason':c.get('reason')} for c in x.get('status',{}).get('conditions',[])]} for x in items]},ensure_ascii=False))
        except RuntimeError as e:print(json.dumps({'kind':kind,'error':str(e)}))

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('action',choices=['preflight','bootstrap','status']);p.add_argument('--expected-server',required=True);p.add_argument('--allow-shared-changes',action='store_true',help='Explicitly adopt different shared TrustyAI/tracing settings after reviewing current consumers.');a=p.parse_args()
    try:
        if a.action=='bootstrap':bootstrap(a.expected_server,a.allow_shared_changes)
        else:globals()[a.action](a.expected_server)
    except (RuntimeError,KeyError,ValueError) as e:print('BLOCKED: '+str(e),file=sys.stderr);return 2
    return 0
if __name__=='__main__':sys.exit(main())
