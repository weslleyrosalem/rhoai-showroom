#!/usr/bin/env python3
"""Bounded AHEAD MaaS rehearsal. Discover endpoints, validate TLS, hide/revoke keys."""
import argparse,json,subprocess,sys,time,urllib.error,urllib.parse,urllib.request

class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode',choices=['status','smoke','quota'])
    parser.add_argument('--expected-server',required=True)
    parser.add_argument('--expected-user',default='aiadmin')
    parser.add_argument('--recover',action='store_true',help='For quota: verify free-tier recovery after 65 seconds')
    args=parser.parse_args()
    def oc(*parts):
        return subprocess.check_output(['oc','--request-timeout=30s',*parts],text=True,timeout=40).strip()
    def get(kind,name,namespace):
        return json.loads(oc('get',kind,name,'-n',namespace,'-o','json'))
    if oc('whoami','--show-server')!=args.expected_server or oc('whoami')!=args.expected_user:
        raise SystemExit('Unexpected cluster or identity. No changes made.')
    gateway=get('gateway','ahead','openshift-ingress')
    listener=next(x for x in gateway['spec']['listeners'] if x['protocol']=='HTTPS')
    host=listener['hostname'];parsed=urllib.parse.urlsplit('https://'+host)
    if not parsed.hostname or parsed.netloc!=host or parsed.username or parsed.password or '*' in host:
        raise SystemExit('Gateway must have one explicit HTTPS hostname.')
    base='https://'+host
    model=get('maasmodelref','ahead-simulator','ahead')['status']['resolvedModelAlias']
    opener=urllib.request.build_opener(NoRedirect)
    def request(path,token=None,body=None,method=None):
        headers={'Content-Type':'application/json'}
        if token:headers['Authorization']='Bearer '+token
        req=urllib.request.Request(base+path,headers=headers,method=method,
            data=None if body is None else json.dumps(body).encode())
        try:
            with opener.open(req,timeout=30) as response:
                code=response.status;raw=response.read(1024*1024)
        except urllib.error.HTTPError as error:
            code=error.code;raw=error.read(1024*1024)
        try:body=json.loads(raw)
        except ValueError:body={}
        return code,body
    records=[];temporary_ids=[];identity=None
    def record(name,passed,**fields):
        result={'test':name,'passed':passed,**fields};records.append(result)
        print(json.dumps(result),flush=True)
    def key(subscription):
        status,value=request('/maas-api/v1/api-keys',identity,
            {'name':'ahead-bounded-rehearsal','expiresIn':'10m','subscription':subscription})
        if status!=201 or not value.get('key') or not value.get('id'):
            raise RuntimeError('API key creation failed: HTTP '+str(status))
        temporary_ids.append(value['id']);return value['key']
    def infer(token,prompt='Hello',max_tokens=1):
        return request('/v1/chat/completions',token,{'model':model,'max_tokens':max_tokens,
            'messages':[{'role':'user','content':prompt}]})
    try:
        for kind,name,namespace in [('aitenant','ahead','ai-tenants'),
                                  ('llminferenceservice','ahead-simulator','ahead'),
                                  ('maasmodelref','ahead-simulator','ahead'),
                                  ('keycloak','keycloak','ahead')]:
            obj=get(kind,name,namespace)
            ready=any(c.get('type')=='Ready' and c.get('status')=='True'
                      for c in obj.get('status',{}).get('conditions',[]))
            record(kind+'/'+name,ready)
        c,_=request('/maas-api/health');record('gateway-health',c==200,http=c)
        if args.mode!='status':
            identity=oc('whoami','-t');premium=key('ahead-simulator-premium')
            for name,token,expected in [('anonymous',None,401),('invalid','invalid-ahead-rehearsal',401),('premium',premium,200)]:
                c,value=infer(token);record(name,c==expected,http=c,usage=value.get('usage'))
            if args.mode=='quota':
                free=key('ahead-simulator-free');statuses=[];usage=0
                for _ in range(16):
                    c,value=infer(free,' AHEAD'*35);statuses.append(c)
                    usage+=value.get('usage',{}).get('total_tokens',0)
                    if c==429:break
                    if c!=200:break
                record('free-quota',429 in statuses,statuses=statuses,observedTokens=usage)
                c,_=infer(premium);record('premium-isolation',c==200,http=c)
                if args.recover:
                    time.sleep(35);time.sleep(30)
                    c,_=infer(free);record('free-recovery',c==200,http=c)
    finally:
        for id in temporary_ids:
            c,_=request('/maas-api/v1/api-keys/'+id,identity,method='DELETE')
            record('temporary-key-revocation',c in (200,204),http=c)
    if not all(x['passed'] for x in records):raise SystemExit(1)

if __name__=='__main__':main()
