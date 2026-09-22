#!/usr/bin/env python3
"""Install the explicitly selected, private OpenShell preview extension."""
import argparse
import json
from pathlib import Path
import subprocess
import tempfile

HERE = Path(__file__).resolve().parent
CHART = "oci://ghcr.io/nvidia/openshell/helm-chart"
VERSION = "0.0.116"
DIGEST = "sha256:df55cd1538bdfb7836834c30dfcf8373b85ffea83bbfd70d50dbe69407a0d2b3"


def output(*args):
    return subprocess.check_output(args, text=True).strip()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--expected-server", required=True)
    parser.add_argument("--expected-user", default="aiadmin")
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    if output("oc", "whoami") != args.expected_user or output("oc", "whoami", "--show-server") != args.expected_server:
        raise SystemExit("Unexpected cluster or user; stopping.")
    if not output("oc", "get", "crd", "sandboxes.agents.x-k8s.io", "--ignore-not-found", "-o", "name"):
        raise SystemExit("Install and verify the pinned Agent Sandbox Operator prerequisite first.")
    issuer = json.loads(output("oc", "get", "--raw", "/.well-known/openid-configuration"))["issuer"]
    if not issuer.startswith("https://"):
        raise SystemExit("A verified HTTPS OIDC issuer is required.")
    with tempfile.TemporaryDirectory(prefix="showroom-openshell-") as directory:
        pull = subprocess.run(["helm", "pull", CHART, "--version", VERSION, "--untar", "--untardir", directory], text=True, capture_output=True, check=True)
        if DIGEST not in pull.stdout + pull.stderr:
            raise SystemExit("Pinned OCI chart digest did not match; stopping.")
        chart = Path(directory) / "helm-chart"
        subprocess.run(["patch", "-p1", "--forward", "--input", str(HERE / "chart-0.0.116.patch")], cwd=chart, check=True)
        # Server dry run validates SCC, RBAC, and namespace resources. Do not
        # print Helm-rendered Secrets or write them to a repository directory.
        namespace_exists = bool(output("oc", "get", "namespace", "ai-showroom-sandbox", "--ignore-not-found", "-o", "name"))
        dry_run = "server" if namespace_exists else "client"
        subprocess.run(["oc", "apply", "--dry-run=" + dry_run, "-k", str(HERE)], check=True)
        if not args.apply:
            print("PLAN: private subject-gated gateway, scoped SCC, no public Route, no GPU. Add --apply to install.")
            return
        subprocess.run(["oc", "apply", "-k", str(HERE)], check=True)
        subprocess.run(["helm", "upgrade", "--install", "showroom-openshell", str(chart), "--namespace", "ai-showroom-sandbox", "--values", str(HERE / "values.yaml"), "--set-string", "server.oidc.issuer=" + issuer, "--wait", "--timeout", "5m"], check=True)
        subprocess.run(["oc", "rollout", "restart", "deployment/showroom-openshell-access", "-n", "ai-showroom-sandbox"], check=True)
        subprocess.run(["oc", "rollout", "status", "deployment/showroom-openshell-access", "-n", "ai-showroom-sandbox", "--timeout=180s"], check=True)
        print("Installed private preview extension. Run the positive and negative acceptance checks before a demonstration.")


if __name__ == "__main__":
    main()
