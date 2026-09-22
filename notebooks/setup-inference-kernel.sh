#!/usr/bin/env bash
# Prepare a persistent, separate Workbench kernel. This never starts inference.
set -euo pipefail

python3 - <<'PY'
import datetime as dt
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import urllib.request
import venv

ROOT = Path('/opt/app-root/src')
VENV = ROOT / '.venvs/aurora-inference'
TOKENIZER = ROOT / '.cache/aurora-qwen-tokenizer'
MODEL = 'Qwen/Qwen3-4B-Instruct-2507'
REVISION = 'cdbee75f17c01a7cc42f958dc650907174af0554'
HASHES = {
    'config.json': '5beea1a4a34c62782bfb2f911c606741a3bab8f92d80a118fa053c28af12e8ba',
    'tokenizer.json': 'aeb13307a71acd8fe81861d94ad54ab689df773318809eed3cbe794b4492dae4',
    'tokenizer_config.json': 'a62ff0a2472a0fa1b8eaabcb57c59b58afa42a22831dc141400b6e0cf2b65ce3',
    'merges.txt': '599bab54075088774b1733fde865d5bd747cbcc7a547c5bc12610e874e26f5e3',
    'vocab.json': 'ca10d7e9fb3ed18575dd1e277a2579c16d108e32f27439684afa0e10b1440910',
}
PINS = {
    'torch': '2.13.0+cpu',
    'guidellm': '0.7.4',
    'transformers': '5.10.1',
    'datasets': '4.4.1',
    'pydantic': '2.12.5',
    'httpx': '0.28.1',
    'numpy': '2.3.5',
    'matplotlib': '3.11.0',
    'ipykernel': '7.3.0',
    'nbformat': '5.10.4',
    'nbclient': '0.11.0',
    'requests': '2.34.2',
    'pandas': '2.3.3',
}
os.umask(0o077)
if sys.version_info[:2] != (3, 12):
    raise SystemExit('Use a Workbench image with Python 3.12, the rehearsed version for these pinned dependencies.')
if not ROOT.is_dir() or not os.access(ROOT, os.W_OK):
    raise SystemExit('Run this script inside the Aurora Workbench with its writable /opt/app-root/src PVC.')
namespace = Path('/var/run/secrets/kubernetes.io/serviceaccount/namespace')
if not namespace.is_file() or namespace.read_text().strip() != 'ai-showroom':
    raise SystemExit('Run this script in the authorized ai-showroom Workbench.')
# The standard Workbench image discovers user kernels under this persistent home.
if Path.home().resolve() != ROOT.resolve():
    raise SystemExit('This setup expects the standard Workbench home /opt/app-root/src. Configure persistent Jupyter kernel discovery before using a different home.')

logs = ROOT / '.showroom-setup'
logs.mkdir(mode=0o700, exist_ok=True)
stamp = dt.datetime.now(dt.timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
log_path = logs / ('inference-kernel-' + stamp + '.log')
env = {key: value for key, value in os.environ.items() if key in {
    'HOME', 'PATH', 'LANG', 'LC_ALL', 'TZ', 'SSL_CERT_FILE', 'SSL_CERT_DIR', 'REQUESTS_CA_BUNDLE',
}}
# Do not inherit a private package index, proxy credentials, S3 keys, or HF tokens.
env.update(PIP_CONFIG_FILE=os.devnull, PIP_DISABLE_PIP_VERSION_CHECK='1')
python = str(VENV / 'bin/python')

def matching_packages():
    if not Path(python).is_file():
        return False
    code = 'import importlib.metadata as m,json; print(json.dumps({name:m.version(name) for name in ' + repr(list(PINS)) + '}))'
    check = subprocess.run([python, '-c', code], capture_output=True, text=True, env=env, timeout=30)
    return check.returncode == 0 and json.loads(check.stdout) == PINS

def matches_tokenizer():
    return all((TOKENIZER / name).is_file()
               and hashlib.sha256((TOKENIZER / name).read_bytes()).hexdigest() == digest
               for name, digest in HASHES.items())

def install_tokenizer():
    TOKENIZER.mkdir(mode=0o700, parents=True, exist_ok=True)
    if not matches_tokenizer():
        print('Downloading five public tokenizer/configuration files from the pinned Qwen revision. No model weights.', flush=True)
        # No implicit authentication, cookies, proxy credentials, or arbitrary file list.
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        with tempfile.TemporaryDirectory(prefix='.tokenizer-stage-', dir=TOKENIZER) as temporary:
            staged = Path(temporary)
            for name, expected in HASHES.items():
                url = f'https://huggingface.co/{MODEL}/resolve/{REVISION}/{name}'
                digest = hashlib.sha256()
                total = 0
                started = time.monotonic()
                with opener.open(url, timeout=30) as response, (staged / name).open('xb') as output:
                    if response.status != 200:
                        raise RuntimeError('Tokenizer download did not return HTTP 200.')
                    while True:
                        if time.monotonic() - started > 180:
                            raise TimeoutError('Tokenizer download deadline exceeded.')
                        chunk = response.read(64 * 1024)
                        if not chunk:
                            break
                        total += len(chunk)
                        if total > 16 * 1024 * 1024:
                            raise RuntimeError('Tokenizer file exceeds the fixed size limit.')
                        digest.update(chunk)
                        output.write(chunk)
                    output.flush()
                    os.fsync(output.fileno())
                if digest.hexdigest() != expected:
                    raise RuntimeError('Pinned tokenizer SHA256 check failed: ' + name)
            # Nothing reaches the final paths until all five hashes have passed.
            for name in HASHES:
                os.replace(staged / name, TOKENIZER / name)
    if not matches_tokenizer():
        raise RuntimeError('Tokenizer verification failed after installation.')
    provenance = {
        'model': MODEL, 'revision': REVISION,
        'source': 'Official Hugging Face tokenizer/configuration files only; no weights',
        'files': {name: {'bytes': (TOKENIZER / name).stat().st_size, 'sha256': digest}
                  for name, digest in HASHES.items()},
    }
    with tempfile.NamedTemporaryFile(mode='w', prefix='.provenance-', dir=TOKENIZER, delete=False) as output:
        json.dump(provenance, output, indent=2)
        output.write('\n')
        output.flush()
        os.fsync(output.fileno())
        temporary = Path(output.name)
    os.replace(temporary, TOKENIZER / 'showroom-provenance.json')
    print('Tokenizer verified: exact revision and all five SHA256 hashes.', flush=True)

with log_path.open('x') as log:
    try:
        if not Path(python).exists():
            print('Creating the separate persistent Python environment.', flush=True)
            venv.EnvBuilder(with_pip=True).create(VENV)
        subprocess.run([python, '-c', 'import sys; assert sys.version_info[:2] == (3, 12), "The existing inference environment must use Python 3.12."'],
                       stdout=log, stderr=subprocess.STDOUT, env=env, timeout=30, check=True)
        if matching_packages():
            print('All pinned packages are already installed; skipping package downloads.', flush=True)
        else:
            steps = [
                ('CPU-only PyTorch', [python, '-m', 'pip', 'install', '--no-cache-dir',
                 '--index-url', 'https://download.pytorch.org/whl/cpu', 'torch==' + PINS['torch']]),
                ('GuideLLM and notebook dependencies', [python, '-m', 'pip', 'install', '--no-cache-dir',
                 '--index-url', 'https://pypi.org/simple'] + [name + '==' + version for name, version in PINS.items() if name != 'torch']),
            ]
            for name, command in steps:
                print('Installing ' + name + '.', flush=True)
                subprocess.run(command, stdout=log, stderr=subprocess.STDOUT, env=env, timeout=900, check=True)
                log.flush()
        if not matching_packages():
            raise RuntimeError('Installed versions differ from the required pins.')
        subprocess.run([python, '-m', 'pip', 'check'], stdout=log, stderr=subprocess.STDOUT,
                       env=env, timeout=60, check=True)
        install_tokenizer()
        subprocess.run([python, '-m', 'ipykernel', 'install', '--user', '--name', 'aurora-inference',
                        '--display-name', 'Aurora Inference Demo'], stdout=log, stderr=subprocess.STDOUT,
                       env=env, timeout=60, check=True)
        kernel = ROOT / '.local/share/jupyter/kernels/aurora-inference/kernel.json'
        if not kernel.is_file() or json.loads(kernel.read_text())['argv'][0] != python:
            raise RuntimeError('The persistent kernel does not reference the expected environment.')
    except Exception as exc:
        print('Setup stopped (' + type(exc).__name__ + '). Private installation log: ' + str(log_path), flush=True)
        raise SystemExit(1) from None

print('Ready: select Aurora Inference Demo in the notebook kernel picker.', flush=True)
print('Open 07-qwen-live-traffic.ipynb or 08-qwen-guidellm.ipynb. No inference was started.', flush=True)
print('Private setup log: ' + str(log_path), flush=True)
PY
