"""Offline controller boundaries; no cluster access, port-forwards, or inference.

Run with: python3 scripts/ahead-llmd/test_workbench_controller.py
The process tests launch only isolated Python sleep fixtures and clean them up.
"""
import datetime as dt
import importlib.util
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import tempfile
import time
import unittest
import uuid

CONTROLLER = Path(__file__).with_name('workbench_controller.py').resolve()
spec = importlib.util.spec_from_file_location('live_controller', CONTROLLER)
controller = importlib.util.module_from_spec(spec)
spec.loader.exec_module(controller)
POSIX_FILES = os.name == 'posix' and hasattr(os, 'O_NOFOLLOW')

# Import the real watchdog but replace the entire benchmark entry point. The
# fixture has no network code: a sessioned leader starts one nested sleeper,
# alongside a regular child representing the independently owned forward.
WORKER_FIXTURE = r'''
import importlib.util,json,os,subprocess,sys,time,types
from pathlib import Path
spec=importlib.util.spec_from_file_location('controller',sys.argv[1])
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
record=Path(sys.argv[2]);cause=sys.argv[3]
fake=types.ModuleType('ahead_llmd')
def main():
    grandfile=record.with_suffix('.grandchild')
    child_code=('import subprocess,sys,time;from pathlib import Path;'
                'p=subprocess.Popen([sys.executable,"-c","import time;time.sleep(60)"]);'
                'Path(sys.argv[1]).write_text(str(p.pid));time.sleep(60)')
    leader=subprocess.Popen([sys.executable,'-c',child_code,str(grandfile)],start_new_session=True)
    while not grandfile.exists():time.sleep(.01)
    forward=subprocess.Popen([sys.executable,'-c','import time;time.sleep(60)'])
    record.write_text(json.dumps({'leader':leader.pid,'forward':forward.pid,
                                 'grandchild':int(grandfile.read_text())}))
    leader.wait()
fake.main=main;sys.modules['ahead_llmd']=fake
parent=-1 if cause=='parent-death' else os.getppid()
# Twenty seconds is the actual worker's reserved shutdown margin. Reaching its
# graceful threshold tests expiry without waiting through a benchmark window.
deadline=time.time()+(20 if cause=='deadline' else 100)
raise SystemExit(module.worker((parent,deadline,[str(record)])))
'''


class RequestValidation(unittest.TestCase):
    def test_exact_schema_canonical_uuid_and_freshness(self):
        current = controller.now()
        identifier = str(uuid.uuid4())
        good = {'id': identifier, 'action': 'compare', 'created_at': current.isoformat()}
        self.assertEqual(controller.request_valid(good, identifier + '.json', current), identifier)
        invalid = [
            dict(good, action='shell'),
            dict(good, command='id'),
            dict(good, id='../escape'),
            dict(good, id='00000000-0000-1000-8000-000000000000'),
            dict(good, created_at=(current - dt.timedelta(seconds=91)).isoformat()),
            dict(good, created_at=(current + dt.timedelta(seconds=1)).isoformat()),
        ]
        for value in invalid:
            with self.subTest(value=value), self.assertRaises(ValueError):
                controller.request_valid(value, identifier + '.json', current)
        with self.assertRaises(ValueError):
            controller.request_valid(good, str(uuid.uuid4()) + '.json', current)


@unittest.skipUnless(POSIX_FILES, 'The controller channel requires POSIX no-follow directory operations')
class FixedFilesystemProtocol(unittest.TestCase):
    def test_claim_cancellation_permissions_and_symlink_boundaries(self):
        with tempfile.TemporaryDirectory() as directory:
            # Resolve platform temporary-directory aliases, then replace only
            # the fixed root literal. Every production filesystem operation is
            # exercised unchanged against this isolated directory.
            root = Path(directory).resolve() / 'channel'
            owner = str(uuid.uuid4())
            root_literal = 'ROOT=' + repr(controller.CHANNEL)
            self.assertEqual(controller.REMOTE.count(root_literal), 1)
            code = controller.REMOTE.replace(root_literal, 'ROOT=' + repr(str(root)))

            def call(operation, expected_success=True, **values):
                packet = dict(op=operation, owner=owner, **values)
                result = subprocess.run(
                    [sys.executable, '-c', code], input=json.dumps(packet),
                    text=True, capture_output=True, timeout=3,
                )
                self.assertEqual(result.returncode == 0, expected_success,
                                 result.stderr if expected_success else '')
                return json.loads(result.stdout) if expected_success else None

            health = {'state': 'READY', 'updated_at': controller.now().isoformat(),
                      'expires_at': (controller.now() + dt.timedelta(minutes=3)).isoformat(),
                      'remaining_runs': 6}
            call('start', value=health)
            call('start', expected_success=False, value=health)
            self.assertEqual(root.stat().st_mode & 0o777, 0o700)
            identifier = str(uuid.uuid4())
            request = {'id': identifier, 'action': 'compare',
                       'created_at': controller.now().isoformat()}
            raw = json.dumps(request)
            request_file = root / 'requests' / (identifier + '.json')
            request_file.write_text(raw)
            self.assertEqual(call('poll')['requests'][0]['raw'], raw)
            call('claim', id=identifier, raw=raw)
            self.assertFalse(request_file.exists())
            call('claim', expected_success=False, id=identifier, raw=raw)

            request_file.symlink_to(root / 'health.json')
            self.assertEqual(call('poll')['requests'], [])
            request_file.unlink()
            request_file.write_text('x' * 1025)
            self.assertEqual(call('poll')['requests'], [])
            (root / 'cancel' / (identifier + '.json')).write_text('{}')
            self.assertTrue(call('cancel', id=identifier, value=health)['cancelled'])

            response = {'id': identifier, 'state': 'CANCELLED', 'result': {'status': 'CANCELLED'}}
            call('response', id=identifier, value=response)
            response_file = root / 'responses' / (identifier + '.json')
            self.assertEqual(response_file.stat().st_mode & 0o777, 0o600)
            self.assertEqual(json.loads(response_file.read_text()), response)
            response_file.unlink()
            response_file.symlink_to(root / 'health.json')
            call('response', expected_success=False, id=identifier, value=response)
            call('stop', value=dict(health, state='STOPPED'))
            self.assertFalse((root / '.controller-lock').exists())


@unittest.skipUnless(os.name == 'posix' and shutil.which('ps'), 'Worker process cleanup requires POSIX and ps')
class WorkerCleanup(unittest.TestCase):
    def test_cancel_parent_loss_and_deadline_clean_owned_processes(self):
        for cause in ('sigterm', 'parent-death', 'deadline'):
            with self.subTest(cause=cause), tempfile.TemporaryDirectory() as directory:
                record = Path(directory) / 'pids.json'
                worker = subprocess.Popen(
                    [sys.executable, '-c', WORKER_FIXTURE, str(CONTROLLER), str(record), cause],
                    stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                )
                pids = {}
                try:
                    limit = time.monotonic() + 4
                    while not record.exists() and worker.poll() is None and time.monotonic() < limit:
                        time.sleep(.01)
                    self.assertTrue(record.exists(), 'Fixture children did not become ready')
                    pids = json.loads(record.read_text())
                    if cause == 'sigterm':
                        worker.terminate()
                    _, error = worker.communicate(timeout=8)
                    self.assertEqual(worker.returncode, 2, error.decode())
                    for pid in pids.values():
                        state = subprocess.run(
                            ['ps', '-o', 'stat=', '-p', str(pid)],
                            capture_output=True, text=True, timeout=2,
                        ).stdout.strip()
                        # An orphan awaiting init's reap is no longer executing.
                        self.assertTrue(not state or state.startswith('Z'), state)
                finally:
                    if worker.poll() is None:
                        worker.terminate()
                        try:
                            worker.wait(timeout=4)
                        except subprocess.TimeoutExpired:
                            worker.kill()
                            worker.wait(timeout=2)
                    # Keep tests harmless even if a cleanup regression is found.
                    if not pids and record.exists():
                        pids = json.loads(record.read_text())
                    if pids:
                        try:
                            os.killpg(pids['leader'], signal.SIGKILL)
                        except ProcessLookupError:
                            pass
                        for name in ('forward', 'grandchild'):
                            try:
                                os.kill(pids[name], signal.SIGKILL)
                            except ProcessLookupError:
                                pass
                    worker.stdout.close()
                    worker.stderr.close()


if __name__ == '__main__':
    unittest.main(verbosity=2)
