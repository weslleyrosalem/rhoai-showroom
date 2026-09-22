#!/usr/bin/env python3
"""Connect the private OpenShell gateway to the existing showroom MaaS key."""
import argparse
import base64
import json
import os
from pathlib import Path
import subprocess
from urllib.parse import urlsplit


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
    secret = json.loads(oc("get", "secret", "showroom-maas-key", "-n", "ai-showroom", "-o", "json"))["data"]
    values = {key: base64.b64decode(value, validate=True).decode() for key, value in secret.items()}
    domain = oc("get", "ingress.config.openshift.io", "cluster", "-o", "jsonpath={.spec.domain}")
    url = urlsplit(values["base-url"])
    if url.scheme != "https" or not url.hostname or not url.hostname.endswith("." + domain) or url.username or url.password or url.port not in (None, 443) or url.query or url.fragment:
        raise SystemExit("MaaS credentials may only be sent to the expected cluster's HTTPS application domain.")
    env = dict(os.environ, XDG_CONFIG_HOME=str(args.state_dir.resolve()), OPENAI_API_KEY=values["api-key"])
    cli = [args.cli, "-g", "showroom"]
    exists = subprocess.run(cli + ["provider", "get", "aurora-maas"], env=env, capture_output=True).returncode == 0
    provider = ["provider", "update", "aurora-maas"] if exists else ["provider", "create", "--name", "aurora-maas", "--type", "openai"]
    provider += ["--credential", "OPENAI_API_KEY", "--config", "OPENAI_BASE_URL=" + values["base-url"]]
    for step in (provider, ["inference", "set", "--provider", "aurora-maas", "--model", values["model-id"]]):
        result = subprocess.run(cli + step, env=env, capture_output=True, text=True)
        if result.returncode:
            raise SystemExit(f"OpenShell {step[0]} operation failed. Inspect gateway status; credentials were not printed.")
        print(f"OpenShell {step[0]} configuration succeeded.")


if __name__ == "__main__":
    main()
