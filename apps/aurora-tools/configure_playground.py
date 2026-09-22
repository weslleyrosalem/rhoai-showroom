#!/usr/bin/env python3
"""Merge one credential-free Aurora MCP entry into the native Gen AI asset list."""
import argparse
import json
import subprocess

NAMESPACE = "redhat-ods-applications"
CONFIG = "gen-ai-aa-mcp-servers"
ENTRY = "Aurora-Supply-Showroom"
OWNER = "showroom.aurora/mcp-asset-entry"


def oc(*args):
    return subprocess.check_output(["oc", "--request-timeout=30s", *args], text=True).strip()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--expected-server", required=True)
    parser.add_argument("--expected-user", default="aiadmin")
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    if oc("whoami", "--show-server") != args.expected_server or oc("whoami") != args.expected_user:
        raise SystemExit("Unexpected cluster or identity; stopping.")
    route = json.loads(oc("get", "route", "showroom-mcp", "-n", "ai-showroom", "-o", "json"))
    if route["spec"].get("tls", {}).get("termination") != "edge" or not route["spec"].get("host"):
        raise SystemExit("The validated TLS MCP Route is required first.")
    value = json.dumps({"url": "https://" + route["spec"]["host"] + "/mcp", "description": "Aurora Supply read-only inventory and 21-day replenishment proposals, with forecast provenance and NeMo checks. OpenShift bearer authentication is required. No orders or stock changes are possible."}, indent=2)
    raw = oc("get", "configmap", CONFIG, "-n", NAMESPACE, "--ignore-not-found", "-o", "json")
    resource = json.loads(raw) if raw else {"apiVersion": "v1", "kind": "ConfigMap", "metadata": {"name": CONFIG, "namespace": NAMESPACE}}
    data = resource.setdefault("data", {})
    annotations = resource["metadata"].setdefault("annotations", {})
    if ENTRY in data and data[ENTRY] != value and annotations.get(OWNER) != ENTRY:
        raise SystemExit("Refusing to replace an existing unowned MCP entry.")
    unchanged = data.get(ENTRY) == value and annotations.get(OWNER) == ENTRY
    data[ENTRY] = value
    annotations[OWNER] = ENTRY
    if args.apply and not unchanged:
        # Existing resourceVersion prevents overwriting a concurrent administrator
        # change. Preserve all other entries and metadata; never store credentials.
        operation = "replace" if raw else "create"
        subprocess.run(["oc", operation, "-f", "-"], input=json.dumps(resource), text=True, check=True, stdout=subprocess.DEVNULL)
    print(json.dumps({"mode": "APPLIED" if args.apply else "PLAN", "entry": ENTRY, "unchanged": unchanged, "other_entries_preserved": len(data) - 1, "credentials_stored": False}))


if __name__ == "__main__":
    main()
