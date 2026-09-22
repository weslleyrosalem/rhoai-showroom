#!/usr/bin/env python3
"""Read-only physical GPU guard. Exit 2 means BLOCKED, never an inferred PASS.

Cloud inventory is intentionally external: OpenShift cannot see pending ROSA
machines, other pools' maxima, or upgrade surge. A current, complete inventory
must come from ROSA/OCM before any cloud operation. No cloud mutations occur here.
"""
import argparse
import datetime as dt
import json
from pathlib import Path
import re
import subprocess
import sys

LIMIT = 16
GPU_COUNTS = {
    'g6e.xlarge': 1, 'g6e.2xlarge': 1, 'g6e.4xlarge': 1,
    'g6e.8xlarge': 1, 'g6e.16xlarge': 1, 'g6e.12xlarge': 4,
    'g6e.24xlarge': 4, 'g6e.48xlarge': 8,
    'p4d.24xlarge': 8, 'p4de.24xlarge': 8,
    'p5.4xlarge': 1, 'p5.48xlarge': 8,
}
ROOT = Path(__file__).resolve().parents[1]


def nonnegative(value, field):
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise ValueError(f'{field} must be a nonnegative integer')
    return value


def physical_gpus(node):
    labels = node['metadata'].get('labels', {})
    count = labels.get('nvidia.com/gpu.count')
    instance = labels.get('node.kubernetes.io/instance-type', '')
    instance_count = GPU_COUNTS.get(instance)
    # GFD's gpu.count can count MIG instances in single strategy, and in
    # mixed strategy can count only whole GPUs. The verified EC2 type is the
    # physical inventory; never interpret those virtual-device labels as cards.
    if instance_count is not None:
        return instance_count
    if re.match(r'^[gp][0-9]', instance):
        raise ValueError('Unmapped AWS GPU instance type; add verified physical GPU count before proceeding')
    mig_active = labels.get('nvidia.com/mig.config', 'all-disabled') != 'all-disabled'
    shared = labels.get('nvidia.com/gpu.sharing-strategy', 'none') != 'none'
    if mig_active or shared:
        raise ValueError('Unknown physical GPU type with MIG/sharing; add verified instance mapping')
    if count is not None:
        value = int(count)
        if value < 0:
            raise ValueError('negative GPU count')
        return value
    alloc = node.get('status', {}).get('allocatable', {})
    if any(k.startswith('nvidia.com/') for k in alloc) or labels.get('nvidia.com/gpu.present') == 'true':
        raise ValueError('GPU node lacks a physical count; do not infer from MIG/time-slicing resources')
    return 0


def assess(profile, nodes, inventory=None, now=None, expected_server=None):
    """Conservatively retain every live/cloud pool, overlay requested maxima by id."""
    now = now or dt.datetime.now(dt.timezone.utc)
    problems = []
    if profile.get('physical_gpu_limit') != LIMIT:
        raise ValueError('profile must use the fixed global limit 16')
    node_counts = {n['metadata']['name']: physical_gpus(n) for n in nodes['items']}
    if len(node_counts) != len(nodes['items']):
        raise ValueError('duplicate node name')
    live = sum(node_counts.values())
    planned = sum(GPU_COUNTS[p['instance_type']] *
                  (nonnegative(p['max_nodes'], 'max_nodes') +
                   nonnegative(p['upgrade_surge_nodes'], 'upgrade_surge_nodes'))
                  for p in profile['pools'])
    if inventory is None:
        return {'status': 'BLOCKED', 'limit': LIMIT, 'live_physical_gpus': live,
                'profile_pool_ceiling': planned,
                'reasons': ['Complete fresh ROSA/OCM pool inventory is required; live nodes omit pending machines, maxima and surge.']}
    if expected_server is not None and inventory.get('cluster_server') != expected_server:
        problems.append('Inventory cluster_server must match the explicitly selected cluster.')
    if inventory.get('schema_version') != 1 or inventory.get('complete') is not True:
        problems.append('Inventory must declare schema_version=1 and complete=true.')
    try:
        timestamp = dt.datetime.fromisoformat(inventory['observed_at'].replace('Z', '+00:00'))
        age = (now - timestamp).total_seconds()
        if age < -60 or age > 900:
            problems.append('Inventory is stale or from the future (maximum age 15 minutes).')
    except (KeyError, ValueError, TypeError):
        problems.append('Inventory observed_at must be an ISO8601 timestamp with timezone.')
    semantics = inventory.get('count_semantics', 'exact')
    if semantics not in ('exact', 'upper-bound'):
        problems.append('Inventory count_semantics must be exact or upper-bound.')
    pools = {}
    covered = set()
    current_cloud = 0
    for pool in inventory.get('pools', []):
        pool = dict(pool)
        ident = pool['id']
        if ident in pools:
            raise ValueError('duplicate pool id')
        if pool.get('instance_type') not in GPU_COUNTS:
            if re.match(r'^[gp][0-9]', pool.get('instance_type', '')):
                raise ValueError('Unmapped AWS GPU pool cannot be declared CPU-only')
            if pool.get('gpus_per_node') != 0:
                raise ValueError('unknown pool type: declare CPU-only gpus_per_node=0 or add verified GPU mapping')
            gpu = 0
        else:
            gpu = GPU_COUNTS[pool['instance_type']]
        for key in ('current_nodes', 'desired_nodes', 'max_nodes', 'upgrade_surge_nodes'):
            nonnegative(pool[key], key)
        names = set(pool['node_names'])
        if names & covered:
            raise ValueError('node is claimed by multiple pools')
        if not names <= set(node_counts):
            problems.append('Inventory lists nodes absent from the current cluster; refresh both snapshots.')
        if len(names) > pool['current_nodes']:
            problems.append('Pool current_nodes is below the count of its registered nodes.')
        for name in names & set(node_counts):
            if node_counts[name] != gpu:
                problems.append('Pool hardware does not match registered node hardware.')
        covered |= names
        current_cloud += pool['current_nodes'] * gpu
        pool['_gpus'] = gpu
        pools[ident] = pool
    # Current nodes remain counted while a pool is being scaled down. Never assume
    # a mutually-exclusive profile has actually removed another pool.
    for requested in profile['pools']:
        ident = requested['id']
        gpu = GPU_COUNTS[requested['instance_type']]
        if ident in pools:
            pool = pools[ident]
            if pool['instance_type'] != requested['instance_type']:
                raise ValueError('cannot change an existing machinepool instance type')
            pool['max_nodes'] = max(pool['max_nodes'], requested['max_nodes'])
            pool['upgrade_surge_nodes'] = max(pool['upgrade_surge_nodes'], requested['upgrade_surge_nodes'])
        else:
            pools[ident] = dict(requested, current_nodes=0, desired_nodes=0, _gpus=gpu)
    unclaimed = sum(v for k, v in node_counts.items() if k not in covered)
    ceiling = unclaimed + sum(p['_gpus'] *
        (max(p['current_nodes'], p['desired_nodes'], p['max_nodes']) + p['upgrade_surge_nodes'])
        for p in pools.values())
    if ceiling > LIMIT:
        problems.append(f'Combined pool maxima/current/desired plus upgrade surge reach {ceiling} physical GPUs, above {LIMIT}.')
    if live > LIMIT:
        problems.append('Current cluster already exceeds the fixed GPU ceiling.')
    return {'status': 'BLOCKED' if problems else 'PASS', 'limit': LIMIT,
            'live_physical_gpus': live,
            'cloud_count_semantics': semantics,
            'cloud_current_physical_gpus': current_cloud if semantics == 'exact' else None,
            'cloud_current_physical_gpu_upper_bound': current_cloud if semantics == 'upper-bound' else None,
            'unclaimed_live_physical_gpus': unclaimed, 'combined_physical_gpu_ceiling': ceiling,
            'reasons': problems,
            'scope': 'Capacity accounting only; does not validate quota, availability, cost, runtime readiness, or perform mutations.'}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--profile', required=True, choices=['core', 'interactive', 'active-l40s-9', 'mig-h100-single', 'full-l40s-13', 'mig-9', 'mig-13'])
    parser.add_argument('--inventory', type=Path, help='Private complete ROSA/OCM JSON snapshot; see hardware lab')
    parser.add_argument('--nodes', type=Path, help='Saved oc get nodes -o json; otherwise query current cluster')
    parser.add_argument('--expected-server', help='Require an exact oc API server before querying live nodes')
    parser.add_argument('--output', type=Path)
    args = parser.parse_args(argv)
    try:
        profile = json.loads((ROOT/'gitops/profiles'/args.profile/'capacity.json').read_text())
        if args.nodes:
            nodes = json.loads(args.nodes.read_text())
        else:
            if not args.expected_server:
                raise ValueError('--expected-server is required for live cluster access')
            server = subprocess.check_output(['oc','whoami','--show-server'], text=True).strip()
            if server != args.expected_server:
                raise ValueError('oc context does not match --expected-server')
            nodes = json.loads(subprocess.check_output(['oc','get','nodes','-o','json','--request-timeout=30s'], text=True))
        inventory = json.loads(args.inventory.read_text()) if args.inventory else None
        result = assess(profile, nodes, inventory, expected_server=args.expected_server)
    except (ValueError, KeyError, OSError, subprocess.CalledProcessError) as exc:
        result = {'status':'BLOCKED','limit':LIMIT,'reasons':[str(exc)]}
    rendered = json.dumps(result, indent=2) + '\n'
    print(rendered, end='')
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered)
    return 0 if result['status']=='PASS' else 2


if __name__ == '__main__':
    sys.exit(main())
