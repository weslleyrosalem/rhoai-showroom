"""Run inside the OpenShell agent, not through oc exec (which bypasses it)."""
import os,json,stat,ctypes,urllib.request,urllib.error,ssl
result={"uid":os.getuid(),"gid":os.getgid()}
libc=ctypes.CDLL(None,use_errno=True)
class Header(ctypes.Structure):_fields_=[('version',ctypes.c_uint32),('pid',ctypes.c_int)]
class Data(ctypes.Structure):_fields_=[('effective',ctypes.c_uint32),('permitted',ctypes.c_uint32),('inheritable',ctypes.c_uint32)]
h=Header(0x20080522,0);d=(Data*2)();c=libc.capget(ctypes.byref(h),ctypes.byref(d))
result['process_status']={'CapEff':d[0].effective+(d[1].effective<<32) if c==0 else None,'NoNewPrivs':libc.prctl(39,0,0,0,0),'Seccomp':libc.prctl(21,0,0,0,0)}
for key,path,mode in [('allowed_write','/tmp/aurora-allowed','w'),('outside_write','/var/tmp/aurora-denied','w'),('tls_private_key','/etc/openshell-tls/client/tls.key','r'),('service_account_token','/var/run/secrets/openshell/token','r')]:
 try:
  with open(path,mode) as f:
   if mode=='w':f.write('synthetic test')
  result[key]={'allowed':True}
  if mode=='w':os.unlink(path)
 except OSError as e:result[key]={'allowed':False,'errno':e.errno}
try:
 with urllib.request.urlopen('https://example.org',timeout=12) as r:result['external_egress']={'status':r.status}
except Exception as e:result['external_egress']={'error':type(e).__name__,'detail':str(e)[:140]}
body=json.dumps({'model':'aurora-model','messages':[{'role':'user','content':'Reply with the two words: Aurora ready'}],'max_tokens':24}).encode()
try:
 req=urllib.request.Request('https://inference.local/v1/chat/completions',data=body,headers={'Content-Type':'application/json'})
 with urllib.request.urlopen(req,timeout=90) as r:
  data=json.load(r);result['inference']={'http_status':r.status,'model':data.get('model'),'reply':data.get('choices',[{}])[0].get('message',{}).get('content','')[:160]}
except Exception as e:result['inference']={'error':type(e).__name__,'detail':str(e)[:180]}
print(json.dumps(result))
