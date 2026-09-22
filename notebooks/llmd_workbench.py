"""Request one live administrator-mediated llm-d comparison through a PVC channel.

No cluster credential, network connection, command, model parameter, or backend
address is accepted by this notebook helper. Historical results are never loaded.
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
import json
import math
import os
from pathlib import Path
import stat
import time
import uuid

CHANNEL = Path('/opt/app-root/src/.local/share/aurora-showroom/llmd-live')
MODES = ('round-robin', 'llmd')
MODEL_URI = 'hf://Qwen/Qwen3-4B-Instruct-2507:cdbee75f17c01a7cc42f958dc650907174af0554'


def _timestamp(value):
    if not isinstance(value, str):
        raise ValueError('The live controller returned an invalid timestamp.')
    parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if parsed.tzinfo is None:
        raise ValueError('Controller timestamps must include a timezone.')
    return parsed


def _now():
    return datetime.now(timezone.utc)


def _directory(path, create=False):
    # Check every existing path component so a parent symlink cannot redirect I/O.
    for part in reversed((path, *path.parents)):
        if part.is_symlink():
            raise ValueError('The live comparison channel must not contain symlinks.')
    if create:
        path.mkdir(mode=0o700, parents=True, exist_ok=True)
    if not path.is_dir():
        raise RuntimeError('The live comparison controller is not prepared. No inference was requested.')
    return path


def _read(path):
    _directory(path.parent)
    descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    with os.fdopen(descriptor, 'r') as stream:
        info = os.fstat(stream.fileno())
        if not stat.S_ISREG(info.st_mode) or info.st_size > 1024 * 1024:
            raise ValueError('Invalid live controller response file.')
        result = json.load(stream)
    if not isinstance(result, dict):
        raise ValueError('Expected a live controller object.')
    return result


def _publish(path, value):
    _directory(path.parent, create=True)
    if path.exists() or path.is_symlink():
        raise ValueError('Refusing to overwrite an existing comparison request.')
    temporary = path.parent / ('.' + uuid.uuid4().hex + '.tmp')
    descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    try:
        with os.fdopen(descriptor, 'w') as stream:
            json.dump(value, stream, allow_nan=False)
            stream.flush()
            os.fsync(stream.fileno())
        # A hard link publishes a complete file without replacing an existing name.
        os.link(temporary, path, follow_symlinks=False)
    finally:
        temporary.unlink(missing_ok=True)


def controller_status():
    """Read a fresh, nonsecret controller lease; do not start a run."""
    try:
        health = _read(CHANNEL / 'health.json')
    except FileNotFoundError:
        raise RuntimeError('The live comparison controller is offline. No prerecorded result will be substituted.') from None
    clock = _now()
    age = (clock - _timestamp(health.get('updated_at'))).total_seconds()
    if not -5 <= age < 90 or _timestamp(health.get('expires_at')) <= clock:
        raise RuntimeError('The live controller lease is stale or expired. Ask the presenter to start a fresh session.')
    if health.get('state') not in ('READY', 'RUNNING'):
        raise RuntimeError('The live comparison controller is unavailable.')
    remaining = health.get('remaining_runs')
    if type(remaining) is not int or not 0 <= remaining <= 6:
        raise ValueError('Invalid live controller run budget.')
    return {'state': health['state'], 'updated_at': health['updated_at'],
            'expires_at': health['expires_at'], 'remaining_runs': remaining}


def _number(value, integer=False):
    if type(value) not in (int, float) or not math.isfinite(value) or value < 0:
        raise ValueError('The live result contains an invalid numerical measurement.')
    if integer and (type(value) is not int):
        raise ValueError('Expected an integer request count.')
    return value


def _summary(raw, requested_at):
    """Allowlist measured fields and refuse another model, mode, or old run."""
    if not isinstance(raw, dict) or raw.get('status') != 'MEASURED':
        raise ValueError('The controller did not return a measured live comparison.')
    start, finish = _timestamp(raw.get('started_at')), _timestamp(raw.get('finished_at'))
    if start.timestamp() < requested_at.timestamp() - 5 or finish < start or finish.timestamp() > _now().timestamp() + 5:
        raise ValueError('The returned measurement does not belong to this fresh request.')
    topology = raw.get('topology', {})
    if (topology.get('ready_backends') != 2 or topology.get('distinct_gpu_nodes') != 2
            or topology.get('model', {}).get('name') != 'aurora-qwen-4b'
            or topology.get('model', {}).get('uri') != MODEL_URI
            or topology.get('prefix_cache_scorer_present') is not True):
        raise ValueError('The live topology does not match the reviewed two-backend Qwen experiment.')
    workload = raw.get('workload', {})
    if (workload.get('seconds_per_mode') != 30 or workload.get('output_tokens') != 32
            or workload.get('guidellm_version') != '0.6.0'
            or any(workload.get('concurrency', {}).get(mode) != 2 for mode in MODES)):
        raise ValueError('The controller changed the fixed reviewed workload.')
    rows, seen = [], set()
    runs = raw.get('runs')
    if not isinstance(runs, list) or len(runs) != 2:
        raise ValueError('Both live comparison modes are required; partial results are not a pass.')
    for run in runs:
        mode = run.get('mode')
        if mode not in MODES or mode in seen:
            raise ValueError('Expected one round-robin run and one llm-d run.')
        seen.add(mode)
        requests = {key: _number(run.get('requests', {}).get(key), True)
                    for key in ('successful', 'errored', 'incomplete', 'total')}
        if (not 1 <= requests['successful'] <= 16 or requests['errored'] or requests['incomplete']
                or requests['total'] != requests['successful']):
            raise ValueError('A benchmark did not pass the functional completion gate.')
        backend = run.get('backend_success_deltas')
        if not isinstance(backend, list) or len(backend) != 2:
            raise ValueError('Two per-backend observations are required.')
        hits = _number(run.get('backend_prefix_hits_delta'))
        queries = _number(run.get('backend_prefix_queries_delta'))
        if hits > queries:
            raise ValueError('The observed cache counters do not form a valid window.')
        row = {'mode': mode, **requests, 'duration_seconds': _number(run.get('duration_seconds')),
               'backend_a_success_delta': _number(backend[0]), 'backend_b_success_delta': _number(backend[1]),
               'prefix_hits_delta': hits, 'prefix_queries_delta': queries,
               'cache_hit_fraction': hits / queries if queries else None,
               'epp_request_delta': _number(run.get('epp_request_delta'))}
        for field in ('time_to_first_token_ms', 'request_latency', 'requests_per_second', 'output_tokens_per_second'):
            for metric in ('mean', 'p95'):
                row[field + '_' + metric] = _number(run.get(field, {}).get(metric))
        rows.append(row)
    rows.sort(key=lambda row: MODES.index(row['mode']))
    return {'started_at': raw['started_at'], 'finished_at': raw['finished_at'],
            'model': 'aurora-qwen-4b', 'ready_backends': 2, 'distinct_gpu_nodes': 2,
            'prefix_cache_scorer_present': True, 'guidellm_version': '0.6.0', 'rows': rows}


def _cancel(identifier):
    destination = CHANNEL / 'cancel' / (identifier + '.json')
    if not destination.exists():
        _publish(destination, {'id': identifier})


async def compare():
    """Submit exactly one fixed live comparison and wait at most 210 seconds."""
    health = controller_status()
    if health['state'] != 'READY' or health['remaining_runs'] < 1:
        raise RuntimeError('The controller is busy or its run budget is exhausted. No request was submitted.')
    created = _now()
    if (_timestamp(health['expires_at']) - created).total_seconds() < 210:
        raise RuntimeError('The remaining controller session is too short for a complete run.')
    identifier = str(uuid.uuid4())
    _publish(CHANNEL / 'requests' / (identifier + '.json'),
             {'id': identifier, 'action': 'compare', 'created_at': created.isoformat()})
    print('Submitted one fresh live comparison. Waiting for the administrator controller...', flush=True)
    response_path = CHANNEL / 'responses' / (identifier + '.json')
    deadline = time.monotonic() + 210
    last_state = None
    try:
        while time.monotonic() < deadline:
            try:
                response = _read(response_path)
            except FileNotFoundError:
                response = None
            if response is not None:
                if response.get('id') != identifier:
                    raise ValueError('The controller response UUID does not match this request.')
                updated = _timestamp(response.get('updated_at'))
                if updated.timestamp() < created.timestamp() - 5 or updated.timestamp() > _now().timestamp() + 5:
                    raise ValueError('The controller response timestamp is not valid for this request.')
                state = response.get('state')
                if state not in ('RUNNING', 'COMPLETE', 'FAILED', 'CANCELLED'):
                    raise ValueError('Unknown live controller response state.')
                if state != last_state:
                    print('Live comparison:', state, flush=True)
                    last_state = state
                if state == 'FAILED':
                    raise RuntimeError('The live comparison failed. Ask the presenter to inspect retained controller evidence; no historical result is substituted.')
                if state == 'CANCELLED':
                    raise RuntimeError('The controller canceled this live comparison. Partial measurements are not presented as a completed comparison.')
                if state == 'COMPLETE':
                    result = _summary(response.get('result'), created)
                    result['request_id'] = identifier
                    print('Fresh round-robin and llm-d measurements received. No notebook load remains running.', flush=True)
                    return result
            await asyncio.sleep(2)
        raise TimeoutError('Live comparison exceeded the 210-second notebook wait limit.')
    except BaseException:
        try:
            _cancel(identifier)
        except (OSError, ValueError, RuntimeError):
            print('The cancellation file could not be written. Contact the presenter; the controller also has a fixed execution deadline.', flush=True)
        print('Cancellation requested for this UUID. The controller owns subprocess cleanup; a server may finish a request already accepted.', flush=True)
        raise


def display_comparison(result):
    """Show this run's actual measurements; do not load or impute prior results."""
    import pandas as pd
    import matplotlib.pyplot as plt
    from IPython.display import display
    frame = pd.DataFrame(result['rows'])
    print('Live UTC window:', result['started_at'], 'to', result['finished_at'])
    display(frame[['mode', 'successful', 'errored', 'incomplete', 'duration_seconds',
                   'epp_request_delta', 'backend_a_success_delta', 'backend_b_success_delta']])
    display(frame[['mode', 'prefix_hits_delta', 'prefix_queries_delta', 'cache_hit_fraction',
                   'time_to_first_token_ms_mean', 'time_to_first_token_ms_p95',
                   'request_latency_mean', 'requests_per_second_mean', 'output_tokens_per_second_mean']])
    fig, axes = plt.subplots(2, 2, figsize=(11, 7))
    frame.set_index('mode')[['backend_a_success_delta', 'backend_b_success_delta']].plot.bar(ax=axes[0, 0])
    axes[0, 0].set(title='Observed per-backend completions', ylabel='Counter delta', xlabel='Path')
    available = frame.dropna(subset=['cache_hit_fraction'])
    axes[0, 1].bar(available['mode'], available['cache_hit_fraction'] * 100)
    axes[0, 1].set(title='Observed local prefix-cache hits', ylabel='Hits / queries (%)', ylim=(0, 100))
    if len(available) < len(frame):
        axes[0, 1].text(.5, .95, 'Missing queries: unavailable, not zero', ha='center', transform=axes[0, 1].transAxes)
    axes[1, 0].bar(frame['mode'], frame['time_to_first_token_ms_mean'])
    axes[1, 0].set(title='GuideLLM-reported mean TTFT', ylabel='Milliseconds')
    axes[1, 1].bar(frame['mode'], frame['request_latency_mean'] * 1000)
    axes[1, 1].set(title='Observed mean end-to-end latency', ylabel='Milliseconds')
    fig.tight_layout()
    plt.show()
    print('Interpretation: two live paths, shared backends, small samples. Authentication/transport differ; '
          'other scoring plugins and concurrent traffic contribute. This does not establish a causal llm-d '
          'speedup, capacity limit, or cross-node KV transfer.')
