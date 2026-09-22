#!/usr/bin/env python3
"""Discover API audience and merge only AuthPolicy audience; never persist tokens."""
import argparse
import json
from pathlib import Path
import subprocess


def oc(*args, input_text=None):
    return subprocess.run(["oc", "--request-timeout=30s", *args], input=input_text,
                          text=True, capture_output=True, check=True).stdout


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--expected-server", required=True)
    parser.add_argument("--expected-user", default="aiadmin")
    parser.add_argument("--patch-output", type=Path, help="Save credential-free strategic merge patch for a GitOps overlay")
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    if oc("whoami", "--show-server").strip().rstrip("/") != args.expected_server.rstrip("/"):
        raise SystemExit("Unexpected cluster; no change made")
    if oc("whoami").strip() != args.expected_user:
        raise SystemExit("Unexpected identity; no change made")
    review = {"apiVersion": "authentication.k8s.io/v1", "kind": "TokenReview",
              "spec": {"token": oc("whoami", "-t").strip()}}
    status = json.loads(oc("create", "-f", "-", "-o", "json", input_text=json.dumps(review))).get("status", {})
    if not status.get("authenticated") or not status.get("audiences"):
        raise SystemExit("API audience discovery failed; no change made")
    patch = {"spec": {"rules": {"authentication": {"openshift": {
        "kubernetesTokenReview": {"audiences": status["audiences"]}}}}}}
    if args.patch_output:
        args.patch_output.parent.mkdir(parents=True, exist_ok=True)
        args.patch_output.write_text(json.dumps({"apiVersion": "kuadrant.io/v1", "kind": "AuthPolicy",
            "metadata": {"name": "showroom-mcp-auth", "namespace": "ai-showroom"}, **patch}, indent=2) + "\n")
    if args.apply:
        # JSON merge changes only the audiences path and preserves other rules.
        oc("patch", "authpolicy", "showroom-mcp-auth", "-n", "ai-showroom", "--type=merge", "-p", json.dumps(patch))
    print(json.dumps({"authenticated": True, "audience_count": len(status["audiences"]),
                      "applied": args.apply, "patch_saved": bool(args.patch_output)}))


if __name__ == "__main__":
    main()
