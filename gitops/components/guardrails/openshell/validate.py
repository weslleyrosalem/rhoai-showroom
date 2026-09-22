#!/usr/bin/env python3
"""Check the private OpenShell extension and print only sanitized evidence."""
import argparse
import base64
import http.client
import json
import os
from pathlib import Path
import ssl
import subprocess
from urllib.parse import urlsplit

HERE = Path(__file__).resolve().parent


def oc(*args):
    return subprocess.check_output(["oc", *args], text=True).strip()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--expected-server", required=True)
    parser.add_argument("--expected-user", default="aiadmin")
    parser.add_argument("--state-dir", required=True, type=Path)
    parser.add_argument("--cli", default="openshell")
    args = parser.parse_args()
    if oc("whoami") != args.expected_user or oc("whoami", "--show-server") != args.expected_server:
        raise SystemExit("Unexpected cluster or user; stopping.")
    state = args.state_dir.resolve()
    gateway = state / "openshell/gateways/showroom"
    metadata = json.loads((gateway / "metadata.json").read_text())
    url = urlsplit(metadata["gateway_endpoint"])
    if url.scheme != "https" or url.hostname != "127.0.0.1" or url.username or url.password or url.path or url.query or url.fragment:
        raise SystemExit("Validation requires the verified localhost port-forward endpoint.")
    context = ssl.create_default_context(cafile=str(gateway / "mtls/ca.crt"))
    other = oc("create", "token", "default", "-n", "ai-showroom-sandbox", "--audience=showroom-openshell", "--duration=10m")
    fake = base64.urlsafe_b64encode(json.dumps({"iss": "openshell-gateway:fake", "sub": "spiffe://openshell/sandbox/fake"}).encode()).decode().rstrip("=")
    checks = []
    cases = [("anonymous", "", "ListSandboxes", "7"), ("invalid", "invalid", "ListSandboxes", "7"), ("other_valid_subject", other, "ListSandboxes", "7"), ("forged_native_admin", "e30." + fake + ".invalid", "ListSandboxes", "7"), ("forged_native_callback", "e30." + fake + ".invalid", "GetSandboxConfig", "16")]
    for name, token, method, expected in cases:
        connection = http.client.HTTPSConnection(url.hostname, url.port, context=context, timeout=10)
        headers = {"Content-Type": "application/grpc", "TE": "trailers"}
        if token:
            headers["Authorization"] = "Bearer " + token
        connection.request("POST", "/openshell.v1.OpenShell/" + method, body=b"\0\0\0\0\0", headers=headers)
        response = connection.getresponse()
        grpc_status = response.getheader("grpc-status")
        checks.append({"name": name, "http_status": response.status, "grpc_status": grpc_status, "pass": grpc_status == expected})
        response.read()
        connection.close()
    env = dict(os.environ, XDG_CONFIG_HOME=str(state))
    cli = [args.cli, "-g", "showroom"]
    result = subprocess.run(cli + ["sandbox", "list"], env=env, capture_output=True, text=True)
    checks.append({"name": "named_subject", "pass": result.returncode == 0})
    result = subprocess.run(cli + ["sandbox", "exec", "--name", "aurora-sandbox", "--no-tty", "--timeout", "120", "--", "python", "-c", (HERE / "runtime_check.py").read_text()], env=env, capture_output=True, text=True)
    runtime = json.loads(result.stdout) if result.returncode == 0 else {"error": "Sandbox runtime check failed"}
    safe = runtime.get("uid", 0) != 0 and runtime.get("process_status") == {"CapEff": 0, "NoNewPrivs": 1, "Seccomp": 2}
    safe = safe and runtime.get("allowed_write", {}).get("allowed") is True
    safe = safe and all(runtime.get(key, {}).get("allowed") is False and runtime[key].get("errno") == 13 for key in ("outside_write", "tls_private_key", "service_account_token"))
    safe = safe and "403 Forbidden" in runtime.get("external_egress", {}).get("detail", "")
    safe = safe and runtime.get("inference", {}).get("http_status") == 200
    checks.append({"name": "agent_runtime_and_inference", "pass": safe})
    for subject in ("showroom-visitor", "showroom-engineer"):
        result = subprocess.run(["oc", "auth", "can-i", "create", "pods/portforward", "-n", "ai-showroom-sandbox", "--as=system:serviceaccount:ai-showroom:" + subject], text=True, capture_output=True)
        checks.append({"name": subject + "_no_portforward", "pass": result.stdout.strip() == "no"})
    passed = all(item["pass"] for item in checks)
    print(json.dumps({"pass": passed, "checks": checks, "runtime": runtime}, indent=2))
    raise SystemExit(0 if passed else 1)


if __name__ == "__main__":
    main()
