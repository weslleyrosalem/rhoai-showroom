#!/usr/bin/env python3
"""Measure first-use versus repeated-prefix SSE on an existing vLLM endpoint.

No cache reset, deployment change, key issuance, or workload restart. Reads the
existing MaaS Secret in memory. All output is sanitized measurement evidence.
"""
import argparse
import base64
import datetime as dt
import hashlib
import json
from pathlib import Path
import secrets
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import benchmark

COUNTERS = ["vllm:prefix_cache_queries_total", "vllm:prefix_cache_hits_total",
            "vllm:external_prefix_cache_queries_total", "vllm:external_prefix_cache_hits_total"]
METRICS_CODE = '''import ssl,urllib.request,json,re
text=urllib.request.urlopen("https://localhost:8000/metrics",context=ssl.create_default_context(cafile="/var/run/kserve/tls/ca.crt"),timeout=10).read(4000000).decode()
names=%r
result={"counters":{}}
for line in text.splitlines():
 if line.startswith("#"):continue
 name=line.split("{",1)[0].split(" ",1)[0]
 if name in names:result["counters"][name]=result["counters"].get(name,0)+float(line.rsplit(" ",1)[1])
 if name=="vllm:cache_config_info":result["cache_config_metric"]=line
 if name in ["vllm:num_requests_running","vllm:num_requests_waiting"]:result[name]=float(line.rsplit(" ",1)[1])
print(json.dumps(result))
''' % COUNTERS


def oc(*args):
    result = subprocess.run(["oc", "--request-timeout=30s", *args], capture_output=True,
                            text=True, timeout=40)
    if result.returncode:
        raise RuntimeError("Cluster inspection failed; no response body or credentials were logged")
    return result.stdout.strip()


def metrics(args):
    return json.loads(oc("exec", "-n", args.namespace, "deployment/" + args.deployment,
                         "-c", "main", "--", "python", "-c", METRICS_CODE))


def prompt(nonce):
    prefix = f"Aurora measurement session {nonce}. Use only the fictional inventory below.\n"
    prefix += "Policy: recommend only; never place orders. Cite inventory evidence. Orders above USD5000 need manager approval. Supplier lead time is seven days. Maintain fourteen days of stock.\n"
    prefix += "\n".join(f"SKU-{i:03d}: on_hand={25+i}; daily_demand={2+i%5}; unit_cost_usd={10+i}; supplier=Northstar; last_count=2026-09-21." for i in range(48))
    return [{"role": "system", "content": prefix}, {"role": "user", "content": "In exactly one short sentence, explain whether SKU-003 needs a replenishment review. Do not place an order."}]


def request(endpoint, model, key, messages, max_tokens):
    start = time.monotonic()
    body = {"model": model, "messages": messages, "temperature": 0, "seed": 42,
            "max_tokens": max_tokens, "stream": True, "stream_options": {"include_usage": True}}
    row = {"started_at": dt.datetime.now(dt.timezone.utc).isoformat(),
           "prompt_sha256": hashlib.sha256(json.dumps(messages, sort_keys=True).encode()).hexdigest()}
    req = urllib.request.Request(endpoint, data=json.dumps(body).encode(), headers={
        "Authorization": "Bearer " + key, "Content-Type": "application/json", "Accept": "text/event-stream"})
    try:
        with urllib.request.build_opener(benchmark.NoRedirect).open(req, timeout=60) as response:
            row["http_status"] = response.status
            row.update(benchmark.parse_sse(benchmark.bounded_sse_lines(response, start + 60), start))
            row["ok"] = response.status == 200
    except urllib.error.HTTPError as error:
        row.update(ok=False, http_status=error.code, error="HTTPError")
    except (OSError, ValueError, TimeoutError) as error:
        row.update(ok=False, error=type(error).__name__)
    row["latency_ms"] = (time.monotonic() - start) * 1000
    return row


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--expected-server", required=True)
    p.add_argument("--expected-user", required=True)
    p.add_argument("--namespace", default="maas-how-to")
    p.add_argument("--deployment", default="redhataillama-31-8b-instruct-kserve")
    p.add_argument("--secret-namespace", default="ai-showroom")
    p.add_argument("--secret", default="showroom-maas-key")
    p.add_argument("--pairs", type=int, default=3)
    p.add_argument("--max-tokens", type=int, default=32)
    p.add_argument("--output", required=True, type=Path)
    args = p.parse_args()
    if not 1 <= args.pairs <= 3 or not 1 <= args.max_tokens <= 64:
        raise ValueError("Use 1..3 pairs and 1..64 output tokens; concurrency is fixed at one")
    if args.output.exists():
        raise ValueError("Output exists; choose a new file to preserve rehearsal history")
    if oc("whoami", "--show-server") != args.expected_server or oc("whoami") != args.expected_user:
        raise ValueError("Cluster or identity differs from the explicit guard")
    secret = json.loads(oc("get", "secret", args.secret, "-n", args.secret_namespace, "-o", "json"))
    if secret["metadata"].get("labels", {}).get("app.kubernetes.io/part-of") != "rhoai-showroom":
        raise ValueError("Only an owned showroom MaaS Secret may be used")
    values = {k: base64.b64decode(secret["data"][k]).decode() for k in ["api-key", "base-url", "model-id"]}
    url = urllib.parse.urlsplit(values["base-url"])
    if url.scheme != "https" or not url.hostname or url.username or url.password or url.query or url.fragment:
        raise ValueError("Require a verified HTTPS MaaS base URL without embedded credentials")
    dep = json.loads(oc("get", "deployment", args.deployment, "-n", args.namespace, "-o", "json"))
    if dep.get("status", {}).get("readyReplicas") != 1 or dep["spec"].get("replicas") != 1:
        raise ValueError("This local-cache rehearsal requires exactly one ready backend")
    rows = []
    result = {"schema_version": 1, "started_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "measurement": "first use of a new prefix versus immediate identical prefix; no global cache flush",
        "boundary": "client HTTP/SSE including gateway, authentication, network and engine",
        "configuration": {"pairs": args.pairs, "concurrency": 1, "max_tokens": args.max_tokens,
            "temperature": 0, "seed": 42}, "model": values["model-id"],
        "runtime_image": next(c["image"] for c in dep["spec"]["template"]["spec"]["containers"] if c["name"] == "main"),
        "requests": rows, "limitations": ["Shared backend metrics can include other clients.",
            "First-use prefix is not a cold model start.", "No Transformers A/B or multi-replica routing comparison.",
            "Local automatic prefix caching is not cross-node KV disaggregation."]}
    total_tokens = 0
    try:
        for pair in range(args.pairs):
            messages = prompt(secrets.token_hex(16))
            for stage in ["first_use", "repeat"]:
                before = metrics(args)
                row = request(values["base-url"].rstrip("/") + "/chat/completions", values["model-id"],
                              values["api-key"], messages, args.max_tokens)
                row.update(pair=pair + 1, stage=stage, before=before)
                # vLLM publishes periodic engine stats; wait without changing the workload.
                time.sleep(6)
                after = metrics(args)
                row["after"] = after
                row["counter_delta"] = {name: after["counters"].get(name, 0) - before["counters"].get(name, 0)
                                        for name in COUNTERS}
                row["counter_reset_detected"] = any(v < 0 for v in row["counter_delta"].values())
                queries = row["counter_delta"][COUNTERS[0]]
                row["other_traffic_or_collection_overlap_possible"] = row.get("prompt_tokens") is None or abs(queries - row["prompt_tokens"]) > 32
                rows.append(row)
                total_tokens += row.get("total_tokens") or 0
                if not row["ok"] or row["counter_reset_detected"] or total_tokens > 18000:
                    raise RuntimeError("Rehearsal stopped after an HTTP/stream/counter/budget failure; inspect recorded evidence")
        result["status"] = "MEASURED"
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as error:
        result.update(status="INCOMPLETE", error=type(error).__name__)
    result["total_usage_tokens"] = total_tokens
    result["finished_at"] = dt.datetime.now(dt.timezone.utc).isoformat()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x") as stream:
        json.dump(result, stream, indent=2)
        stream.write("\n")
    print(json.dumps({"status": result["status"], "total_usage_tokens": total_tokens,
        "requests": [{k: r.get(k) for k in ["pair", "stage", "http_status", "ttft_ms", "latency_ms", "prompt_tokens", "completion_tokens", "counter_delta", "other_traffic_or_collection_overlap_possible"]}for r in rows]}, indent=2))
    return 0 if result["status"] == "MEASURED" else 2


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as error:
        print(f"BLOCKED: {error}", file=sys.stderr)
        sys.exit(2)
