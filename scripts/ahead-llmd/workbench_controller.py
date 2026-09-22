#!/usr/bin/env python3
"""Administrator-side bounded notebook channel; never exposes cluster credentials.

Only a fresh UUID compare request is accepted. Benchmark configuration is fixed.
Run cancellation gets graceful AHEAD cleanup, followed by tracked-child cleanup.
"""
import argparse
import datetime as dt
import json
import os
from pathlib import Path
import re
import signal
import subprocess
import sys
import threading
import time
import uuid

HERE = Path(__file__).resolve().parent
PUBLIC_ROOT = HERE.parents[1]
CHANNEL = '/opt/app-root/src/.local/share/aurora-showroom/llmd-live'
MAX_RUNS, COOLDOWN, WALL_SECONDS = 6, 30, 180
UUID4 = re.compile(r'[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}')

# Every directory component is opened without following symlinks. Values from
# the Workbench select no commands, paths, endpoints, models, or workload sizes.
REMOTE = r'''
import datetime as dt,json,os,re,stat,sys,uuid
ROOT='/opt/app-root/src/.local/share/aurora-showroom/llmd-live'
packet=json.loads(sys.stdin.buffer.read(131073))
if len(json.dumps(packet))>131072: raise ValueError('Packet too large')
def directory(path):
 fd=os.open('/',os.O_RDONLY|os.O_DIRECTORY)
 for part in path.strip('/').split('/'):
  try: os.mkdir(part,0o700,dir_fd=fd)
  except FileExistsError: pass
  child=os.open(part,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW,dir_fd=fd);os.close(fd);fd=child
 return fd
root=directory(ROOT)
os.fchmod(root,0o700)
def sub(name):
 if name not in ('requests','responses','cancel'):raise ValueError('Invalid directory')
 try:os.mkdir(name,0o700,dir_fd=root)
 except FileExistsError:pass
 fd=os.open(name,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW,dir_fd=root);os.fchmod(fd,0o700);return fd
def ident(value):
 if not isinstance(value,str) or not re.fullmatch(r'[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}',value):raise ValueError('Invalid ID')
 return value
def read(fd,name,limit):
 f=os.open(name,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK,dir_fd=fd)
 try:
  st=os.fstat(f)
  if not stat.S_ISREG(st.st_mode) or st.st_size>limit:raise ValueError('Invalid file')
  data=os.read(f,limit+1)
  if len(data)>limit:raise ValueError('Oversized file')
  return data
 finally:os.close(f)
def write(fd,name,value):
 try:
  if not stat.S_ISREG(os.stat(name,dir_fd=fd,follow_symlinks=False).st_mode):raise ValueError('Invalid target')
 except FileNotFoundError:pass
 temp='.tmp-'+uuid.uuid4().hex
 f=os.open(temp,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600,dir_fd=fd)
 try:
  with os.fdopen(f,'w') as stream:json.dump(value,stream,allow_nan=False);stream.flush();os.fsync(stream.fileno())
  os.rename(temp,name,src_dir_fd=fd,dst_dir_fd=fd)
 finally:
  try:os.unlink(temp,dir_fd=fd)
  except FileNotFoundError:pass
op=packet['op'];result={}
if op=='start':
 for name in ('requests','responses','cancel'):os.close(sub(name))
 lock=os.open('.controller-lock',os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600,dir_fd=root)
 with os.fdopen(lock,'w') as f:json.dump({'owner':packet['owner']},f)
else:
 owner=json.loads(read(root,'.controller-lock',1024))['owner']
 if owner!=packet['owner']:raise ValueError('Controller ownership mismatch')
if op in ('health','start'):write(root,'health.json',packet['value'])
elif op=='poll':
 fd=sub('requests');found=[]
 for name in sorted(os.listdir(fd))[:64]:
  if name.endswith('.json') and re.fullmatch(r'[0-9a-f-]{36}\.json',name):
   try:
    ident(name[:-5]);raw=read(fd,name,1024);found.append({'filename':name,'raw':raw.decode('utf-8')})
   except (ValueError,OSError,UnicodeError):continue
 result={'requests':found};os.close(fd)
elif op=='claim':
 name=ident(packet['id'])+'.json';fd=sub('requests')
 raw=read(fd,name,1024).decode('utf-8')
 if raw!=packet['raw']:raise ValueError('Request changed during claim')
 os.unlink(name,dir_fd=fd);os.close(fd)
 result={'claimed':True}
elif op=='cancel':
 fd=sub('cancel');name=ident(packet['id'])+'.json'
 try:read(fd,name,1024);result={'cancelled':True}
 except FileNotFoundError:result={'cancelled':False}
 os.close(fd)
 write(root,'health.json',packet['value'])
elif op=='response':
 fd=sub('responses');write(fd,ident(packet['id'])+'.json',packet['value']);os.close(fd)
elif op=='stop':
 write(root,'health.json',packet['value']);os.unlink('.controller-lock',dir_fd=root)
else:raise ValueError('Invalid operation')
os.close(root);print(json.dumps(result,allow_nan=False))
'''


def now():
    return dt.datetime.now(dt.timezone.utc)


def parsed_time(value):
    if not isinstance(value, str):
        raise ValueError('Expected timestamp')
    parsed = dt.datetime.fromisoformat(value.replace('Z', '+00:00'))
    if parsed.tzinfo is None:
        raise ValueError('Timestamp needs timezone')
    return parsed.astimezone(dt.timezone.utc)


def request_valid(value, filename, current):
    if not isinstance(value, dict) or set(value) != {'id', 'action', 'created_at'}:
        raise ValueError('Request schema rejected')
    identifier = value['id']
    if not isinstance(identifier, str) or not UUID4.fullmatch(identifier) or filename != identifier + '.json':
        raise ValueError('Canonical UUID4 required')
    if value['action'] != 'compare' or not 0 <= (current - parsed_time(value['created_at'])).total_seconds() <= 90:
        raise ValueError('Request action or freshness rejected')
    return identifier


def atomic(path, value):
    temp = path.with_name('.tmp-' + uuid.uuid4().hex)
    descriptor = os.open(temp, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    try:
        with os.fdopen(descriptor, 'w') as stream:
            json.dump(value, stream, indent=2, allow_nan=False)
            stream.write('\n'); stream.flush(); os.fsync(stream.fileno())
        os.replace(temp, path)
    finally:
        temp.unlink(missing_ok=True)


def oc(*args):
    result = subprocess.run(['oc', '--request-timeout=10s', *args], capture_output=True, timeout=15)
    if result.returncode:
        raise RuntimeError('OpenShift operation failed; access details suppressed')
    return result.stdout


def channel(owner, op, **values):
    payload = json.dumps(dict(op=op, owner=owner, **values)).encode()
    result = subprocess.run(['oc', '--request-timeout=3s', 'exec', '-i', '-n', 'ai-showroom',
                             'aurora-lab-0', '-c', 'aurora-lab', '--', 'python3', '-c', REMOTE],
                            input=payload, capture_output=True, timeout=4)
    if result.returncode:
        raise RuntimeError('Workbench channel rejected an operation; details suppressed')
    return json.loads(result.stdout)


def worker(arguments):
    """A watchdog outlives the controller; track sessioned GuideLLM explicitly."""
    import ahead_llmd
    parent, deadline, ahead_args = arguments
    children, lock, stopped = [], threading.Lock(), threading.Event()
    original = subprocess.Popen
    stopping = False

    def tracked(*args, **kwargs):
        process = original(*args, **kwargs)
        with lock:
            children.append((process, bool(kwargs.get('start_new_session'))))
        return process

    def terminate(signum, frame):
        nonlocal stopping
        if not stopping:
            stopping = True
            raise KeyboardInterrupt

    def kill_children(sig):
        with lock:
            snapshot = list(children)
        for process, session in reversed(snapshot):
            # A session leader can exit while its workers survive: still signal
            # its owned process group. Never signal an unrelated parent group.
            try:
                if session:
                    os.killpg(process.pid, sig)
                elif process.poll() is None:
                    process.send_signal(sig)
            except ProcessLookupError:
                pass

    def watchdog():
        sent = None
        while not stopped.wait(.5):
            if sent is None and (os.getppid() != parent or time.time() >= deadline - 20):
                sent = time.monotonic(); os.kill(os.getpid(), signal.SIGTERM)
            if stopping and sent is None:
                sent = time.monotonic()
            if sent is not None and time.monotonic() - sent > 12:
                kill_children(signal.SIGTERM)
            if (sent is not None and time.monotonic() - sent > 17) or time.time() >= deadline:
                kill_children(signal.SIGKILL)
                os._exit(124)

    subprocess.Popen = tracked
    signal.signal(signal.SIGTERM, terminate)
    signal.signal(signal.SIGINT, terminate)
    threading.Thread(target=watchdog, daemon=True).start()
    sys.argv = ['ahead_llmd.py', *ahead_args]
    try:
        return ahead_llmd.main()
    except BaseException:
        # Do not print an exception, credential, raw path, or upstream body.
        return 2
    finally:
        kill_children(signal.SIGTERM)
        until = time.monotonic() + 2
        while time.monotonic() < until:
            with lock:
                alive = [p for p, _ in children if p.poll() is None]
            if not alive:
                break
            time.sleep(.1)
        kill_children(signal.SIGKILL)
        with lock:
            for process, _ in children:
                try: process.wait(timeout=.2)
                except subprocess.TimeoutExpired: pass
        stopped.set()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--expected-server', required=True)
    parser.add_argument('--expected-user', required=True)
    parser.add_argument('--guidellm', type=Path, required=True)
    parser.add_argument('--tokenizer', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--expires-at', default='2026-09-22T16:30:00Z')
    parser.add_argument('--max-runs', type=int, choices=range(1, 7), default=6)
    args = parser.parse_args()
    expiry = parsed_time(args.expires_at)
    if not 0 < (expiry - now()).total_seconds() <= 10800:
        raise ValueError('Expiry must be in the future and within three hours')
    if oc('whoami', '--show-server').decode().strip() != args.expected_server or oc('whoami').decode().strip() != args.expected_user:
        raise ValueError('Unexpected cluster or identity')
    from ahead_llmd import private_output_path
    from summarize_ahead_llmd import summarize
    output = private_output_path(args.output)
    os.umask(0o077); output.mkdir(parents=True, mode=0o700)
    owner = str(uuid.uuid4()); completed = {}; active = None; started = False; last_finish = 0
    def health(state):
        return {'state': state, 'updated_at': now().isoformat(), 'expires_at': expiry.isoformat(),
                'remaining_runs': max(0, args.max_runs-len(completed))}
    def response(identifier, state, created, begun, result=None):
        value = {'id': identifier, 'state': state, 'created_at': created, 'started_at': begun,
                 'updated_at': now().isoformat(), 'result': result}
        channel(owner, 'response', id=identifier, value=value)
    def stop_signal(signum, frame):
        raise KeyboardInterrupt
    signal.signal(signal.SIGTERM, stop_signal); signal.signal(signal.SIGINT, stop_signal)
    try:
        channel(owner, 'start', value=health('READY')); started = True
        while now() < expiry and len(completed) < args.max_runs:
            channel(owner, 'health', value=health('READY'))
            if time.monotonic()-last_finish < COOLDOWN:
                time.sleep(5); continue
            found = channel(owner, 'poll')['requests']; selected = None
            for item in found:
                try:
                    value = json.loads(item['raw']); identifier = request_valid(value, item['filename'], now())
                    if identifier in completed:
                        continue
                except (ValueError, TypeError, KeyError, json.JSONDecodeError):
                    continue
                selected = (value, item); break
            if selected is None:
                time.sleep(5); continue
            value, item = selected; identifier = value['id']; begun = now().isoformat()
            channel(owner, 'claim', id=identifier, raw=item['raw'])
            completed[identifier] = {'state': 'RUNNING', 'started_at': begun}
            atomic(output/'ledger.json', completed)
            response(identifier, 'RUNNING', value['created_at'], begun)
            channel(owner, 'health', value=health('RUNNING'))
            run_output = output/identifier
            deadline = min(expiry.timestamp(), time.time()+WALL_SECONDS)
            ahead_args = ['--expected-server', args.expected_server, '--expected-user', args.expected_user,
                          '--guidellm', str(args.guidellm.resolve()), '--tokenizer', str(args.tokenizer.resolve()),
                          '--output', str(run_output), '--seconds', '30', '--requests', '16',
                          '--modes', 'round-robin', 'llmd']
            # Administrator identity remains local; the Workbench receives no
            # token, kubeconfig, subprocess arguments, or access-detail logs.
            with (output/(identifier+'.log')).open('w') as log:
                active = subprocess.Popen([sys.executable, str(Path(__file__).resolve()), '_worker'],
                    stdin=subprocess.PIPE, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
                active.stdin.write(json.dumps([os.getpid(), deadline, ahead_args]).encode()); active.stdin.close()
                cancelled = False
                while active.poll() is None:
                    cancellation = channel(owner, 'cancel', id=identifier, value=health('RUNNING'))['cancelled']
                    if cancellation or time.time() >= deadline-20:
                        cancelled = True; active.terminate(); break
                    time.sleep(5)
                if active.poll() is None:
                    try: active.wait(timeout=20)
                    except subprocess.TimeoutExpired:
                        # Worker watchdog has already cleaned tracked children
                        # by its absolute deadline. Never kill its group blindly.
                        active.wait(timeout=5)
                code = active.returncode; active = None
            result, state = None, 'FAILED'
            if code == 0 and not cancelled:
                try:
                    result = summarize(run_output)
                    if {run['mode'] for run in result['runs']} != {'round-robin', 'llmd'}:
                        raise ValueError('Unexpected result modes')
                    if any(not 1 <= run['requests']['successful'] <= 16 for run in result['runs']):
                        raise ValueError('Result exceeds the fixed request cap')
                    if not parsed_time(begun) <= parsed_time(result['started_at']) <= parsed_time(result['finished_at']) <= now():
                        raise ValueError('Result timestamps do not match this run')
                    state = 'COMPLETE'
                    atomic(output/(identifier+'-summary.json'), result)
                except (ValueError, KeyError, OSError, TypeError):
                    pass
            if result is None:
                if cancelled:
                    state = 'CANCELLED'
                result = {'status': 'CANCELLED' if cancelled else 'FAILED',
                          'message': 'No complete comparison. Partial private artifacts are retained by the administrator.'}
            completed[identifier] = {'state': state, 'started_at': begun, 'finished_at': now().isoformat()}
            atomic(output/'ledger.json', completed)
            response(identifier, state, value['created_at'], begun, result)
            last_finish = time.monotonic()
        return 0
    finally:
        if active is not None and active.poll() is None:
            active.terminate()
            try: active.wait(timeout=23)
            except subprocess.TimeoutExpired: pass  # Worker parent-death/expiry watchdog remains authoritative.
        if started:
            try: channel(owner, 'stop', value=health('STOPPED'))
            except Exception: pass


if __name__ == '__main__':
    if sys.argv[1:] == ['_worker']:
        sys.exit(worker(json.loads(sys.stdin.buffer.read(65537))))
    try:
        sys.exit(main())
    except (Exception, KeyboardInterrupt) as error:
        print('Controller stopped: '+type(error).__name__+'; private artifacts retained.', file=sys.stderr)
        sys.exit(2)
