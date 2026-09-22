#!/usr/bin/env python3
"""Merge only the Aurora MCP source into the shared catalog ConfigMap."""
import argparse
import json
from pathlib import Path
import subprocess
import yaml


def oc(*args):
    return subprocess.check_output(["oc", "--request-timeout=30s", *args], text=True)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--expected-server", required=True)
    p.add_argument("--expected-user", default="aiadmin")
    p.add_argument("--apply", action="store_true")
    args = p.parse_args()
    if oc("whoami").strip() != args.expected_user or oc("whoami", "--show-server").strip() != args.expected_server:
        raise SystemExit("Cluster or identity does not match the expected values")
    root = Path(__file__).resolve().parents[2] / "gitops/components/mcp/catalog"
    cm = json.loads(oc("get", "configmap", "mcp-catalog-sources", "-n", "rhoai-model-registries", "-o", "json"))
    sources = yaml.safe_load(cm.get("data", {}).get("sources.yaml", "mcp_catalogs: []")) or {}
    entries = sources.setdefault("mcp_catalogs", [])
    if not isinstance(entries, list):
        raise SystemExit("Unexpected catalog source schema; no changes made")
    aurora = yaml.safe_load((root / "sources.yaml").read_text())["mcp_catalogs"][0]
    preserved = [entry for entry in entries if entry.get("id") != aurora["id"]]
    sources["mcp_catalogs"] = preserved + [aurora]
    patch = {"metadata": {"resourceVersion": cm["metadata"]["resourceVersion"]}, "data": {
        "sources.yaml": yaml.safe_dump(sources, sort_keys=False),
        "aurora-showroom.yaml": (root / "aurora-catalog.yaml").read_text(),
    }}
    if args.apply:
        subprocess.run(["oc", "patch", "configmap", "mcp-catalog-sources", "-n", "rhoai-model-registries", "--type=merge", "--patch", json.dumps(patch)], check=True)
    print(json.dumps({"applied": args.apply, "source": aurora["id"], "other_sources_preserved": len(preserved)}))


if __name__ == "__main__":
    main()
