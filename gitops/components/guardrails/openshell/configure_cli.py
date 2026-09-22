#!/usr/bin/env python3
"""Create private local OpenShell CLI state without printing credentials."""
import argparse
import base64
import json
import os
from pathlib import Path
import subprocess
import time


def oc(*args):
    return subprocess.check_output(["oc", *args], text=True).strip()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--expected-server", required=True)
    parser.add_argument("--expected-user", default="aiadmin")
    parser.add_argument("--state-dir", required=True, type=Path)
    parser.add_argument("--port", default=38004, type=int)
    args = parser.parse_args()
    if oc("whoami") != args.expected_user or oc("whoami", "--show-server") != args.expected_server:
        raise SystemExit("Unexpected cluster or user; stopping.")
    if not 1024 <= args.port <= 65535:
        raise SystemExit("Use an unprivileged localhost port.")
    state = args.state_dir.resolve()
    repository = Path(__file__).resolve().parents[4]
    if state == repository or repository in state.parents:
        raise SystemExit("Store credentials outside the Git repository.")
    os.umask(0o077)
    target = state / "openshell/gateways/showroom"
    tls = target / "mtls"
    tls.mkdir(parents=True, mode=0o700, exist_ok=True)
    state.chmod(0o700)
    target.chmod(0o700)
    tls.chmod(0o700)
    data = json.loads(oc("get", "secret", "openshell-client-tls", "-n", "ai-showroom-sandbox", "-o", "json"))["data"]
    for name in ("ca.crt", "tls.crt", "tls.key"):
        path = tls / name
        path.write_bytes(base64.b64decode(data[name], validate=True))
        path.chmod(0o600)
    issuer = json.loads(oc("get", "--raw", "/.well-known/openid-configuration"))["issuer"]
    token = oc("create", "token", "showroom-openshell-client", "-n", "ai-showroom-sandbox", "--audience=showroom-openshell", "--duration=1h")
    metadata = {"name": "showroom", "gateway_endpoint": f"https://127.0.0.1:{args.port}", "gateway_port": args.port, "is_remote": True, "auth_mode": "oidc", "oidc_issuer": issuer, "oidc_client_id": "showroom-openshell", "oidc_audience": "showroom-openshell"}
    bundle = {"access_token": token, "expires_at": int(time.time()) + 3500, "issuer": issuer, "client_id": "showroom-openshell"}
    for name, value in (("metadata.json", metadata), ("oidc_token.json", bundle)):
        path = target / name
        path.write_text(json.dumps(value))
        path.chmod(0o600)
    print(f"Private CLI state created at {state}. Token expires within one hour; rerun to renew.")


if __name__ == "__main__":
    main()
