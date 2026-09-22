#!/usr/bin/env python3
"""Measure the native Aurora OVMS/TrustyAI monitoring demonstration.

Run locally with oc login, or inside the Aurora Workbench. Tokens stay in memory.
The deterministic policy graph is not a learned forecast or a fairness guarantee.
"""
import argparse
import datetime
import json
import math
import os
from pathlib import Path
import ssl
import subprocess
import sys
import time
import urllib.error
import urllib.request
import uuid

NAMESPACE = 'ai-showroom-monitoring'
MODEL = 'aurora-allocation'
TRUSTY = f'https://trustyai-service-tls.{NAMESPACE}.svc'
INFERENCE = f'https://{MODEL}-predictor.{NAMESPACE}.svc:8443/v2/models/{MODEL}/infer'


def cohort(promotion=False):
    """100 paired synthetic observations; zone 0=East, zone 1=West."""
    rows = []
    for index in range(50):
        demand = 125.0 + index * 0.5
        stock = demand + (-20 if index < 30 else 40 if index < 45 else 120)
        for zone in (0, 1):
            rows.append([float(zone), demand + (60 if promotion and zone == 0 else 0), stock])
    return rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('phase', choices=['reference', 'baseline', 'promotion', 'measure'])
    parser.add_argument('--in-cluster', action='store_true', help=argparse.SUPPRESS)
    parser.add_argument('--schedule', action='store_true')
    parser.add_argument('--expected-server', help='Required for local oc mutations; independently verified API URL')
    parser.add_argument('--expected-user', help='Required for local oc mutations; independently verified identity')
    args = parser.parse_args()
    if not args.in_cluster and not os.path.exists('/var/run/secrets/kubernetes.io/serviceaccount/token'):
        if args.phase != 'measure' or args.schedule:
            if not args.expected_server or not args.expected_user:
                parser.error('Local mutation requires --expected-server and --expected-user; Workbench mode uses its bound cluster identity.')
            server = subprocess.check_output(['oc', 'whoami', '--show-server'], text=True, timeout=20).strip()
            user = subprocess.check_output(['oc', 'whoami'], text=True, timeout=20).strip()
            if (server.rstrip('/'), user) != (args.expected_server.rstrip('/'), args.expected_user):
                raise SystemExit('Cluster or identity mismatch; no inference/data changes made.')
        owned = json.loads(subprocess.check_output(['oc', 'get', 'inferenceservice', MODEL, '-n', NAMESPACE, '-o', 'json'], timeout=20))
        if owned['metadata'].get('labels', {}).get('app.kubernetes.io/part-of') != 'rhoai-showroom':
            raise SystemExit('Target model is not labeled as owned by this showroom.')
        token = subprocess.check_output(['oc', 'whoami', '-t'], text=True, timeout=20).strip()
        command = ['oc', 'exec', '-i', 'aurora-lab-0', '-n', 'ai-showroom', '-c', 'aurora-lab', '--', 'python', '-c', Path(__file__).read_text(), args.phase, '--in-cluster']
        if args.schedule:
            command.append('--schedule')
        result = subprocess.run(command, input=json.dumps({'token': token}), text=True, capture_output=True, timeout=180)
        print(result.stdout.replace(token, '[REDACTED]'), end='')
        if result.returncode:
            raise SystemExit(result.stderr.replace(token, '[REDACTED]'))
        return
    token = json.load(sys.stdin)['token'] if args.in_cluster else Path('/var/run/secrets/kubernetes.io/serviceaccount/token').read_text().strip()
    if Path('/var/run/secrets/kubernetes.io/serviceaccount/namespace').read_text().strip() != 'ai-showroom':
        raise SystemExit('Run inside the approved ai-showroom Workbench.')
    context = ssl.create_default_context(cafile='/var/run/secrets/kubernetes.io/serviceaccount/service-ca.crt')
    context.load_verify_locations(cafile='/var/run/secrets/kubernetes.io/serviceaccount/ca.crt')
    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, *unused, **kwargs):
            return None
    opener = urllib.request.build_opener(NoRedirect, urllib.request.HTTPSHandler(context=context))
    def request(url, body=None):
        req = urllib.request.Request(url, data=json.dumps(body).encode() if body is not None else None, headers={'Authorization': 'Bearer ' + token, 'Content-Type': 'application/json', 'Accept': '*/*'})
        try:
            with opener.open(req, timeout=30) as response:
                raw = response.read().decode()
                try:
                    return json.loads(raw)
                except json.JSONDecodeError:
                    return raw
        except urllib.error.HTTPError as error:
            raise RuntimeError(f'HTTP {error.code}: {error.read().decode()[:1500]}') from None
    owned = request(f'https://kubernetes.default.svc/apis/serving.kserve.io/v1beta1/namespaces/{NAMESPACE}/inferenceservices/{MODEL}')
    if owned['metadata'].get('labels', {}).get('app.kubernetes.io/part-of') != 'rhoai-showroom':
        raise SystemExit('Target model is not labeled as owned by this showroom.')
    def schedule(path, body):
        existing = request(TRUSTY + path + '/requests').get('requests', [])
        matches = [x for x in existing if x['request'].get('requestName') == body['requestName'] and x['request'].get('modelId') == body['modelId']]
        if len(matches) > 1:
            raise RuntimeError('Duplicate named monitoring requests; inspect before scheduling again.')
        if matches:
            for key, expected in body.items():
                actual = matches[0]['request'].get(key)
                if isinstance(actual, dict) and 'value' in actual:
                    actual = actual['value']
                if actual != expected:
                    raise RuntimeError(f'Existing named schedule conflicts on {key}; no replacement made.')
            return {'existingRequestId': matches[0]['id'], 'batchSize': matches[0]['request'].get('batchSize')}
        return request(TRUSTY + path + '/request', body)
    evidence = {'timestamp_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(), 'namespace': NAMESPACE, 'model': MODEL, 'phase': args.phase}
    before = request(TRUSTY + '/info').get(MODEL, {}).get('data', {}).get('observations', 0)
    if args.phase != 'measure':
        rows = cohort(args.phase == 'promotion')
        body = {'inputs': [{'name': 'inventory', 'shape': [len(rows), 3], 'datatype': 'FP64', 'data': rows}]}
        prediction = request(INFERENCE, body)
        outcomes = prediction['outputs'][0]['data']
        # KServe returns a flattened tensor. Keep the actual OVMS result as evidence.
        if outcomes and isinstance(outcomes[0], list):
            outcomes = [x[0] for x in outcomes]
        assert len(outcomes) == 100
        expected = [int(row[1] > row[2]) for row in rows]
        assert outcomes == expected, 'OVMS results differ from the published policy graph'
        evidence['inference_count'] = len(rows)
        evidence['group_rates'] = {name: sum(outcomes[zone::2]) / 50 for zone, name in enumerate(['East', 'West'])}
        evidence['actual_model_outputs_match_policy'] = True
        if args.phase == 'reference':
            body['id'] = str(uuid.uuid4())
            prediction['id'] = body['id']
            evidence['reference_upload'] = request(TRUSTY + '/data/upload', {'model_name': MODEL, 'data_tag': 'AURORA_REFERENCE', 'request': body, 'response': prediction})
        # The native KServe agent asynchronously sends actual inference input/output.
        deadline = time.monotonic() + 30
        while args.phase != 'reference':
            count = request(TRUSTY + '/info').get(MODEL, {}).get('data', {}).get('observations', 0)
            if count >= before + len(rows):
                evidence['automatic_capture_verified'] = True
                evidence['capture_check_scope'] = 'Aggregate observation increase in an exclusive rehearsal; no request-id correlation.'
                break
            if time.monotonic() >= deadline:
                raise RuntimeError('Native KServe capture did not deliver 100 new rows; inspect agent TLS/logs.')
            time.sleep(1)
        info = request(TRUSTY + '/info').get(MODEL, {}).get('data', {})
        if 'Warehouse zone' not in info.get('inputSchema', {}).get('items', {}):
            evidence['name_mapping'] = request(TRUSTY + '/info/names', {'modelId': MODEL, 'inputMapping': {'inventory-0': 'Warehouse zone', 'inventory-1': 'Seven-day demand', 'inventory-2': 'Available units'}, 'outputMapping': {'expedite-0': 'Expedited review'}})
    evidence['model_info'] = request(TRUSTY + '/info')
    if args.phase != 'reference':
        fairness = {'modelId': MODEL, 'protectedAttribute': 'Warehouse zone', 'privilegedAttribute': 0.0, 'unprivilegedAttribute': 1.0, 'outcomeName': 'Expedited review', 'favorableOutcome': 1, 'batchSize': 100}
        drift = {'modelId': MODEL, 'referenceTag': 'AURORA_REFERENCE', 'batchSize': evidence['model_info'][MODEL]['data']['observations']}
        for metric in ['spd', 'dir']:
            evidence[metric] = request(TRUSTY + '/metrics/group/fairness/' + metric, fairness)
            if not math.isfinite(float(evidence[metric]['value'])):
                raise RuntimeError(f'{metric.upper()} returned a non-finite value; no successful measurement claimed.')
            if args.schedule:
                body = dict(fairness, requestName='Aurora warehouse service levels — ' + metric.upper())
                evidence[metric + '_schedule'] = schedule('/metrics/group/fairness/' + metric, body)
        evidence['meanshift'] = request(TRUSTY + '/metrics/drift/meanshift', drift)
        evidence['drift_window'] = 'Cumulative recorded unlabeled inferences versus the fixed reference; fairness uses the latest 100 rows.'
        if args.schedule:
            evidence['drift_schedule'] = schedule('/metrics/drift/meanshift', dict(drift, batchSize=100, requestName='Aurora promotion demand drift'))
    print(json.dumps(evidence, indent=2))


if __name__ == '__main__':
    main()
